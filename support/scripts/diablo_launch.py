"""Safely preflight and supervise a Diablo MiSTer launch.

The script intentionally defines a small loader contract instead of guessing at
an undocumented MiSTer menu API. A menu/installer supplies JSON argv arrays
for a core loader and an ARM runtime. The loader receives ``{rbf}``,
``{candidate_id}`` and a per-run ``{ready_file}``; it must exit successfully
and write exactly the candidate ID to that file once the matching core is
ready. The runtime receives the generated admission and transport environment.
No command is passed through a shell.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import Any
import uuid


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
import candidate_manifest


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "diablo-launch-contract-v1"
BOOT_ID = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
CAMPAIGN_FILES = {
    "diablo": ("DIABDAT.MPQ",),
    "hellfire": ("DIABDAT.MPQ", "hellfire.mpq", "hfmonk.mpq", "hfmusic.mpq", "hfvoice.mpq"),
}


class LaunchError(RuntimeError):
    """The launch did not reach a safe runnable state."""


@dataclass(frozen=True)
class LaunchContext:
    root: Path
    candidate_manifest: Path
    candidate_id: str
    source_id: str
    rbf: Path
    engine: Path
    campaign: str
    data_root: Path
    save_root: Path
    runtime_root: Path
    boot_id: str
    physical_base: int
    lock_file: Path


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    exit_code: int | None
    timed_out: bool
    log: Path
    retained_bytes: int
    discarded_bytes: int


class TransportLock:
    """Process-lifetime exclusive lease for the shared transport aperture.

    The lock file is deliberately persistent, but the ownership is an OS
    advisory lock.  A crashed launcher therefore releases the lease when the
    descriptor closes, while the next launch can overwrite the diagnostic
    metadata after it acquires the same file.  Keeping the descriptor open for
    the whole loader/runtime/unload sequence prevents a second process from
    writing the admitted DDR region concurrently.
    """

    def __init__(self, path: Path, handle: Any) -> None:
        self.path = path
        self._handle = handle

    @classmethod
    def acquire(cls, path: Path, context: LaunchContext) -> "TransportLock":
        path = Path(path)
        # Check the directory entry before resolving it.  Resolving first
        # would follow a redirected lock and could let a launcher claim an
        # unrelated file outside the admitted runtime directory.
        if path.is_symlink():
            raise LaunchError(f"transport lock must not be a symlink: {path}")
        path = path.resolve()
        if path.is_symlink():
            raise LaunchError(f"transport lock must not be a symlink: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = path.open("a+b")
        except OSError as error:
            raise LaunchError(f"cannot open transport lock: {path}: {error}") from error
        try:
            # Windows byte-range locking requires an existing byte and the
            # file cursor at the start of that range.  The same one-byte file
            # is harmless on POSIX, where flock locks the open description.
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\\0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError) as error:
            handle.close()
            if getattr(error, "errno", None) in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise LaunchError(f"another transport owner holds the lease: {path}") from error
            raise LaunchError(f"cannot acquire transport lock: {path}: {error}") from error
        try:
            handle.seek(0)
            handle.truncate()
            handle.write((json.dumps({"schema": "diablo-transport-lock-v1",
                                      "boot_id": context.boot_id,
                                      "candidate_id": context.candidate_id,
                                      "pid": os.getpid()}, sort_keys=True) + "\\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        except OSError as error:
            cls(path, handle).close()
            raise LaunchError(f"cannot write transport lock metadata: {path}: {error}") from error
        return cls(path, handle)

    def close(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            # Closing the descriptor still releases the process lease.  The
            # caller is already in cleanup, so do not mask the launch result.
            pass
        finally:
            self._handle.close()
            self._handle = None

    def fileno(self) -> int:
        if self._handle is None:
            raise LaunchError("transport lock is already closed")
        return self._handle.fileno()


def project_path(root: Path, value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise LaunchError(f"{label} must be a relative path below the project root")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise LaunchError(f"{label} escapes the project root") from error
    return resolved


def parse_unsigned(value: str, label: str) -> int:
    if not value or value.startswith(("+", "-")):
        raise LaunchError(f"{label} must be an unsigned integer")
    try:
        parsed = int(value, 0)
    except ValueError as error:
        raise LaunchError(f"{label} must be an unsigned integer") from error
    if parsed < 0 or parsed > (1 << 64) - 1:
        raise LaunchError(f"{label} is out of range")
    return parsed


def require_directory(path: Path, label: str, create: bool = False) -> Path:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise LaunchError(f"{label} must be a real directory: {path}")
    return path.resolve()


def require_writable_directory(path: Path, label: str) -> Path:
    path = require_directory(path, label, create=True)
    probe = path / (".diablo-write-probe-" + uuid.uuid4().hex)
    try:
        with probe.open("xb") as handle:
            handle.write(b"probe\n")
    except OSError as error:
        raise LaunchError(f"{label} is not writable: {path}: {error}") from error
    finally:
        try:
            probe.unlink()
        except FileNotFoundError:
            pass
    return path


def read_boot_id(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise LaunchError(f"cannot read boot ID: {path}: {error}") from error
    if not BOOT_ID.fullmatch(value):
        raise LaunchError("boot ID must be the current kernel UUID")
    return value.lower()


def require_candidate_artifact(root: Path, manifest: dict[str, Any], path: Path, label: str) -> Path:
    if path.is_symlink():
        raise LaunchError(f"{label} must not be a symlink: {path}")
    symlink = candidate_manifest.first_symlink_component(path.parent, root)
    if symlink is not None:
        raise LaunchError(f"{label} path must not contain a symlink: {symlink}")
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise LaunchError(f"{label} is missing or is a symlink: {resolved}")
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            continue
        candidate = Path(artifact["path"])
        candidate = candidate if candidate.is_absolute() else root / candidate
        if candidate.resolve() == resolved:
            digest = candidate_manifest.sha256_file(resolved)
            if artifact.get("sha256") == digest and artifact.get("bytes") == resolved.stat().st_size:
                return resolved
    raise LaunchError(f"{label} is not a hash-verified artifact in the candidate manifest: {resolved}")


def preflight(root: Path, candidate_path: Path, rbf: Path, engine: Path, campaign: str, data_root: Path,
              save_root: Path, runtime_root: Path, boot_id_file: Path, physical_base: str, lock_file: Path) -> LaunchContext:
    root = root.resolve()
    manifest_path = candidate_path if candidate_path.is_absolute() else root / candidate_path
    if manifest_path.is_symlink():
        raise LaunchError(f"candidate manifest must not be a symlink: {manifest_path}")
    symlink = candidate_manifest.first_symlink_component(manifest_path.parent, root)
    if symlink is not None:
        raise LaunchError(f"candidate manifest path must not contain a symlink: {symlink}")
    problems = candidate_manifest.verify_manifest(root, manifest_path)
    if problems:
        raise LaunchError("candidate manifest verification failed: " + "; ".join(problems))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_id = manifest.get("candidate_id")
    source_id = manifest.get("source_id")
    if not isinstance(candidate_id, str) or len(candidate_id) != 64 or not isinstance(source_id, str) or len(source_id) != 64:
        raise LaunchError("candidate manifest has invalid identities")
    if campaign not in CAMPAIGN_FILES:
        raise LaunchError(f"unsupported campaign: {campaign}")
    data_root = require_directory(data_root, "data root")
    for name in CAMPAIGN_FILES[campaign]:
        archive = data_root / name
        if archive.is_symlink() or not archive.is_file() or not os.access(archive, os.R_OK):
            raise LaunchError(f"required {campaign} archive is unavailable or redirected: {name}")
    save_root = require_writable_directory(save_root / campaign, "campaign save root")
    runtime_root = require_writable_directory(runtime_root, "runtime root")
    locks = require_writable_directory(runtime_root / "locks", "runtime lock directory")
    return LaunchContext(root, manifest_path.resolve(), candidate_id, source_id,
                         require_candidate_artifact(root, manifest, rbf, "RBF"),
                         require_candidate_artifact(root, manifest, engine, "engine"), campaign, data_root, save_root,
                         runtime_root, read_boot_id(boot_id_file), parse_unsigned(physical_base, "physical base"),
                         locks / lock_file.name)


def write_admission(context: LaunchContext, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise LaunchError(f"refusing to replace admission record: {path}")
    content = ("schema=diablo-reserved-ddr-admission-v1\n"
               f"boot_id={context.boot_id}\n"
               f"physical_base=0x{context.physical_base:x}\n"
               "bytes=2097152\n"
               f"candidate_id={context.candidate_id}\n")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except OSError as error:
        raise LaunchError(f"cannot create admission record: {path}: {error}") from error


def parse_command(value: str, label: str) -> list[str]:
    try:
        command = json.loads(value)
    except json.JSONDecodeError as error:
        raise LaunchError(f"{label} must be a JSON argv array: {error}") from error
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item and "\x00" not in item for item in command):
        raise LaunchError(f"{label} must be a non-empty JSON argv string array")
    return command


def render_command(command: list[str], variables: dict[str, str], label: str) -> tuple[str, ...]:
    try:
        rendered = tuple(item.format_map(variables) for item in command)
    except (KeyError, ValueError) as error:
        raise LaunchError(f"{label} has an unsupported placeholder: {error}") from error
    if not all(item for item in rendered):
        raise LaunchError(f"{label} rendered an empty argument")
    return rendered


def terminate_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/pid", str(process.pid), "/t", "/f"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, 15)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, 9)
            except ProcessLookupError:
                pass
        else:
            process.kill()


def run_logged(argv: tuple[str, ...], environment: dict[str, str], cwd: Path, log: Path, timeout_seconds: float,
               maximum_log_bytes: int, inherited_fds: tuple[int, ...] = ()) -> CommandResult:
    if timeout_seconds <= 0 or maximum_log_bytes <= 0:
        raise LaunchError("timeouts and maximum log size must be positive")
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists() or log.is_symlink():
        raise LaunchError(f"refusing to replace process log: {log}")
    popen_options: dict[str, Any] = {}
    inherited_handles: list[int] = []
    if os.name != "nt":
        if inherited_fds:
            popen_options["pass_fds"] = inherited_fds
    elif inherited_fds:
        # Windows passes kernel handles rather than POSIX descriptors.  The
        # explicit handle list keeps the launcher lock available to a child
        # without inheriting unrelated descriptors; restore inheritable flags
        # immediately after CreateProcess returns.
        import msvcrt
        startup = subprocess.STARTUPINFO()
        for descriptor in inherited_fds:
            handle = msvcrt.get_osfhandle(descriptor)
            os.set_handle_inheritable(handle, True)
            inherited_handles.append(handle)
        startup.lpAttributeList = {"handle_list": inherited_handles}
        popen_options["startupinfo"] = startup
        popen_options["close_fds"] = True
    try:
        process = subprocess.Popen(argv, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment,
                                   cwd=str(cwd), start_new_session=(os.name != "nt"), **popen_options)
    except OSError as error:
        raise LaunchError(f"cannot start {argv[0]}: {error}") from error
    finally:
        if os.name == "nt":
            for handle in inherited_handles:
                try:
                    os.set_handle_inheritable(handle, False)
                except OSError:
                    pass
    retained = 0
    discarded = 0
    lock = threading.Lock()
    with log.open("xb") as handle:
        def copy_output() -> None:
            nonlocal retained, discarded
            assert process.stdout is not None
            for chunk in iter(lambda: process.stdout.read(64 * 1024), b""):
                with lock:
                    available = max(0, maximum_log_bytes - retained)
                    if available:
                        kept = chunk[:available]
                        handle.write(kept)
                        retained += len(kept)
                    discarded += len(chunk) - min(len(chunk), available)
            handle.flush()

        reader = threading.Thread(target=copy_output, name="diablo-launch-log", daemon=True)
        reader.start()
        timed_out = False
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_tree(process)
        reader.join(timeout=10)
        if reader.is_alive():
            terminate_tree(process)
            raise LaunchError("process output reader did not terminate")
        if process.stdout is not None:
            process.stdout.close()
    return CommandResult(argv, process.returncode, timed_out, log, retained, discarded)


def wait_for_ready(path: Path, candidate_id: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file() and not path.is_symlink():
            try:
                if path.read_text(encoding="utf-8").strip() == candidate_id:
                    return
            except OSError:
                pass
        time.sleep(0.05)
    raise LaunchError("core loader did not publish readiness for the selected candidate")


def result_json(context: LaunchContext, run_id: str, admission: Path, ready: Path,
                results: list[CommandResult], status: str, error: str | None,
                lock_acquired: bool) -> dict[str, Any]:
    return {"schema": SCHEMA, "status": status, "run_id": run_id, "candidate_id": context.candidate_id,
            "source_id": context.source_id, "campaign": context.campaign,
            "admission": str(admission), "ready_file": str(ready), "lock_file": str(context.lock_file),
            "lock_acquired": lock_acquired, "error": error,
            "commands": [{"argv": list(result.argv), "exit_code": result.exit_code, "timed_out": result.timed_out,
                          "log": str(result.log), "retained_log_bytes": result.retained_bytes,
                          "discarded_log_bytes": result.discarded_bytes} for result in results]}


def run(context: LaunchContext, loader_command: list[str], runtime_command: list[str], unload_command: list[str] | None,
        startup_timeout: float, shutdown_timeout: float, maximum_log_bytes: int) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    admission = context.runtime_root / "admission" / (run_id + ".txt")
    ready = context.runtime_root / "ready" / (run_id + ".ready")
    logs = context.runtime_root / "logs"
    ready.parent.mkdir(parents=True, exist_ok=True)
    results: list[CommandResult] = []
    lease: TransportLock | None = None
    loader_started = False
    variables = {"rbf": str(context.rbf), "engine": str(context.engine), "candidate_id": context.candidate_id,
                 "campaign": context.campaign, "data_root": str(context.data_root), "save_root": str(context.save_root),
                 "runtime_root": str(context.runtime_root), "admission_file": str(admission), "ready_file": str(ready),
                 "lock_file": str(context.lock_file), "physical_base": f"0x{context.physical_base:x}"}
    environment = dict(os.environ)
    environment.update({"DIABLO_MISTER_SHARED_PHYS": variables["physical_base"], "DIABLO_MISTER_CANDIDATE_ID": context.candidate_id,
                        "DIABLO_MISTER_ADMISSION_FILE": str(admission), "DIABLO_MISTER_TRANSPORT_LOCK": str(context.lock_file),
                        "DIABLO_DATA_DIR": str(context.data_root), "DIABLO_SAVE_DIR": str(context.save_root), "DIABLO_CAMPAIGN": context.campaign})
    error: str | None = None
    try:
        lease = TransportLock.acquire(context.lock_file, context)
        environment["DIABLO_MISTER_TRANSPORT_LOCK_FD"] = str(lease.fileno())
        if os.name == "nt":
            import msvcrt
            environment["DIABLO_MISTER_TRANSPORT_LOCK_HANDLE"] = str(msvcrt.get_osfhandle(lease.fileno()))
        write_admission(context, admission)
        loader = render_command(loader_command, variables, "loader command")
        inherited_fds = (lease.fileno(),)
        loader_result = run_logged(loader, environment, context.root, logs / (run_id + ".loader.log"), startup_timeout, maximum_log_bytes,
                                   inherited_fds)
        results.append(loader_result)
        loader_started = True
        if loader_result.timed_out or loader_result.exit_code != 0:
            raise LaunchError("core loader failed before readiness")
        wait_for_ready(ready, context.candidate_id, startup_timeout)
        runtime = render_command(runtime_command, variables, "runtime command")
        runtime_result = run_logged(runtime, environment, context.root, logs / (run_id + ".runtime.log"), shutdown_timeout, maximum_log_bytes,
                                    inherited_fds)
        results.append(runtime_result)
        if runtime_result.timed_out or runtime_result.exit_code != 0:
            raise LaunchError("runtime exited with failure")
    except LaunchError as failure:
        error = str(failure)
    finally:
        if unload_command is not None and loader_started:
            try:
                unloaded = render_command(unload_command, variables, "unload command")
                results.append(run_logged(unloaded, environment, context.root, logs / (run_id + ".unload.log"), shutdown_timeout, maximum_log_bytes,
                                          inherited_fds if lease is not None else ()))
            except LaunchError as failure:
                error = error or str(failure)
        for transient in (admission, ready):
            try:
                transient.unlink()
            except FileNotFoundError:
                pass
        if lease is not None:
            lease.close()
    return result_json(context, run_id, admission, ready, results, "pass" if error is None else "fail", error,
                       lease is not None)


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--rbf", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--campaign", choices=tuple(CAMPAIGN_FILES), required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--save-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--boot-id-file", type=Path, default=Path("/proc/sys/kernel/random/boot_id"))
    parser.add_argument("--physical-base", required=True)
    parser.add_argument("--lock-file", type=Path, default=Path("transport.lock"))
    parser.add_argument("--loader-command", help="JSON argv for the core loader")
    parser.add_argument("--runtime-command", help="JSON argv for the ARM runtime")
    parser.add_argument("--unload-command", help="optional JSON argv used on menu return")
    parser.add_argument("--startup-timeout", type=float, default=30)
    parser.add_argument("--shutdown-timeout", type=float, default=30)
    parser.add_argument("--maximum-log-bytes", type=int, default=1024 * 1024)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    try:
        context = preflight(args.root, args.candidate_manifest, args.rbf, args.engine, args.campaign, args.data_root,
                            args.save_root, args.runtime_root, args.boot_id_file, args.physical_base, args.lock_file)
        if args.loader_command is None and args.runtime_command is None:
            result = {"schema": SCHEMA, "status": "preflight-pass", "candidate_id": context.candidate_id,
                      "source_id": context.source_id, "campaign": context.campaign, "rbf": str(context.rbf),
                      "engine": str(context.engine), "save_root": str(context.save_root), "runtime_root": str(context.runtime_root),
                      "transport_environment": {"DIABLO_MISTER_SHARED_PHYS": f"0x{context.physical_base:x}",
                                                  "DIABLO_MISTER_CANDIDATE_ID": context.candidate_id,
                                                  "DIABLO_MISTER_TRANSPORT_LOCK": str(context.lock_file)}}
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.loader_command is None or args.runtime_command is None:
            raise LaunchError("loader and runtime commands must be supplied together")
        result = run(context, parse_command(args.loader_command, "loader command"),
                     parse_command(args.runtime_command, "runtime command"),
                     parse_command(args.unload_command, "unload command") if args.unload_command else None,
                     args.startup_timeout, args.shutdown_timeout, args.maximum_log_bytes)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    except LaunchError as error:
        print(json.dumps({"schema": SCHEMA, "status": "fail", "error": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

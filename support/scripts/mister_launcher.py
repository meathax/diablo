"""Launch one verified Diablo package directly on a MiSTer target.

The launcher is copied into every release package and uses only Python's
standard library on the target. It verifies the package before loading its RBF,
creates a current-boot DDR admission, owns the transport lease for the child,
and keeps user game data outside the immutable package.
"""
from __future__ import annotations

import argparse
import datetime as dt
try:
    import fcntl
except ImportError:  # pragma: no cover - the production target is Linux.
    fcntl = None  # type: ignore[assignment]
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import time
from typing import Any


PACKAGE_SCHEMA = "diablo-package-manifest-v2"
DEPLOYMENT_SCHEMA = "diablo-deployment-manifest-v2"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
BOOT_ID = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
PRIVATE_MARKERS = (".mpq", ".sav", ".sve", "private", "secret", "password", "token")
SHARED_BYTES = 2 * 1024 * 1024
CAMPAIGN_FILES = {
    "diablo": ("diabdat.mpq",),
    "hellfire": ("diabdat.mpq", "hellfire.mpq", "hfmonk.mpq", "hfmusic.mpq", "hfvoice.mpq"),
}


class LaunchError(RuntimeError):
    """The package did not reach a safe runnable state."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise LaunchError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise LaunchError(f"{label} must stay below the package root")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise LaunchError(f"{label} escapes the package root") from error
    return path


def _real_file(root: Path, value: object, label: str) -> Path:
    relative = _relative(root, value, label)
    path = root / relative
    if path.is_symlink() or not path.is_file() or path.resolve().is_symlink():
        raise LaunchError(f"{label} is missing or is a symlink: {relative}")
    return path.resolve()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise LaunchError(f"{label} must be a JSON object")
    return value


def _file_records(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise LaunchError(f"package contains a symlink: {path.relative_to(root)}")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            result[relative] = path
    return result


def verify_package(root: Path) -> dict[str, Any]:
    """Verify package metadata without importing any project code."""
    root = root.resolve()
    package = _read_json(_real_file(root, "package-manifest.json", "package manifest"), "package manifest")
    if package.get("schema") != PACKAGE_SCHEMA or package.get("status") != "pass":
        raise LaunchError("unsupported or non-passing package manifest")
    if package.get("private_data_excluded") is not True:
        raise LaunchError("package manifest does not exclude private data")
    for field in ("candidate_id", "source_id"):
        if not HEX64.fullmatch(str(package.get(field, ""))):
            raise LaunchError(f"package manifest {field} is invalid")
    deployment_record = package.get("deployment_manifest")
    if not isinstance(deployment_record, dict) or deployment_record.get("path") != "deployment.json":
        raise LaunchError("package manifest has no deployment manifest")
    deployment_path = _real_file(root, "deployment.json", "deployment manifest")
    if deployment_record.get("sha256") != sha256_file(deployment_path):
        raise LaunchError("deployment manifest hash does not match package manifest")
    deployment = _read_json(deployment_path, "deployment manifest")
    if deployment.get("schema") != DEPLOYMENT_SCHEMA or deployment.get("status") != "pass":
        raise LaunchError("unsupported or non-passing deployment manifest")
    if deployment.get("private_data_excluded") is not True:
        raise LaunchError("deployment manifest does not exclude private data")
    if deployment.get("candidate_id") != package.get("candidate_id") or deployment.get("source_id") != package.get("source_id"):
        raise LaunchError("package and deployment identities differ")
    roles = {record.get("role") for record in deployment.get("artifacts", []) if isinstance(record, dict)}
    if roles != {"engine", "rbf", "abi", "launcher"}:
        raise LaunchError("deployment manifest does not contain all runtime roles")
    expected_role_paths = {"engine": "devilutionx", "rbf": "Diablo.rbf",
                           "abi": "transport_abi.hex", "launcher": "diablo_launcher.py"}
    for record in deployment.get("artifacts", []):
        if isinstance(record, dict) and record.get("role") in expected_role_paths:
            if record.get("path") != expected_role_paths[record["role"]]:
                raise LaunchError(f"deployment artifact path for {record['role']} must be {expected_role_paths[record['role']]}")
    files = _file_records(root)
    listed: set[str] = set()
    records = package.get("files")
    if not isinstance(records, list):
        raise LaunchError("package manifest files are missing")
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise LaunchError("package file record is malformed")
        relative = _relative(root, record["path"], "package file").as_posix()
        if relative in listed:
            raise LaunchError(f"package file is listed twice: {relative}")
        listed.add(relative)
        path = files.get(relative)
        if path is None or record.get("bytes") != path.stat().st_size or record.get("sha256") != sha256_file(path):
            raise LaunchError(f"package file hash/size mismatch: {relative}")
    expected = set(files) - {"package-manifest.json"}
    if listed != expected:
        raise LaunchError("package manifest does not cover exactly the installed package")
    for record in deployment.get("artifacts", []):
        if not isinstance(record, dict):
            continue
        path = _real_file(root, record.get("path"), "deployment artifact")
        if record.get("bytes") != path.stat().st_size or record.get("sha256") != sha256_file(path):
            raise LaunchError(f"deployment artifact hash/size mismatch: {record.get('role')}")
    assets = deployment.get("runtime_assets")
    if not isinstance(assets, dict) or assets.get("path") != "assets":
        raise LaunchError("deployment asset tree is missing")
    asset_records = assets.get("files")
    if not isinstance(asset_records, list):
        raise LaunchError("deployment asset records are missing")
    current_assets: list[dict[str, Any]] = []
    assets_root = _real_file(root, "assets", "assets directory") if (root / "assets").is_file() else root / "assets"
    if not assets_root.is_dir() or assets_root.is_symlink():
        raise LaunchError("assets directory is missing")
    for path in sorted(assets_root.rglob("*")):
        if path.is_symlink():
            raise LaunchError(f"assets tree contains a symlink: {path}")
        if path.is_file():
            current_assets.append({"path": path.relative_to(assets_root).as_posix(),
                                   "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    current_assets.sort(key=lambda item: str(item["path"]))
    listed_assets = sorted(asset_records, key=lambda item: str(item.get("path")) if isinstance(item, dict) else "")
    if listed_assets != current_assets or assets.get("bytes") != sum(item["bytes"] for item in current_assets):
        raise LaunchError("deployment asset tree hash/size mismatch")
    if assets.get("sha256") != hashlib.sha256(canonical_bytes(current_assets)).hexdigest():
        raise LaunchError("deployment asset tree digest mismatch")
    return {"candidate_id": package["candidate_id"], "source_id": package["source_id"],
            "board_profile": package.get("board_profile"), "deployment": deployment}


def _writable(path: Path, label: str) -> Path:
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        raise LaunchError(f"{label} must be a real directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise LaunchError(f"{label} must not be a symlink: {path}")
    probe = path / (".diablo-write-probe-" + secrets.token_hex(8))
    try:
        probe.write_bytes(b"probe\n")
    except OSError as error:
        raise LaunchError(f"{label} is not writable: {path}: {error}") from error
    finally:
        try:
            probe.unlink()
        except FileNotFoundError:
            pass
    return path.resolve()


def _boot_id(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip().lower()
    except OSError as error:
        raise LaunchError(f"cannot read boot ID: {path}: {error}") from error
    if not BOOT_ID.fullmatch(value):
        raise LaunchError("boot ID is not a kernel UUID")
    return value


def _unsigned(value: str, label: str) -> int:
    if not value or value.startswith(("+", "-")):
        raise LaunchError(f"{label} must be unsigned")
    try:
        result = int(value, 0)
    except ValueError as error:
        raise LaunchError(f"{label} must be unsigned") from error
    if result < 0:
        raise LaunchError(f"{label} must be unsigned")
    return result


def _data_file(data_root: Path, name: str) -> Path | None:
    wanted = name.casefold()
    for path in data_root.iterdir():
        if path.is_file() and not path.is_symlink() and path.name.casefold() == wanted:
            return path
    return None


def _require_campaign_data(data_root: Path, campaign: str) -> None:
    if data_root.is_symlink() or not data_root.is_dir():
        raise LaunchError(f"data root is not a real directory: {data_root}")
    missing = [name for name in CAMPAIGN_FILES[campaign] if _data_file(data_root, name) is None]
    if missing:
        raise LaunchError("missing campaign data: " + ", ".join(missing))


def _core_process_matches(rbf: Path) -> bool:
    expected = str(rbf)
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            values = entry.joinpath("cmdline").read_bytes().split(b"\0")
            argv = [value.decode("utf-8", "replace") for value in values if value]
        except OSError:
            continue
        if argv and Path(argv[0]).name == "MiSTer" and expected in argv[1:]:
            return True
    return False


def _load_core(command_path: Path, rbf: Path, timeout: float) -> None:
    if command_path.is_symlink() or not command_path.exists():
        raise LaunchError(f"MiSTer command FIFO is missing: {command_path}")
    try:
        with command_path.open("w", encoding="ascii") as command:
            command.write(f"load_core {rbf}\n")
            command.flush()
    except OSError as error:
        raise LaunchError(f"cannot request RBF load: {error}") from error
    state = Path("/sys/class/fpga_manager/fpga0/state")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if (state.read_text(encoding="ascii").strip().lower() == "operating"
                    and _core_process_matches(rbf)):
                return
        except OSError:
            pass
        time.sleep(0.25)
    raise LaunchError("FPGA/core loader did not reach operating state for the requested RBF")


def _admission(path: Path, boot_id: str, physical_base: int, candidate_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise LaunchError(f"refusing to replace admission file: {path}")
    text = ("schema=diablo-reserved-ddr-admission-v1\n" f"boot_id={boot_id}\n"
            f"physical_base=0x{physical_base:x}\n" f"bytes={SHARED_BYTES}\n" f"candidate_id={candidate_id}\n")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, text.encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _engine_args(args: argparse.Namespace, package: Path, save_root: Path, config_root: Path, log_path: Path) -> list[str]:
    command = [str(package / "devilutionx"), "--" + args.campaign,
               "--data-dir", str(args.data_root), "--save-dir", str(save_root),
               "--config-dir", str(config_root), "--lang", args.lang,
               "--verbose", "--log-to-file", str(log_path), "-n"]
    command.extend(args.engine_arg)
    return command


def _force_frame_pacing(engine_args: list[str]) -> bool:
	return any(str(value).casefold() == "--timedemo" for value in engine_args)


def _stop_engine(process: subprocess.Popen) -> int:
    """Stop only our engine process group, never the replacement MiSTer core."""
    if process.poll() is not None:
        return process.wait()
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return process.wait()
    try:
        return process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.wait(timeout=5)


def _wait_for_engine(process: subprocess.Popen, rbf: Path, duration: float) -> tuple[int, bool, bool]:
    """Invalidate this run if its core disappears, including unlimited sessions."""
    deadline = time.monotonic() + duration if duration > 0 else None
    while True:
        exit_code = process.poll()
        if exit_code is not None:
            return exit_code, False, False
        if not _core_process_matches(rbf):
            return _stop_engine(process), False, True
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            return _stop_engine(process), True, False
        try:
            return process.wait(timeout=min(0.25, remaining) if remaining is not None else 0.25), False, False
        except subprocess.TimeoutExpired:
            pass


def launch(args: argparse.Namespace) -> dict[str, Any]:
    package = args.package_root.resolve()
    identity = verify_package(package)
    candidate_id = str(identity["candidate_id"])
    data_root = args.data_root.resolve()
    _require_campaign_data(data_root, args.campaign)
    save_root = _writable(args.save_root.resolve(), "save root")
    config_root = _writable((args.config_root or (save_root / "config")).resolve(), "config root")
    runtime_root = _writable((args.runtime_root or (Path("/tmp") / ("diablo-" + candidate_id[:16]))).resolve(), "runtime root")
    boot_id = _boot_id(args.boot_id_file)
    physical_base = _unsigned(args.physical_base, "physical base")
    if physical_base % 4096 or physical_base + SHARED_BYTES > (1 << 32):
        raise LaunchError("physical base must be page aligned and fit the 32-bit target aperture")
    lock_path = runtime_root / "transport.lock"
    admission_path = runtime_root / "admission.txt"
    ready_path = runtime_root / "ready.json"
    log_path = runtime_root / "engine.log"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_path.open("a+b")
    if fcntl is None:
        lock_handle.close()
        raise LaunchError("the MiSTer launcher requires POSIX file locking")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        lock_handle.close()
        raise LaunchError(f"another transport owner holds the lease: {lock_path}") from error
    try:
        lock_handle.seek(0)
        lock_handle.truncate()
        lock_handle.write((json.dumps({"schema": "diablo-transport-lock-v1", "boot_id": boot_id,
                                       "candidate_id": candidate_id, "pid": os.getpid()}, sort_keys=True) + "\n").encode())
        lock_handle.flush()
        _load_core(args.command_path, package / "Diablo.rbf", args.loader_timeout)
        _admission(admission_path, boot_id, physical_base, candidate_id)
        ready_path.write_text(json.dumps({"schema": "diablo-mister-ready-v1", "candidate_id": candidate_id,
                                          "boot_id": boot_id, "physical_base": physical_base}) + "\n", encoding="utf-8")
        env = dict(os.environ)
        env.update({"DIABLO_MISTER_TRANSPORT": "1", "DIABLO_MISTER_SHARED_PHYS": f"0x{physical_base:x}",
                    "DIABLO_MISTER_CANDIDATE_ID": candidate_id, "DIABLO_MISTER_ADMISSION_FILE": str(admission_path),
                    "DIABLO_MISTER_TRANSPORT_LOCK": str(lock_path), "DIABLO_MISTER_TRANSPORT_LOCK_FD": str(lock_handle.fileno()),
                    "DIABLO_MISTER_SESSION_EPOCH": f"0x{secrets.randbits(32) or 1:08x}",
                    "DIABLO_DATA_DIR": str(data_root), "DIABLO_SAVE_DIR": str(save_root),
                    "DIABLO_CAMPAIGN": args.campaign, "SDL_VIDEODRIVER": "dummy",
                    "SDL_AUDIODRIVER": "dummy", "SDL_RENDER_DRIVER": "software",
                    "DIABLO_MISTER_FORCE_FRAME_PACING": "1" if _force_frame_pacing(args.engine_arg) else "0"})
        command = _engine_args(args, package, save_root, config_root, log_path)
        with log_path.open("ab") as output:
            process = subprocess.Popen(command, cwd=package, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True, pass_fds=(lock_handle.fileno(),))
            started = dt.datetime.now(dt.timezone.utc).isoformat()
            exit_code, timed_out, core_changed = _wait_for_engine(process, package / "Diablo.rbf", args.duration)
        return {"status": ("fail" if core_changed else
                           "pass" if timed_out and args.duration > 0 else ("pass" if exit_code == 0 else "fail")),
                 "timed_out": timed_out,
                 "core_changed": core_changed,
                 "stop_reason": "core_changed" if core_changed else "duration" if timed_out else "engine_exit",
                "candidate_id": candidate_id, "source_id": identity["source_id"], "campaign": args.campaign,
                "command": command, "exit_code": exit_code, "started_utc": started,
                "log": str(log_path), "admission": str(admission_path), "ready": str(ready_path),
                "forced_frame_pacing": _force_frame_pacing(args.engine_arg)}
    finally:
        for path in (admission_path, ready_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--save-root", type=Path, required=True)
    parser.add_argument("--config-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--campaign", choices=tuple(CAMPAIGN_FILES), default="diablo")
    parser.add_argument("--physical-base", default="0x3fe00000")
    parser.add_argument("--boot-id-file", type=Path, default=Path("/proc/sys/kernel/random/boot_id"))
    parser.add_argument("--command-path", type=Path, default=Path("/dev/MiSTer_cmd"))
    parser.add_argument("--loader-timeout", type=float, default=45.0)
    parser.add_argument("--duration", type=float, default=0.0,
                        help="seconds to run before clean termination; zero waits for the game")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--engine-arg", action="append", default=[],
                        help="additional argument passed to devilutionx; repeat for multiple arguments")
    args = parser.parse_args(argv)
    try:
        result = launch(args)
    except (LaunchError, OSError, ValueError) as error:
        print(json.dumps({"status": "fail", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

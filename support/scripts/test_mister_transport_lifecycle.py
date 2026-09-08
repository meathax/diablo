"""Run the production SDL transport adapter lifecycle regression under WSL.

Windows intentionally has no file-backed TransportRuntime implementation.  The
runner therefore compiles and executes the real adapter against Ubuntu's SDL2
and POSIX mmap/flock APIs, using only a temporary project-local shared file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wsl_environment() -> dict[str, str]:
    os.environ["MSYS_NO_PATHCONV"] = "1"
    os.environ["MSYS2_ARG_CONV_EXCL"] = "*"
    return os.environ.copy()


def wsl_command(arguments: list[str], distribution: str) -> list[str]:
    executable = shutil.which("wsl.exe") or shutil.which("wsl")
    if executable is None:
        raise RuntimeError("WSL is unavailable")
    return [executable, "-d", distribution, "--", *arguments]


def as_wsl_path(path: Path, environment: dict[str, str], distribution: str) -> str:
    source = str(path).replace("\\", "/")
    result = subprocess.run(wsl_command(["wslpath", "-a", source], distribution),
                            text=True, encoding="utf-8", errors="replace",
                            capture_output=True, env=environment, check=True)
    return result.stdout.strip()


def run_logged(command: list[str], log: Path, *, environment: dict[str, str] | None = None,
               timeout: int = 180) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, encoding="utf-8", errors="replace",
                               capture_output=True, env=environment, timeout=timeout, check=False)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("$ " + json.dumps(command) + "\n" + completed.stdout + completed.stderr,
                   encoding="utf-8")
    return completed


def write_immutable(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise RuntimeError(f"refusing to replace immutable lifecycle receipt: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wsl-distribution", default=os.getenv("DIABLO_WSL_DISTRIBUTION", "Ubuntu"))
    args = parser.parse_args()
    run_id = uuid.uuid4().hex
    build = ROOT / ".work" / "build" / "transport-lifecycle" / run_id
    build.mkdir(parents=True, exist_ok=False)
    compile_log = build / "compile.log"
    run_log = build / "run.log"
    shared_file = build / "transport-runtime-memory.bin"
    lock_file = build / "transport-runtime.lock"
    environment = wsl_environment()
    distribution = str(args.wsl_distribution)
    source = as_wsl_path(ROOT / "support/tests/mister_transport_lifecycle_test.cpp", environment, distribution)
    include = as_wsl_path(ROOT / "support/reference", environment, distribution)
    shared = as_wsl_path(shared_file, environment, distribution)
    lock = as_wsl_path(lock_file, environment, distribution)
    wsl_build = "/tmp/diablo-transport-lifecycle-" + run_id
    executable = wsl_build + "/transport-lifecycle"

    mkdir = run_logged(wsl_command(["mkdir", "-p", wsl_build], distribution), compile_log, environment=environment)
    if mkdir.returncode != 0:
        raise RuntimeError("could not create WSL lifecycle build directory")
    pkg = run_logged(wsl_command(["pkg-config", "--cflags", "--libs", "sdl2"], distribution),
                     build / "pkg-config.log", environment=environment)
    if pkg.returncode != 0:
        raise RuntimeError("WSL SDL2 development package is unavailable")
    pkg_flags = shlex.split(pkg.stdout.strip())
    compile_command = wsl_command([
        "g++", "-std=c++23", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread",
        "-I", include, source, *pkg_flags, "-o", executable,
    ], distribution)
    compiled = run_logged(compile_command, compile_log, environment=environment, timeout=180)
    if compiled.returncode != 0:
        raise RuntimeError(f"lifecycle regression compile failed; see {compile_log}")
    run_command = wsl_command([
        "env", "SDL_VIDEODRIVER=dummy", "DIABLO_MISTER_PROFILE=0",
        executable, shared, lock,
    ], distribution)
    executed = run_logged(run_command, run_log, environment=environment, timeout=180)
    status = "pass" if executed.returncode == 0 else "fail"
    receipt = {
        "schema": "diablo-transport-lifecycle-test-v1",
        "run_id": run_id,
        "status": status,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "distribution": distribution,
        "source": {"path": str((ROOT / "support/tests/mister_transport_lifecycle_test.cpp").relative_to(ROOT)),
                   "sha256": sha256(ROOT / "support/tests/mister_transport_lifecycle_test.cpp")},
        "inputs": {
            "runtime_header": sha256(ROOT / "support/reference/mister_transport_runtime.hpp"),
            "adapter_header": sha256(ROOT / "support/reference/mister_transport_sdl.hpp"),
            "abi_header": sha256(ROOT / "support/reference/transport_abi.hpp"),
        },
        "commands": {"compile": compile_command, "run": run_command},
        "outputs": {
            "compile_log": {"path": str(compile_log.relative_to(ROOT)).replace("\\", "/"),
                            "sha256": sha256(compile_log)},
            "run_log": {"path": str(run_log.relative_to(ROOT)).replace("\\", "/"),
                        "sha256": sha256(run_log)},
            "shared_file": str(shared_file.relative_to(ROOT)).replace("\\", "/"),
            "lock_file": str(lock_file.relative_to(ROOT)).replace("\\", "/"),
            "wsl_binary": executable,
        },
        "checks": [
            "64 production Adapter Initialize cycles with requested file-backed epochs",
            "idempotent Initialize while active",
            "idempotent Shutdown from inactive and active states",
            "production Present fault recovery rebinds a fresh epoch and resets frame ownership",
            "public PCM callback publication during active runtime and concurrent shutdown admission",
        ],
        "scope": "Linux/WSL file-backed production Adapter lifecycle and callback admission only; no FPGA, board, scene, performance or physical acceptance.",
        "exit_code": executed.returncode,
    }
    receipt_path = ROOT / ".mister" / "evidence" / "receipts" / (
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-transport-lifecycle-" + run_id + ".json")
    write_immutable(receipt_path, receipt)
    print(json.dumps({"status": status, "receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
                      "receipt_sha256": sha256(receipt_path), "run_log": str(run_log.relative_to(ROOT)).replace("\\", "/")},
                     sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

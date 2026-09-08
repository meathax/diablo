"""Run bounded local verification and publish an immutable, source-bound receipt.

This runner never loads an RBF, touches physical DDR, or invokes a board tool.
Board work remains opt-in and requires an explicitly named configuration file.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import uuid


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
import candidate_manifest


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "diablo-verification-receipt-v1"
DEPENDENCY_INPUTS = (*candidate_manifest.SOURCE_INPUTS, "support/tests")


@dataclass(frozen=True)
class Step:
    identifier: str
    commands: tuple[tuple[str, ...], ...]
    required_tools: tuple[str, ...] = ()
    timeout_seconds: int = 180


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def source_snapshot(root: Path) -> dict[str, object]:
    source_files = candidate_manifest.files_for_inputs(root, DEPENDENCY_INPUTS)
    inputs = {
        "source_files": source_files,
        "git": candidate_manifest.git_identity(root, (str(item["path"]) for item in source_files)),
    }
    return {
        "kind": "source-snapshot",
        "source_id": hashlib.sha256(canonical_bytes(inputs)).hexdigest(),
        "inputs": inputs,
        "candidate_id": None,
        "limitation": "No immutable ARM/RBF candidate manifest was supplied; this receipt cannot promote a board candidate.",
    }


def read_candidate(root: Path, manifest_argument: Path | None) -> dict[str, object]:
    snapshot = source_snapshot(root)
    if manifest_argument is None:
        return snapshot
    manifest_path = manifest_argument if manifest_argument.is_absolute() else root / manifest_argument
    problems = candidate_manifest.verify_manifest(root, manifest_path)
    if problems:
        raise RuntimeError("candidate manifest verification failed: " + "; ".join(problems))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot.update({
        "kind": "candidate-manifest",
        "candidate_id": manifest["candidate_id"],
        "candidate_manifest": str(manifest_path.resolve().relative_to(root.resolve())).replace("\\", "/"),
        "artifact_count": len(manifest["artifacts"]),
        "limitation": None,
    })
    return snapshot


def allowable_environment() -> dict[str, str]:
    result: dict[str, str] = {}
    banned_fragments = ("TOKEN", "SECRET", "PASSWORD", "PRIVATE", "KEY")
    for name, value in os.environ.items():
        if name.startswith("DIABLO_") and not any(fragment in name.upper() for fragment in banned_fragments):
            result[name] = value
    return dict(sorted(result.items()))


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/pid", str(process.pid), "/t", "/f"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        os.killpg(process.pid, signal.SIGKILL)


def execute(command: tuple[str, ...], root: Path, timeout_seconds: int) -> tuple[str, str, int | None, bool]:
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(command, cwd=root, text=True, encoding="utf-8", errors="replace",
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               creationflags=flags, start_new_session=os.name != "nt")
    try:
        output, _ = process.communicate(timeout=timeout_seconds)
        return "finished", output, process.returncode, False
    except subprocess.TimeoutExpired:
        terminate_process_tree(process)
        output, _ = process.communicate()
        return "timed_out", output, None, True


def tool_path(name: str) -> str | None:
    return shutil.which(name) or (shutil.which(name + ".exe") if not name.endswith(".exe") else None)


def rtl_step(root: Path, identifier: str, top: str, sources: tuple[str, ...], timeout_seconds: int = 180) -> Step:
    iverilog = tool_path("iverilog") or "iverilog"
    vvp = tool_path("vvp") or "vvp"
    output = root / ".work" / "build" / "verification" / (identifier + ".vvp")
    return Step(identifier, (
        (iverilog, "-g2012", "-I", str(root / "rtl"), "-s", top, "-o", str(output),
         *(str(root / item) for item in sources)),
        (vvp, str(output)),
    ), ("iverilog", "vvp"), timeout_seconds)


def selected_steps(root: Path, suite: str) -> tuple[list[Step], list[dict[str, str]]]:
    python = sys.executable
    compiler = tool_path("g++") or tool_path("clang++") or "g++"
    foundation = [Step("python-foundation", ((python, "-m", "unittest", "discover", "-s",
                                                str(root / "support" / "tests"), "-p", "test_*.py", "-v"),),
                       ("python",), 300)]
    host = [
        Step("command-renderer", ((python, str(root / "support/scripts/test_command_renderer.py")),),
             ("g++",), 180),
        Step("command-transport", ((python, str(root / "support/scripts/test_command_transport.py")),),
             ("g++",), 180),
        Step("transport-lifecycle", ((python, str(root / "support/scripts/test_mister_transport_lifecycle.py")),),
             ("wsl",), 300),
        Step("transport-abi-host", (
            (compiler, "-std=c++23", "-Wall", "-Wextra", "-Werror", "-I", str(root / "support/reference"),
             str(root / "support/tests/transport_abi_test.cpp"), "-o",
             str(root / ".work/build/verification/transport_abi_test.exe")),
            (str(root / ".work/build/verification/transport_abi_test.exe"),
             str(root / ".work/build/verification/transport_abi_header.hex")),
        ), ("g++",), 180),
        Step("indexed-frame-probe", (
            (compiler, "-std=c++23", "-Wall", "-Wextra", "-Werror", "-I", str(root / "support/reference"),
             str(root / "support/tests/indexed_frame_probe.cpp"), "-o",
             str(root / ".work/build/verification/indexed_frame_probe.exe")),
            (str(root / ".work/build/verification/indexed_frame_probe.exe"),
             str(root / ".work/build/verification/indexed_frame_probe.bin")),
        ), ("g++",), 180),
    ]
    sdl_environment = (
        os.getenv("DIABLO_TRANSPORT_SDL_BUILD_INCLUDE"),
        os.getenv("DIABLO_TRANSPORT_SDL_SOURCE_INCLUDE"),
        os.getenv("DIABLO_TRANSPORT_SDL_LIBRARY"),
    )
    arm_environment = (
        os.getenv("DIABLO_WSL_DISTRIBUTION"),
        os.getenv("DIABLO_ARM_CXX"),
        os.getenv("DIABLO_ARM_SYSROOT"),
        os.getenv("DIABLO_ARM_QEMU"),
    )
    transport_input_configured = all(sdl_environment)
    host_build_directory = os.getenv("DIABLO_HOST_BUILD_DIR")
    if host_build_directory:
        host.append(Step(
            "host-png",
            ((python, str(root / "support/scripts/test_host_png.py"), "--build-dir", host_build_directory),),
            ("ctest",), 180))
    if transport_input_configured:
        host.append(Step(
            "transport-sdl-input",
            ((python, str(root / "support/scripts/test_mister_transport_input.py"),
              "--sdl-build-include", str(sdl_environment[0]),
              "--sdl-source-include", str(sdl_environment[1]),
              "--sdl-library", str(sdl_environment[2])),),
            ("g++",), 240))
    rtl = [
        rtl_step(root, "command-consumer", "diablo_command_consumer_tb",
                 ("rtl/diablo_command_consumer.sv", "support/tests/diablo_command_consumer_tb.sv")),
        rtl_step(root, "ddr-probe", "diablo_ddr_probe_tb",
                 ("rtl/diablo_ddr_probe.sv", "support/tests/diablo_ddr_probe_tb.sv")),
        rtl_step(root, "frame-ownership", "diablo_frame_ownership_tb",
                 ("rtl/diablo_frame_ownership.sv", "support/tests/diablo_frame_ownership_tb.sv")),
        rtl_step(root, "framebuffer-scanout", "diablo_framebuffer_scanout_tb",
                 ("rtl/diablo_framebuffer_scanout.sv", "support/tests/diablo_framebuffer_scanout_tb.sv")),
        rtl_step(root, "input-capture", "diablo_input_capture_tb",
                 ("rtl/diablo_input_capture.sv", "support/tests/diablo_input_capture_tb.sv")),
        rtl_step(root, "i2s-interface", "i2s_interface_tb",
                 ("sys/i2s.v", "support/tests/i2s_interface_tb.sv")),
        rtl_step(root, "pcm-player", "diablo_pcm_player_tb",
                 ("rtl/diablo_pcm_player.sv", "support/tests/diablo_pcm_player_tb.sv")),
        rtl_step(root, "pcm-player-long", "diablo_pcm_player_long_tb",
                 ("rtl/diablo_pcm_player.sv", "support/tests/diablo_pcm_player_long_tb.sv")),
        rtl_step(root, "transport-control-reader", "diablo_transport_control_reader_tb",
                 ("rtl/diablo_transport_control_reader.sv", "support/tests/diablo_transport_control_reader_tb.sv")),
        rtl_step(root, "transport-ddram-arbiter", "diablo_transport_ddram_arbiter_tb",
                 ("rtl/diablo_transport_ddram_arbiter.sv", "support/tests/diablo_transport_ddram_arbiter_tb.sv")),
        rtl_step(root, "transport-integrated-ddr", "diablo_transport_integrated_tb", (
                 "rtl/diablo_transport_ddram_arbiter.sv", "rtl/diablo_transport_control_reader.sv",
                 "rtl/diablo_framebuffer_scanout.sv", "rtl/diablo_pcm_player.sv", "rtl/diablo_input_capture.sv",
                 "rtl/diablo_command_consumer.sv", "support/tests/diablo_transport_integrated_tb.sv")),
        rtl_step(root, "transport-abi-rtl", "transport_abi_tb", ("support/tests/transport_abi_tb.sv",)),
        rtl_step(root, "native-test-pattern", "native_test_pattern_tb",
                 ("rtl/native_test_pattern.sv", "support/tests/native_test_pattern_tb.sv"), 240),
    ]
    deferred = [
        {"id": "host-png", "status": "not_run",
         "reason": "set DIABLO_HOST_BUILD_DIR to a configured host CMake build to run the registered HostPngLoading tests."},
        {"id": "transport-sdl-input", "status": "not_run",
         "reason": "set DIABLO_TRANSPORT_SDL_BUILD_INCLUDE, DIABLO_TRANSPORT_SDL_SOURCE_INCLUDE and DIABLO_TRANSPORT_SDL_LIBRARY to run the registered SDL input fixture."},
    ]
    if suite == "foundation":
        return foundation, []
    if suite == "host":
        pending = []
        if not host_build_directory:
            pending.append(deferred[0])
        if not transport_input_configured:
            pending.append(deferred[1])
        return host, pending
    if suite == "rtl":
        return rtl, []
    if suite == "local":
        pending = []
        if not host_build_directory:
            pending.append(deferred[0])
        if not transport_input_configured:
            pending.append(deferred[1])
        return foundation + host + rtl, pending
    if suite == "arm":
        if not all(arm_environment):
            return [], [{"id": "arm-qemu", "status": "not_run",
                         "reason": "set DIABLO_WSL_DISTRIBUTION, DIABLO_ARM_CXX, DIABLO_ARM_SYSROOT and DIABLO_ARM_QEMU to run the registered ARM/QEMU ABI suite."}]
        return [Step("transport-abi-arm", ((python, str(root / "support/scripts/test_transport_abi.py")),),
                     ("g++", "iverilog", "vvp", "wsl"), 600)], []
    return [], [{"id": "board", "status": "not_run",
                 "reason": "a board adapter is intentionally not implemented by the local verification runner."}]


def record_step(step: Step, root: Path, logs: Path) -> dict[str, object]:
    missing = [name for name in step.required_tools if tool_path(name) is None]
    if missing:
        return {"id": step.identifier, "status": "not_run", "reason": "required tools unavailable: " + ", ".join(missing)}
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / (step.identifier + ".log")
    sections: list[str] = []
    status = "pass"
    exit_code: int | None = 0
    for command in step.commands:
        sections.append("$ " + json.dumps(command) + "\n")
        outcome, output, code, timed_out = execute(command, root, step.timeout_seconds)
        sections.append(output)
        if timed_out:
            status, exit_code = "timed_out", None
            break
        if code != 0:
            status, exit_code = "fail", code
            break
    log.write_text("\n".join(sections), encoding="utf-8")
    return {"id": step.identifier, "status": status, "exit_code": exit_code,
            "timeout_seconds": step.timeout_seconds,
            "commands": [list(command) for command in step.commands],
            "log": str(log.relative_to(root)).replace("\\", "/"), "log_sha256": sha256(log),
            "log_bytes": log.stat().st_size}


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise RuntimeError(f"refusing to overwrite immutable receipt: {path}") from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def run(root: Path, suite: str, candidate: Path | None, board_configuration: Path | None) -> tuple[int, dict[str, object], Path]:
    root = root.resolve()
    run_id = str(uuid.uuid4())
    started = dt.datetime.now(dt.timezone.utc)
    logs = root / ".mister" / "evidence" / "runs" / run_id
    (root / ".work" / "build" / "verification").mkdir(parents=True, exist_ok=True)
    steps, not_run = selected_steps(root, suite)
    try:
        candidate_record = read_candidate(root, candidate)
        candidate_error = None
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        candidate_record = {
            "kind": "invalid-source-snapshot",
            "source_id": None,
            "candidate_id": None,
            "inputs": {"source_files": []},
            "limitation": str(error),
        }
        candidate_error = str(error)
    if suite == "board" and board_configuration is None:
        not_run.insert(0, {"id": "board-configuration", "status": "not_run",
                           "reason": "--board-configuration is required for the board suite."})
    elif suite == "board" and not board_configuration.is_file():
        not_run.insert(0, {"id": "board-configuration", "status": "not_run",
                           "reason": f"board configuration does not exist: {board_configuration}"})
    if candidate_error is not None:
        results = [{"id": "candidate-validation", "status": "fail", "reason": candidate_error}] + not_run
    else:
        results = [record_step(step, root, logs) for step in steps] + not_run
    statuses = {str(item["status"]) for item in results}
    status = "fail" if statuses & {"fail", "timed_out"} else "incomplete" if "not_run" in statuses else "pass"
    receipt = {
        "schema": SCHEMA,
        "run_id": run_id,
        "suite": suite,
        "started_utc": started.isoformat(),
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status,
        "argv": sys.argv,
        "cwd": str(root),
        "environment_allowlist": allowable_environment(),
        "tool_identity": {"python": sys.version, "python_executable": sys.executable,
                          "g++": tool_path("g++"), "iverilog": tool_path("iverilog"), "vvp": tool_path("vvp")},
        "candidate": candidate_record,
        "dependency_snapshot": candidate_record["inputs"]["source_files"],
        "results": results,
        "scope": "Local host/RTL verification only. This receipt is not ARM, hardware, audio, video, input-device or campaign acceptance evidence.",
    }
    timestamp = started.strftime("%Y%m%dT%H%M%SZ")
    target = root / ".mister" / "evidence" / "receipts" / (timestamp + "-" + run_id + ".json")
    write_receipt(target, receipt)
    return (0 if status == "pass" else 1 if status == "fail" else 2), receipt, target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--suite", choices=("foundation", "host", "rtl", "local", "arm", "board"), required=True)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--board-configuration", type=Path)
    args = parser.parse_args(argv)
    try:
        code, receipt, path = run(args.root, args.suite, args.candidate_manifest, args.board_configuration)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "fail", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({"status": receipt["status"], "suite": args.suite,
                      "receipt": str(path.resolve().relative_to(args.root.resolve())).replace("\\", "/"),
                      "source_id": receipt["candidate"]["source_id"]}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

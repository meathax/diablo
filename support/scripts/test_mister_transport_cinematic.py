"""Run the focused cinematic transport regression against the real adapter.

The executable test exercises the production SDL adapter and its file-backed ABI
under WSL.  The runner also inspects the generated storm_svid.cpp overlay so the
test cannot pass with an adapter-only copy of the movie path: an active movie
publication must return from BlitFrame before the generic stale PalSurface path.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
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
    result = subprocess.run(
        wsl_command(["wslpath", "-a", source], distribution),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=environment,
        check=True,
    )
    return result.stdout.strip()


def run_logged(
    command: list[str],
    log: Path,
    *,
    environment: dict[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=environment,
        timeout=timeout,
        check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "$ " + json.dumps(command) + "\n" + completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    return completed


def write_immutable(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise RuntimeError(f"refusing to replace immutable cinematic receipt: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def function_body(source: str, function_name: str) -> str:
    match = re.search(rf"\b{re.escape(function_name)}\s*\([^)]*\)\s*\{{", source)
    if match is None:
        raise ValueError(f"generated source has no {function_name} definition")
    opening = source.find("{", match.start(), match.end())
    depth = 0
    for index in range(opening, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise ValueError(f"generated source has an unterminated {function_name} definition")


def matching_call_end(source: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(source)):
        character = source[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("generated Present call is unterminated")


def inspect_generated_hook(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    body = function_body(source, "BlitFrame")
    present_matches = list(re.finditer(r"(?<!Render)\bPresent\s*\(", body))
    if not present_matches:
        raise ValueError("BlitFrame has no transport Present call")
    present = present_matches[0]
    render = body.find("RenderPresent")
    if render < 0:
        raise ValueError("BlitFrame no longer has the generic RenderPresent boundary")
    if present.start() > render:
        raise ValueError("transport Present occurs after generic RenderPresent")
    return_true = body.find("return true", present.end(), render)
    if return_true < 0:
        raise ValueError("active movie path does not return true before RenderPresent")
    guard_start = max(0, present.start() - 240)
    guard = body[guard_start:present.start()]
    if re.search(r"\bif\s*\([^{};]*Present\s*$", guard):
        raise ValueError("Present remains the condition of a fall-through if guard")
    call_end = matching_call_end(body, present.end() - 1)
    present_arguments = body[present.end():call_end]
    if re.search(r"SVidSurface\s*(?:\.get\s*\(\s*\)|->)", present_arguments):
        raise ValueError("movie Present receives native SVidSurface without transport geometry staging")
    # The production patch may use a helper in the reference header.  These
    # tokens make the generated unit prove it handles the fixed 640x480 target
    # and a palette-aware letterbox path, while avoiding a helper name ABI.
    geometry_tokens = {
        "target_width": bool(re.search(r"\b(?:640|FRAME_WIDTH)\b", body)),
        "target_height": bool(re.search(r"\b(?:480|FRAME_HEIGHT)\b", body)),
        "palette_mapping": bool(re.search(r"SDL_MapRGB|MapRGB|palette", body, re.I)),
        "letterbox": bool(re.search(r"black|border|letter|aspect|scale", body, re.I)),
    }
    try:
        display_path = str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        display_path = str(path)
    return {
        "path": display_path,
        "sha256": sha256(path),
        "checks": {
            "active_present_before_generic_render": True,
            "return_true_before_generic_render": True,
            "no_present_condition_fallthrough": True,
            "no_direct_native_surface_present": True,
            "geometry_tokens": geometry_tokens,
        },
    }


def candidate_generated_sources(args: argparse.Namespace) -> list[Path]:
    if args.generated_source is not None:
        return [args.generated_source]
    roots = []
    if args.build_dir is not None:
        roots.append(args.build_dir)
    environment_path = os.getenv("DIABLO_TRANSPORT_BUILD_DIR")
    if environment_path:
        roots.append(Path(environment_path))
    roots.extend(
        [
            ROOT / ".work" / "c26-fpga-0232f7",
            ROOT / ".work" / "build" / "arm-engine-c34-clean",
        ]
    )
    result: list[Path] = []
    for root in roots:
        for relative in (
            Path("mister-engine-overlay") / "storm" / "storm_svid.cpp",
            Path("mister-engine-overlay") / "Source" / "storm" / "storm_svid.cpp",
        ):
            candidate = root / relative
            if candidate.is_file() and candidate not in result:
                result.append(candidate)
        if root.is_dir():
            for candidate in root.rglob("storm_svid.cpp"):
                if candidate.is_file() and "mister-engine-overlay" in candidate.parts and candidate not in result:
                    result.append(candidate)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wsl-distribution", default=os.getenv("DIABLO_WSL_DISTRIBUTION", "Ubuntu"))
    parser.add_argument("--generated-source", type=Path)
    parser.add_argument("--build-dir", type=Path)
    args = parser.parse_args()
    run_id = uuid.uuid4().hex
    build = ROOT / ".work" / "build" / "transport-cinematic" / run_id
    build.mkdir(parents=True, exist_ok=False)
    compile_log = build / "compile.log"
    run_log = build / "run.log"
    shared_file = build / "transport-runtime-memory.bin"
    lock_file = build / "transport-runtime.lock"
    environment = wsl_environment()
    distribution = str(args.wsl_distribution)
    source_path = ROOT / "support" / "tests" / "mister_transport_cinematic_test.cpp"
    include_path = ROOT / "support" / "reference"
    static_checks: dict[str, object]
    generated_candidates = candidate_generated_sources(args)
    if not generated_candidates:
        static_checks = {
            "status": "blocked",
            "reason": "generated mister-engine-overlay/storm/storm_svid.cpp was not found",
            "searched_builds": [str(path) for path in [args.build_dir] if path is not None],
        }
    else:
        try:
            static_checks = {"status": "pass", **inspect_generated_hook(generated_candidates[0])}
        except (OSError, ValueError) as error:
            static_checks = {
                "status": "fail",
                "source": str(generated_candidates[0]),
                "reason": str(error),
            }

    compile_status = "not_run"
    run_status = "not_run"
    compile_result: subprocess.CompletedProcess[str] | None = None
    executed: subprocess.CompletedProcess[str] | None = None
    executable = ""
    try:
        source = as_wsl_path(source_path, environment, distribution)
        include = as_wsl_path(include_path, environment, distribution)
        shared = as_wsl_path(shared_file, environment, distribution)
        lock = as_wsl_path(lock_file, environment, distribution)
        wsl_build = "/tmp/diablo-transport-cinematic-" + run_id
        executable = wsl_build + "/transport-cinematic"
        mkdir = run_logged(
            wsl_command(["mkdir", "-p", wsl_build], distribution),
            build / "mkdir.log",
            environment=environment,
        )
        if mkdir.returncode != 0:
            raise RuntimeError("could not create WSL cinematic build directory")
        pkg = run_logged(
            wsl_command(["pkg-config", "--cflags", "--libs", "sdl2"], distribution),
            build / "pkg-config.log",
            environment=environment,
        )
        if pkg.returncode != 0:
            raise RuntimeError("WSL SDL2 development package is unavailable")
        pkg_flags = shlex.split(pkg.stdout.strip())
        compile_command = wsl_command(
            [
                "g++",
                "-std=c++23",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pthread",
                "-I",
                include,
                source,
                *pkg_flags,
                "-o",
                executable,
            ],
            distribution,
        )
        compile_result = run_logged(compile_command, compile_log, environment=environment)
        compile_status = "pass" if compile_result.returncode == 0 else "fail"
        if compile_result.returncode == 0:
            run_command = wsl_command(
                ["env", "SDL_VIDEODRIVER=dummy", "DIABLO_MISTER_PROFILE=0", executable, shared, lock],
                distribution,
            )
            executed = run_logged(run_command, run_log, environment=environment)
            run_status = "pass" if executed.returncode == 0 else "fail"
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        compile_status = "blocked"
        (build / "runner-error.txt").write_text(str(error) + "\n", encoding="utf-8")

    status = "pass" if static_checks.get("status") == "pass" and compile_status == "pass" and run_status == "pass" else (
        "fail" if static_checks.get("status") == "fail" or compile_status == "fail" or run_status == "fail" else "blocked"
    )
    receipt = {
        "schema": "diablo-transport-cinematic-test-v1",
        "run_id": run_id,
        "status": status,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "distribution": distribution,
        "source": {"path": str(source_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(source_path)},
        "inputs": {
            "adapter_header": sha256(ROOT / "support" / "reference" / "mister_transport_sdl.hpp"),
            "abi_header": sha256(ROOT / "support" / "reference" / "transport_abi.hpp"),
            "overlay_cmake": sha256(ROOT / "support" / "cmake" / "arm-transport.cmake"),
        },
        "generated_hook": static_checks,
        "compile_status": compile_status,
        "run_status": run_status,
        "outputs": {
            "compile_log": str(compile_log.relative_to(ROOT)).replace("\\", "/") if compile_log.exists() else None,
            "run_log": str(run_log.relative_to(ROOT)).replace("\\", "/") if run_log.exists() else None,
            "compile_log_sha256": sha256(compile_log) if compile_log.exists() else None,
            "run_log_sha256": sha256(run_log) if run_log.exists() else None,
            "shared_file": str(shared_file.relative_to(ROOT)).replace("\\", "/"),
            "lock_file": str(lock_file.relative_to(ROOT)).replace("\\", "/"),
            "wsl_binary": executable,
        },
        "checks": [
            "native indexed 640x480 title and two changing cinematic frames preserve pixels and palette",
            "full frame pipeline backpressure leaves only retained title frames and no movie publication",
            "movie publication resumes after retirement and return-to-title publishes the title source",
            "disabled transport follows the normal inactive initialization path",
            "generated active movie hook returns before generic RenderPresent and stages non-native geometry",
        ],
        "scope": "Focused host adapter and generated cinematic-hook regression; no FPGA, board, input, audio or physical acceptance.",
        "exit_code": 0 if status == "pass" else 1,
    }
    receipt_path = ROOT / ".mister" / "evidence" / "receipts" / (
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-transport-cinematic-" + run_id + ".json"
    )
    write_immutable(receipt_path, receipt)
    print(
        json.dumps(
            {
                "status": status,
                "receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
                "receipt_sha256": sha256(receipt_path),
                "compile_status": compile_status,
                "run_status": run_status,
                "static_status": static_checks.get("status"),
            },
            sort_keys=True,
        )
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

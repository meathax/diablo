"""Qualify deterministic host-versus-ARM scene captures as immutable evidence.

This tool deliberately stops at software/reference equality.  A passing receipt
does not claim FPGA scanout, physical HDMI/audio, or controller qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "diablo-scene-oracle-v1"
SCENARIO_CAPTURE_START_MS = {"dungeon-v1": 5000}

try:
    from compare_frames import compare_series, read_frame
except ModuleNotFoundError:  # pragma: no cover - exercised when loaded by a test
    _spec = importlib.util.spec_from_file_location("compare_frames", Path(__file__).with_name("compare_frames.py"))
    if _spec is None or _spec.loader is None:  # pragma: no cover
        raise
    _frames = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_frames)
    compare_series = _frames.compare_series
    read_frame = _frames.read_frame

try:
    from candidate_manifest import verify_manifest
except ModuleNotFoundError:  # pragma: no cover - exercised when loaded by a test
    _candidate_spec = importlib.util.spec_from_file_location("candidate_manifest", Path(__file__).with_name("candidate_manifest.py"))
    if _candidate_spec is None or _candidate_spec.loader is None:  # pragma: no cover
        raise
    _candidate = importlib.util.module_from_spec(_candidate_spec)
    _candidate_spec.loader.exec_module(_candidate)
    verify_manifest = _candidate.verify_manifest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _run_success(record: dict[str, Any], side: str, scenario: str) -> bool:
    if side == "host":
        return record.get("scenario") == scenario and record.get("passed") is True
    return record.get("scenario") == scenario and record.get("status") == "passed"


def capture_records(directory: Path, scenario: str = "town-v1") -> list[dict[str, Any]]:
    if not directory.is_dir():
        raise ValueError(f"capture directory is missing: {directory}")
    if list(directory.glob("*.partial")):
        raise ValueError(f"incomplete capture remains: {directory}")
    captures = []
    for path in sorted(directory.glob("*.d8f")):
        frame = read_frame(path)
        capture = {
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": frame["sha256"],
            "frame": frame["frame"],
            "logic_ms": frame["logic_ms"],
        }
        if scenario == "dungeon-v1":
            state_path = Path(str(path) + ".state.json")
            state = _load_json(state_path)
            if (state.get("schema") != "diablo-capture-scene-state-v1"
                    or state.get("frame") != frame["frame"]
                    or state.get("logic_ms") != frame["logic_ms"]
                    or frame["logic_ms"] < SCENARIO_CAPTURE_START_MS[scenario]
                    or state.get("level") != 1 or state.get("player_level") != 1
                    or state.get("player_active") is not True
                    or state.get("transition_complete") is not True):
                raise ValueError(f"capture is not a completed level-1 dungeon frame: {path}")
            capture["scene_state"] = state
            capture["scene_state_sha256"] = sha256(state_path)
        captures.append(capture)
    if not captures:
        raise ValueError(f"no indexed captures found: {directory}")
    return captures


def _immutable_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"refusing to replace immutable scene receipt: {path}")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise RuntimeError(f"refusing to replace immutable scene receipt: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def qualify(host_dir: Path, arm_dir: Path, candidate: dict[str, Any] | None = None,
            host_role: str | None = None, arm_role: str | None = None,
            scenario: str = "town-v1") -> dict[str, Any]:
    host_dir = host_dir.resolve()
    arm_dir = arm_dir.resolve()
    host_run_path, arm_run_path = host_dir / "run.json", arm_dir / "run.json"
    host_run, arm_run = _load_json(host_run_path), _load_json(arm_run_path)
    errors: list[str] = []
    if not _run_success(host_run, "host", scenario):
        errors.append(f"host scenario is not a passed {scenario} run")
    if not _run_success(arm_run, "arm", scenario):
        errors.append(f"ARM scenario is not a passed {scenario} run")
    expected_capture_start = SCENARIO_CAPTURE_START_MS.get(scenario)
    if expected_capture_start is not None:
        for side, record in (("host", host_run), ("ARM", arm_run)):
            if record.get("capture_start_logic_ms") != expected_capture_start:
                errors.append(
                    f"{side} capture start is not {expected_capture_start}ms for {scenario}")
    if host_role is not None and host_run.get("build_role") != host_role:
        errors.append(f"host run build role is not {host_role}")
    if arm_role is not None and arm_run.get("build_role") != arm_role:
        errors.append(f"ARM run build role is not {arm_role}")
    for field in ("campaign", "scenario", "demo_sha256"):
        if host_run.get(field) != arm_run.get(field):
            errors.append(f"run metadata differs: {field}")
    host_captures: list[dict[str, Any]] = []
    arm_captures: list[dict[str, Any]] = []
    try:
        host_captures = capture_records(host_dir / "frames", scenario)
        arm_captures = capture_records(arm_dir / "frames", scenario)
        comparison = compare_series(host_dir / "frames", arm_dir / "frames")
        if not comparison.get("equal"):
            errors.append("capture series are not exactly equal")
    except (OSError, ValueError) as error:
        comparison = {"equal": False, "difference": "capture validation", "detail": str(error)}
        errors.append(str(error))
    return {
        "schema": SCHEMA,
        "run_id": str(uuid.uuid4()),
        "status": "pass" if not errors else "fail",
        "host": {
            "run": str(host_run_path),
            "run_sha256": sha256(host_run_path),
            "build_role": host_run.get("build_role"),
            "executable_sha256": host_run.get("executable_sha256"),
            "captures": host_captures,
        },
        "arm": {
            "run": str(arm_run_path),
            "run_sha256": sha256(arm_run_path),
            "build_role": arm_run.get("build_role"),
            "binary_sha256": arm_run.get("binary_sha256"),
            "captures": arm_captures,
        },
        "scenario": {
            "campaign": host_run.get("campaign"),
            "name": host_run.get("scenario"),
            "demo_sha256": host_run.get("demo_sha256"),
            "frames_compared": comparison.get("frames_compared", 0),
        },
        "comparison": comparison,
        "candidate": candidate or {"manifest": None, "candidate_id": None, "source_id": None},
        "errors": errors,
        "scope": "Exact native640 host-reference versus ARM/QEMU indexed frame and RGB888 palette equality; no FPGA, physical HDMI, audio, input, FPS or full-campaign claim",
    }


def _candidate_record(manifest_path: Path | None) -> dict[str, Any] | None:
    if manifest_path is None:
        return None
    manifest_path = manifest_path if manifest_path.is_absolute() else ROOT / manifest_path
    problems = verify_manifest(ROOT, manifest_path)
    if problems:
        raise ValueError("candidate manifest verification failed: " + "; ".join(problems))
    manifest = _load_json(manifest_path)
    for key in ("candidate_id", "source_id"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise ValueError(f"candidate manifest lacks {key}: {manifest_path}")
    return {"manifest": str(manifest_path.resolve()), "candidate_id": manifest["candidate_id"],
            "source_id": manifest["source_id"], "manifest_sha256": sha256(manifest_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, required=True, help="host-reference run directory")
    parser.add_argument("--arm", type=Path, required=True, help="ARM/QEMU run directory")
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--scenario", choices=("town-v1", "dungeon-v1"), default="town-v1")
    parser.add_argument("--host-role", default="host-reference")
    parser.add_argument("--arm-role", default="arm-reference")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    candidate = _candidate_record(args.candidate_manifest)
    receipt = qualify(args.host, args.arm, candidate, args.host_role, args.arm_role, args.scenario)
    _immutable_write(args.output, receipt)
    print(json.dumps({"status": receipt["status"], "output": str(args.output),
                      "campaign": receipt["scenario"]["campaign"],
                      "frames_compared": receipt["scenario"]["frames_compared"],
                      "errors": receipt["errors"]}, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

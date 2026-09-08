"""Run an explicit, candidate-bound MiSTer qualification profile.

The adapter deliberately does not guess at a network or menu API. A checked-in
or operator-supplied configuration names the exact argv arrays to run (for
example an SSH wrapper), and records the physical observations made for the
same candidate. Shell strings, missing observations and identity mismatches
are rejected instead of becoming an incomplete-looking pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


SCHEMA = "diablo-board-configuration-v1"
RESULT_ID = "board-qualification"
REQUIRED_OBSERVATIONS = ("video", "audio", "input", "campaign", "performance")
MAX_OUTPUT_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _identity(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def read_configuration(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"board configuration is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("board configuration must be a JSON object")
    return value


def validate_configuration(configuration: dict[str, Any], expected_candidate: str,
                           expected_source: str | None = None) -> None:
    if configuration.get("schema") != SCHEMA:
        raise ValueError("unsupported board configuration schema")
    if configuration.get("status") != "pass":
        raise ValueError("board configuration status must be pass")
    if configuration.get("candidate_id") != expected_candidate or not _identity(expected_candidate):
        raise ValueError("board configuration candidate_id does not match the selected candidate")
    source_id = configuration.get("source_id")
    if expected_source is not None and source_id != expected_source:
        raise ValueError("board configuration source_id does not match the selected candidate")
    if not isinstance(source_id, str) or not _identity(source_id):
        raise ValueError("board configuration requires a 64-hex source_id")
    target = configuration.get("target")
    if not isinstance(target, dict) or not isinstance(target.get("name"), str) or not target["name"]:
        raise ValueError("board configuration target.name is required")
    commands = configuration.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("board configuration requires at least one command")
    command_ids: set[str] = set()
    for entry in commands:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise ValueError("board command ids must be non-empty strings")
        if entry["id"] in command_ids:
            raise ValueError(f"duplicate board command id: {entry['id']}")
        command_ids.add(entry["id"])
        argv = entry.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item and "\x00" not in item for item in argv):
            raise ValueError(f"board command {entry['id']} requires a non-empty argv array")
        if any("{" in item or "}" in item for item in argv):
            allowed = {"candidate_id", "source_id", "target"}
            for item in argv:
                if "{" in item or "}" in item:
                    try:
                        rendered = item.format(candidate_id=expected_candidate, source_id=source_id,
                                                target=target["name"])
                    except (KeyError, ValueError) as error:
                        raise ValueError(f"board command {entry['id']} has unsupported placeholder") from error
                    if not rendered:
                        raise ValueError(f"board command {entry['id']} renders an empty argument")
    observations = configuration.get("observations")
    if not isinstance(observations, dict):
        raise ValueError("board configuration requires physical observations")
    for name in REQUIRED_OBSERVATIONS:
        observation = observations.get(name)
        if not isinstance(observation, dict) or observation.get("status") != "pass":
            raise ValueError(f"physical observation {name} is missing or not pass")
        if observation.get("candidate_id") != expected_candidate:
            raise ValueError(f"physical observation {name} is not bound to the selected candidate")
        if not isinstance(observation.get("method"), str) or not observation["method"]:
            raise ValueError(f"physical observation {name} requires a method")
        if not isinstance(observation.get("evidence"), list) or not observation["evidence"]:
            raise ValueError(f"physical observation {name} requires evidence references")


def _render(argv: list[str], candidate_id: str, source_id: str, target: str) -> tuple[str, ...]:
    values = {"candidate_id": candidate_id, "source_id": source_id, "target": target}
    try:
        rendered = tuple(value.format_map(values) for value in argv)
    except (KeyError, ValueError) as error:
        raise ValueError(f"unsupported board command placeholder: {error}") from error
    if not all(rendered):
        raise ValueError("board command rendered an empty argument")
    return rendered


def run_configuration(root: Path, configuration_path: Path, expected_candidate: str,
                      expected_source: str | None, log: Path, timeout_default: float = 120,
                      maximum_log_bytes: int = MAX_OUTPUT_BYTES) -> dict[str, Any]:
    configuration = read_configuration(configuration_path)
    validate_configuration(configuration, expected_candidate, expected_source)
    source_id = str(configuration["source_id"])
    target = str(configuration["target"]["name"])
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists() or log.is_symlink():
        raise ValueError(f"refusing to replace board log: {log}")
    sections: list[str] = []
    command_results: list[dict[str, Any]] = []
    overall = "pass"
    with log.open("xb") as handle:
        for entry in configuration["commands"]:
            command_id = str(entry["id"])
            argv = _render(entry["argv"], expected_candidate, source_id, target)
            timeout = float(entry.get("timeout_seconds", timeout_default))
            if timeout <= 0:
                raise ValueError(f"board command {command_id} timeout must be positive")
            started = time.monotonic()
            sections.append("$ " + json.dumps(list(argv)) + "\n")
            try:
                completed = subprocess.run(argv, cwd=root, shell=False, text=True,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           encoding="utf-8", errors="replace", timeout=timeout,
                                           check=False)
                output = completed.stdout or ""
                code = completed.returncode
                timed_out = False
            except subprocess.TimeoutExpired as error:
                output = (error.stdout or "") if isinstance(error.stdout, str) else ""
                code = None
                timed_out = True
            sections.append(output)
            command_results.append({"id": command_id, "argv": list(argv), "exit_code": code,
                                    "timed_out": timed_out, "elapsed_seconds": time.monotonic() - started})
            if timed_out or code != 0:
                overall = "fail"
        encoded = "".join(sections).encode("utf-8", errors="replace")
        handle.write(encoded[:maximum_log_bytes])
        if len(encoded) > maximum_log_bytes:
            overall = "fail"
    return {"id": RESULT_ID, "status": overall, "commands": command_results,
            "target": target, "candidate_id": expected_candidate, "source_id": source_id,
            "observations": configuration["observations"], "log": str(log.relative_to(root)).replace("\\", "/"),
            "log_sha256": sha256_file(log), "log_bytes": log.stat().st_size}


def write_result(path: Path, result: dict[str, Any]) -> None:
    """Publish a board result once; a later run must use a new receipt path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to replace board result: {path}")
    temporary = path.with_name(f".{path.name}.{os.urandom(8).hex()}.tmp")
    try:
        temporary.write_text(json.dumps({"schema": SCHEMA, **result}, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source-id")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    configuration = args.configuration if args.configuration.is_absolute() else root / args.configuration
    log = args.log if args.log.is_absolute() else root / args.log
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        result = run_configuration(root, configuration, args.candidate_id, args.source_id, log)
        write_result(output, result)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": result["status"] == "pass", "result": str(output)}, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

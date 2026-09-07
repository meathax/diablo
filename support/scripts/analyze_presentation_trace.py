"""Validate and summarize a Diablo MiSTer presentation-profile JSONL trace."""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path
from typing import Any


SCHEMA = "diablo-presentation-trace-v1"


class TraceError(ValueError):
    """The trace is malformed or incomplete for the requested qualification."""


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank percentile: deterministic, conservative and documented in
    # the output so later acceptance tooling cannot silently use another rule.
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def distribution(values: list[int]) -> dict[str, int] | None:
    if not values:
        return None
    return {
        "count": len(values),
        "min": min(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "p999": percentile(values, 0.999),
        "max": max(values),
    }


def load_trace(path: Path, require_complete: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TraceError(f"cannot read trace: {path}: {error}") from error
    if not lines:
        raise TraceError("trace is empty")
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise TraceError(f"invalid trace header JSON: {error}") from error
    if not isinstance(header, dict) or header.get("schema") != SCHEMA:
        raise TraceError(f"unsupported trace schema: {header.get('schema') if isinstance(header, dict) else None}")
    for field in ("records", "dropped_records", "timing_invalid_records"):
        if not isinstance(header.get(field), int) or header[field] < 0:
            raise TraceError(f"trace header field {field} must be a non-negative integer")
    if require_complete and header["dropped_records"] != 0:
        raise TraceError(f"trace is incomplete: {header['dropped_records']} telemetry records were overwritten")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise TraceError(f"invalid trace record JSON at line {line_number}: {error}") from error
        if not isinstance(record, dict):
            raise TraceError(f"trace record at line {line_number} is not an object")
        required = ("sequence", "start_ns", "finish_ns", "elapsed_ns", "timing_valid",
                    "published", "backpressure", "outcome")
        missing = [field for field in required if field not in record]
        if missing:
            raise TraceError(f"trace record at line {line_number} is missing: {', '.join(missing)}")
        if any(not isinstance(record[field], int) or record[field] < 0
               for field in ("sequence", "start_ns", "finish_ns", "elapsed_ns")):
            raise TraceError(f"trace record at line {line_number} has invalid numeric fields")
        if any(not isinstance(record[field], bool) for field in ("timing_valid", "published", "backpressure")):
            raise TraceError(f"trace record at line {line_number} has invalid boolean fields")
        if not isinstance(record["outcome"], str) or not record["outcome"]:
            raise TraceError(f"trace record at line {line_number} has invalid outcome")
        if record["timing_valid"]:
            if record["finish_ns"] < record["start_ns"] or record["elapsed_ns"] != record["finish_ns"] - record["start_ns"]:
                raise TraceError(f"trace record at line {line_number} has inconsistent timing")
        elif record["elapsed_ns"] != 0:
            raise TraceError(f"trace record at line {line_number} has elapsed time without valid timing")
        records.append(record)

    if header["records"] != len(records):
        raise TraceError(f"trace header declares {header['records']} records but contains {len(records)}")
    if header["timing_invalid_records"] != sum(not item["timing_valid"] for item in records):
        raise TraceError("trace timing-invalid count does not match its records")
    expected_sequence = header["dropped_records"]
    for record in records:
        if record["sequence"] != expected_sequence:
            raise TraceError(f"trace sequence is discontinuous at {record['sequence']}, expected {expected_sequence}")
        expected_sequence += 1
    return header, records


def analyze(path: Path, require_complete: bool = True) -> dict[str, Any]:
    header, records = load_trace(path, require_complete=require_complete)
    timed = [item for item in records if item["timing_valid"]]
    starts = [item["start_ns"] for item in timed]
    intervals = [later - earlier for earlier, later in zip(starts, starts[1:])]
    if any(interval < 0 for interval in intervals):
        raise TraceError("timed presentation starts are not monotonic")
    outcomes = collections.Counter(item["outcome"] for item in records)
    return {
        "schema": "diablo-presentation-trace-analysis-v1",
        "input_schema": header["schema"],
        "trace": str(path),
        "trace_complete": header["dropped_records"] == 0,
        "attempts": len(records),
        "published": sum(item["published"] for item in records),
        "backpressure": sum(item["backpressure"] for item in records),
        "timing_invalid": header["timing_invalid_records"],
        "outcomes": dict(sorted(outcomes.items())),
        "percentile_method": "nearest-rank",
        "present_duration_ns": distribution([item["elapsed_ns"] for item in timed]),
        "presentation_interval_ns": distribution(intervals),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--allow-dropped", action="store_true",
                        help="analyze an incomplete trace but report trace_complete=false")
    parser.add_argument("--max-present-p99-ns", type=int)
    parser.add_argument("--max-interval-p99-ns", type=int)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.trace, require_complete=not args.allow_dropped)
    except TraceError as error:
        print(json.dumps({"status": "fail", "error": str(error)}, sort_keys=True))
        return 1

    gates: dict[str, bool] = {}
    if args.max_present_p99_ns is not None:
        duration = result["present_duration_ns"]
        gates["max_present_p99_ns"] = duration is not None and duration["p99"] <= args.max_present_p99_ns
    if args.max_interval_p99_ns is not None:
        interval = result["presentation_interval_ns"]
        gates["max_interval_p99_ns"] = interval is not None and interval["p99"] <= args.max_interval_p99_ns
    result["gates"] = gates
    result["status"] = "pass" if all(gates.values()) else "fail"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

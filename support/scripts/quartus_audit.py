"""Strict report parsing building blocks, not an RBF acceptance authority.

Input reports remain read-only. Missing tables and unknown numeric forms fail
closed. Build freshness, source closure, hardware receipts and signed acceptance
must be established by the runner integration before any artifact can ship.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re


class AuditError(ValueError):
    pass


def rows(text: str) -> list[list[str]]:
    return [[cell.strip() for cell in line.strip().split(";")[1:-1]]
            for line in text.splitlines() if line.strip().startswith(";") and line.strip().endswith(";")]


def tables(text: str, wanted) -> dict[str, list[list[str]]]:
    result = {}
    active = None
    for row in rows(text):
        if len(row) == 1:
            active = row[0] if wanted(row[0]) else None
            if active is None:
                continue
            if active in result:
                raise AuditError(f"Duplicate table: {active}")
            result[active] = []
        elif active:
            result[active].append(row)
    return result


def number(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise AuditError(f"Unknown numeric field: {value!r}") from error
    if not parsed.is_finite():
        raise AuditError(f"Non-finite numeric field: {value!r}")
    return parsed


def require_identity(text: str, status_name: str, device: str) -> None:
    data = rows(text)
    statuses = [r[1] for r in data if len(r) > 1 and r[0] == status_name]
    devices = {r[1] for r in data if len(r) > 1 and r[0] == "Device"}
    if len(statuses) != 1 or not statuses[0].startswith("Successful -"):
        raise AuditError(f"Missing, ambiguous or unsuccessful {status_name}")
    if devices != {device}:
        raise AuditError(f"Device mismatch: expected {device}, observed {sorted(devices)}")
    if re.search(r"^\s*(?:Error|Critical Warning)\s*\(", text, re.MULTILINE):
        raise AuditError("Unreviewed error or critical warning")


def inference(text: str, contract: dict) -> dict:
    require_identity(text, "Analysis & Synthesis Status", contract["device"])
    data = tables(text, lambda title: title == "Analysis & Synthesis RAM Summary").get("Analysis & Synthesis RAM Summary")
    required_header = ["Name", "Type", "Mode", "Port A Depth", "Port A Width",
                       "Port B Depth", "Port B Width", "Size", "MIF"]
    if not data or data[0] != required_header:
        raise AuditError("Missing or unsupported RAM summary header")
    memories = {}
    for row in data[1:]:
        if len(row) != len(required_header) or row[0] in memories:
            raise AuditError("Malformed or duplicate RAM entry")
        if not re.fullmatch(r"[0-9,]+", row[7]):
            raise AuditError("Unknown inferred RAM size")
        memories[row[0]] = {"bits": int(row[7].replace(",", "")), "type": row[1], "mode": row[2]}
    if not memories:
        raise AuditError("Empty RAM summary")
    for name, expected in contract.get("required_memories", {}).items():
        if name not in memories:
            raise AuditError(f"Expected RAM was not inferred: {name}")
        if memories[name]["bits"] != expected["bits"]:
            raise AuditError(f"Wrong inferred size: {name}")
        if "mode" in expected and memories[name]["mode"] != expected["mode"]:
            raise AuditError(f"Wrong memory mode: {name}")
    observed = []
    for line in text.splitlines():
        if "uninferred due to" in line:
            match = re.search(r'RAM logic "([^"]+)" is uninferred due to (.*?) File:', line)
            if not match:
                raise AuditError("Unrecognized uninferred RAM diagnostic")
            observed.append({"name": match[1], "reason": match[2]})
    allowed = contract.get("reviewed_uninferred", [])
    expected = [{"name": x["name"], "reason": x["reason"]} for x in allowed]
    if any(not x.get("evidence") for x in allowed):
        raise AuditError("Uninferred-memory exception lacks review evidence")
    if sorted(observed, key=lambda x: x["name"]) != sorted(expected, key=lambda x: x["name"]):
        raise AuditError("Unreviewed or stale uninferred-memory exception")
    return {"inferred_memory_count": len(memories), "memories": memories, "reviewed_uninferred": observed}


TIMING_KINDS = ("Setup", "Hold", "Recovery", "Removal", "Minimum Pulse Width")


def timing(text: str, contract: dict) -> dict:
    parsed = tables(text, lambda title: bool(re.fullmatch(
        r".+ Model (Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary", title))
        or title == "Unconstrained Paths Summary")
    expected_corners = contract["required_corners"]
    if not expected_corners or len(set(expected_corners)) != len(expected_corners):
        raise AuditError("Timing contract requires unique, explicit corners")
    observed = {}
    for title, data in parsed.items():
        match = re.fullmatch(r"(.+ Model) (Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary", title)
        if not match:
            continue
        corner, kind = match.groups()
        if not data or data[0] != ["Clock", "Slack", "End Point TNS"]:
            raise AuditError(f"Unsupported timing header: {title}")
        if len(data) < 2:
            raise AuditError(f"Vacuous timing table: {title}")
        clocks = {}
        for row in data[1:]:
            if len(row) != 3 or row[0] in clocks:
                raise AuditError(f"Malformed or duplicate clock: {title}")
            slack, tns = number(row[1]), number(row[2])
            if slack < 0 or tns != 0:
                raise AuditError(f"Timing failure: {title}: {row[0]} slack={slack} TNS={tns}")
            clocks[row[0]] = {"slack_ns": str(slack), "tns_ns": str(tns)}
        observed.setdefault(corner, {})[kind] = clocks
    if set(observed) != set(expected_corners):
        raise AuditError("Missing or unexpected timing corner")
    for corner, kinds in observed.items():
        if set(kinds) != set(TIMING_KINDS):
            raise AuditError(f"Missing timing check: {corner}")
        for clock in contract.get("required_clocks", []):
            for kind in ("Setup", "Hold"):
                if clock not in kinds[kind]:
                    raise AuditError(f"Missing active clock {clock} in {corner} {kind}")
    unconstrained = parsed.get("Unconstrained Paths Summary")
    if not unconstrained or unconstrained[0] != ["Property", "Setup", "Hold"] or len(unconstrained) < 2:
        raise AuditError("Missing unconstrained-path accounting")
    properties = set()
    for row in unconstrained[1:]:
        if len(row) != 3 or row[0] in properties:
            raise AuditError("Malformed unconstrained-path accounting")
        properties.add(row[0])
        if number(row[1]) != 0 or number(row[2]) != 0:
            raise AuditError(f"Unconstrained endpoints require named export/review: {row[0]}")
    required = {"Illegal Clocks", "Unconstrained Clocks", "Unconstrained Input Ports", "Unconstrained Output Ports"}
    if not required <= properties:
        raise AuditError("Incomplete unconstrained-path accounting")
    return {"corners": observed, "unconstrained": "zero"}


def fit(text: str, contract: dict) -> dict:
    require_identity(text, "Fitter Status", contract["device"])
    resources = {}
    for label in ("Logic utilization (in ALMs)", "Total block memory bits", "Total DSP Blocks"):
        values = [row[1] for row in rows(text) if len(row) > 1 and row[0] == label]
        if not values:
            raise AuditError(f"Missing resource count: {label}")
        match = re.fullmatch(r"([\d,]+) / ([\d,]+)(?: \(\s*\d+ % \))?", values[0])
        if not match:
            raise AuditError(f"Unsupported resource count: {label}")
        used, total = [int(x.replace(",", "")) for x in match.groups()]
        if total <= 0 or used > total:
            raise AuditError(f"Resource capacity exceeded: {label}")
        resources[label] = {"used": used, "capacity": total}
    return resources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["inference", "timing", "fit"])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--encoding", choices=["cp1252", "utf-8"], default="cp1252")
    args = parser.parse_args()
    if args.output.resolve() in {args.report.resolve(), args.contract.resolve()} or args.output.exists():
        parser.error("Output must be a new file, distinct from inputs")
    report = args.report.read_bytes()
    contract = args.contract.read_bytes()
    receipt = {"schema": "diablo-quartus-report-audit-v1", "kind": args.kind,
               "report_sha256": hashlib.sha256(report).hexdigest(),
               "contract_sha256": hashlib.sha256(contract).hexdigest(),
               "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "scope": "report-only", "encoding": args.encoding, "release_acceptance": False}
    try:
        receipt["result"] = globals()[args.kind](report.decode(args.encoding), json.loads(contract))
        receipt["status"] = "pass"
        code = 0
    except (AuditError, ValueError, KeyError) as error:
        receipt.update(status="fail", error=str(error))
        code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "error": receipt.get("error"), "release_acceptance": False}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

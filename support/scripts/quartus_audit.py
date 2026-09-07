"""Strict report parsing building blocks, not an RBF acceptance authority.

Input reports remain read-only. Missing tables and unknown numeric forms fail
closed. Build freshness, source closure, hardware receipts and signed acceptance
must be established by the runner integration before any artifact can ship.
"""
from __future__ import annotations

import argparse
from collections import Counter
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


def diagnostics(text: str, contract: dict, report_sha256: str | None) -> dict:
    observed = Counter()
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"(?:Error|Critical Warning)\b", line):
            if line.startswith("Error"):
                raise AuditError("Quartus errors cannot be waived")
            if not re.fullmatch(r"Critical Warning \([0-9]+\): .+", line):
                raise AuditError("Unsupported critical-warning format")
            observed[line] += 1
    # Tabular diagnostics lack a stable code/context. They cannot be waived by
    # a similarly worded message elsewhere in the report.
    if any(cell in {"Error", "Critical Warning"} for row in rows(text) for cell in row):
        raise AuditError("Tabular error/critical warning requires separate contextual review support")
    reviews = contract.get("reviewed_diagnostics", [])
    if not isinstance(reviews, list):
        raise AuditError("Diagnostic reviews must be a list")
    expected = {}
    for review in reviews:
        if (not isinstance(review, dict)
                or set(review) != {"message", "count", "report_sha256", "evidence"}
                or not isinstance(review["message"], str)
                or not re.fullmatch(r"Critical Warning \([0-9]+\): .+", review["message"])
                or type(review["count"]) is not int or review["count"] <= 0
                or not isinstance(review["evidence"], str) or not review["evidence"].strip()):
            raise AuditError("Diagnostic review requires exact message, count and evidence")
        if (not isinstance(report_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", report_sha256)
                or review["report_sha256"] != report_sha256):
            raise AuditError("Diagnostic review report hash mismatch")
        if review["message"] in expected:
            raise AuditError("Duplicate diagnostic review")
        expected[review["message"]] = review["count"]
    if dict(observed) != expected:
        raise AuditError("Unreviewed or stale critical-warning review")
    return {"reviewed_critical_warnings": dict(observed), "ordinary_warnings_qualified": False}


def unsigned(value: str) -> int:
    if not re.fullmatch(r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)", value):
        raise AuditError(f"Unsupported integer count: {value!r}")
    return int(value.replace(",", ""))


def entity_resources(text: str, required: dict) -> dict:
    title = "Analysis & Synthesis Resource Utilization by Entity"
    data = tables(text, lambda name: name == title).get(title)
    header = ["Compilation Hierarchy Node", "Combinational ALUTs", "Dedicated Logic Registers",
              "Block Memory Bits", "DSP Blocks", "Pins", "Virtual Pins", "Full Hierarchy Name",
              "Entity Name", "Library Name"]
    if not data or data[0] != header or len(data) < 2:
        raise AuditError("Missing or unsupported per-entity resource table")
    observed = {}
    for row in data[1:]:
        if len(row) != len(header) or not row[7] or row[7] in observed:
            raise AuditError("Malformed or duplicate entity")
        match = re.fullmatch(r"([0-9,]+) \(([0-9,]+)\)", row[2])
        if not match:
            raise AuditError("Unsupported hierarchical register count")
        total, local = map(unsigned, match.groups())
        if local > total:
            raise AuditError("Local registers exceed hierarchical count")
        observed[row[7]] = {"registers_inclusive": total, "registers_local": local,
                            "block_memory_bits": unsigned(row[3])}
    if not isinstance(required, dict) or not required:
        raise AuditError("Inference requires nonempty per-entity expectations")
    for name, expected in required.items():
        if (not isinstance(expected, dict) or set(expected) != {"max_registers_inclusive", "block_memory_bits"}
                or any(type(value) is not int or value < 0 for value in expected.values())):
            raise AuditError("Entity expectation requires explicit register ceiling and memory bits")
        if name not in observed:
            raise AuditError(f"Missing expected entity: {name}")
        if (observed[name]["registers_inclusive"] > expected["max_registers_inclusive"]
                or observed[name]["block_memory_bits"] != expected["block_memory_bits"]):
            raise AuditError(f"Entity resource expectation failed: {name}")
    return observed


def inference(text: str, contract: dict, report_sha256: str | None = None) -> dict:
    require_identity(text, "Analysis & Synthesis Status", contract["device"])
    diagnostic_result = diagnostics(text, contract, report_sha256)
    required = contract.get("required_memories")
    if not isinstance(required, dict) or not required:
        raise AuditError("Inference requires nonempty expected-memory contract")
    data = tables(text, lambda title: title == "Analysis & Synthesis RAM Summary").get("Analysis & Synthesis RAM Summary")
    required_header = ["Name", "Type", "Mode", "Port A Depth", "Port A Width",
                       "Port B Depth", "Port B Width", "Size", "MIF"]
    if not data or data[0] != required_header:
        raise AuditError("Missing or unsupported RAM summary header")
    memories = {}
    for row in data[1:]:
        if len(row) != len(required_header) or row[0] in memories:
            raise AuditError("Malformed or duplicate RAM entry")
        memories[row[0]] = {"bits": unsigned(row[7]), "type": row[1], "mode": row[2],
                           **dict(zip(("port_a_depth", "port_a_width", "port_b_depth", "port_b_width"),
                                      map(unsigned, row[3:7])))}
    if not memories:
        raise AuditError("Empty RAM summary")
    for name, expected in required.items():
        if (not isinstance(expected, dict) or not {"bits", "mode", "port_a_depth", "port_a_width", "port_b_depth", "port_b_width"} <= set(expected)
                or set(expected) - {"bits", "type", "mode", "port_a_depth", "port_a_width", "port_b_depth", "port_b_width"}):
            raise AuditError("Memory expectation requires explicit size, mode and port dimensions")
        for key, value in expected.items():
            if key in {"type", "mode"}:
                if not isinstance(value, str) or not value.strip():
                    raise AuditError("Memory type/mode must be explicit")
            elif type(value) is not int or value < 0 or (key == "bits" and value == 0):
                raise AuditError("Invalid expected memory size/dimension")
        if name not in memories:
            raise AuditError(f"Expected RAM was not inferred: {name}")
        if any(memories[name][key] != value for key, value in expected.items()):
            raise AuditError(f"Wrong inferred memory shape: {name}")
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
    entities = entity_resources(text, contract.get("required_entities"))
    return {"inferred_memory_count": len(memories), "memories": memories, "reviewed_uninferred": observed,
            "entities": entities, "diagnostics": diagnostic_result}


TIMING_KINDS = ("Setup", "Hold", "Recovery", "Removal", "Minimum Pulse Width")
UNCONSTRAINED_PROPERTIES = ("Illegal Clocks", "Unconstrained Clocks",
                            "Unconstrained Input Ports", "Unconstrained Output Ports")
DOMAINS = ("Setup", "Hold")


def strict_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AuditError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    result = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise AuditError("Expected JSON object")
    return result


def endpoint_names(groups: dict) -> set[tuple[str, str, str]]:
    """Require all eight groups, including empty ones; never infer a domain."""
    if not isinstance(groups, dict) or set(groups) != set(DOMAINS):
        raise AuditError("Endpoint export requires explicit Setup and Hold domains")
    result = set()
    for domain, properties in groups.items():
        if not isinstance(properties, dict) or set(properties) != set(UNCONSTRAINED_PROPERTIES):
            raise AuditError(f"Incomplete or unknown endpoint categories: {domain}")
        for category, names in properties.items():
            if not isinstance(names, list):
                raise AuditError("Endpoint names must be lists")
            for name in names:
                if (not isinstance(name, str) or not name.strip()
                        or any(ord(char) < 32 for char in name)):
                    raise AuditError("Invalid endpoint name")
                key = (domain, category, name)
                if key in result:
                    raise AuditError(f"Duplicate endpoint: {key}")
                result.add(key)
    return result


def normalize_unconstrained(report: bytes, groups: dict) -> dict:
    """Normalize already labelled runner data; this does not parse raw headings."""
    endpoint_names(groups)
    return {"schema": "diablo-unconstrained-export-v1",
            "report_sha256": hashlib.sha256(report).hexdigest(),
            "domains": {domain: {category: sorted(groups[domain][category])
                                 for category in UNCONSTRAINED_PROPERTIES}
                        for domain in DOMAINS}}


def unconstrained_accounting(data: list, contract: dict, export: dict | None,
                            report_sha256: str | None) -> dict:
    if not data or data[0] != ["Property", "Setup", "Hold"]:
        raise AuditError("Missing unconstrained-path accounting")
    counts = {}
    for row in data[1:]:
        if len(row) != 3 or row[0] in counts or row[0] not in UNCONSTRAINED_PROPERTIES:
            raise AuditError("Malformed or unknown unconstrained-path accounting")
        if any(not re.fullmatch(r"[0-9]+", value) for value in row[1:]):
            raise AuditError("Unconstrained counts must be nonnegative integers")
        counts[row[0]] = dict(zip(DOMAINS, map(int, row[1:])))
    if set(counts) != set(UNCONSTRAINED_PROPERTIES):
        raise AuditError("Incomplete unconstrained-path accounting")
    observed = set()
    if export is not None:
        if (not isinstance(export, dict)
                or set(export) != {"schema", "report_sha256", "domains"}
                or export["schema"] != "diablo-unconstrained-export-v1"):
            raise AuditError("Unsupported endpoint export schema")
        if (not isinstance(report_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", report_sha256)
                or export["report_sha256"] != report_sha256):
            raise AuditError("Endpoint export report hash mismatch")
        observed = endpoint_names(export["domains"])
    for category, domains in counts.items():
        for domain, count in domains.items():
            actual = sum(1 for d, c, _ in observed if (d, c) == (domain, category))
            if count != actual:
                raise AuditError(f"Endpoint count mismatch: {domain} {category}: report={count} export={actual}")
    reviews = contract.get("reviewed_unconstrained", [])
    if not isinstance(reviews, list):
        raise AuditError("Endpoint reviews must be a list")
    reviewed = set()
    for review in reviews:
        if (not isinstance(review, dict)
                or set(review) != {"domain", "property", "name", "evidence"}
                or any(not isinstance(value, str) or not value.strip() for value in review.values())):
            raise AuditError("Endpoint review requires exact identity and evidence")
        key = (review["domain"], review["property"], review["name"])
        if key in reviewed:
            raise AuditError(f"Duplicate endpoint review: {key}")
        reviewed.add(key)
    if reviewed != observed:
        raise AuditError("Unreviewed endpoint or stale endpoint review")
    return {"counts": counts, "reviewed_endpoint_count": len(reviewed),
            "export_present": export is not None}


def timing(text: str, contract: dict, export: dict | None = None,
           report_sha256: str | None = None) -> dict:
    diagnostic_result = diagnostics(text, contract, report_sha256)
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
    accounting = unconstrained_accounting(parsed.get("Unconstrained Paths Summary"),
                                         contract, export, report_sha256)
    return {"corners": observed, "unconstrained": accounting, "diagnostics": diagnostic_result}


def fit(text: str, contract: dict, report_sha256: str | None = None) -> dict:
    require_identity(text, "Fitter Status", contract["device"])
    diagnostics(text, contract, report_sha256)
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
    parser.add_argument("--unconstrained-export", type=Path,
                        help="Explicit Setup/Hold named export; timing diagnostics only")
    args = parser.parse_args()
    if args.unconstrained_export and args.kind != "timing":
        parser.error("Endpoint export is only supported for timing")
    inputs = [args.report, args.contract]
    if args.unconstrained_export:
        inputs.append(args.unconstrained_export)
    if args.output.resolve() in {path.resolve() for path in inputs} or args.output.exists():
        parser.error("Output must be a new file, distinct from inputs")
    report = args.report.read_bytes()
    contract = args.contract.read_bytes()
    receipt = {"schema": "diablo-quartus-report-audit-v1", "kind": args.kind,
               "report_sha256": hashlib.sha256(report).hexdigest(),
               "contract_sha256": hashlib.sha256(contract).hexdigest(),
               "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "scope": "report-only", "encoding": args.encoding, "release_acceptance": False}
    try:
        export = None
        if args.unconstrained_export:
            raw_export = args.unconstrained_export.read_bytes()
            receipt["unconstrained_export_sha256"] = hashlib.sha256(raw_export).hexdigest()
            export = strict_json(raw_export)
        options = {"report_sha256": receipt["report_sha256"]}
        if args.kind == "timing":
            options["export"] = export
        receipt["result"] = globals()[args.kind](report.decode(args.encoding), strict_json(contract), **options)
        receipt["status"] = "pass"
        code = 0
    except (AuditError, ValueError, KeyError, OSError, TypeError) as error:
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

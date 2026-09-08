"""Validate the audit's explicit closure gate matrix and evidence records.

The evaluator is deliberately conservative. A C-item is not closed merely
because a status field says so: it needs every listed immutable evidence file,
all prerequisites must be closed, and each verification receipt must describe
the same source identity. A candidate manifest may be supplied to reject
evidence from a changed source or artifact set before promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MATRIX_SCHEMA = "diablo-closure-gate-matrix-v1"
RECORD_SCHEMA = "diablo-closure-record-v1"
RECEIPT_SCHEMA = "diablo-verification-receipt-v1"
ITEM_IDS = tuple(f"C{number:02d}" for number in range(1, 35))
VALID_STATES = {"open", "in_progress", "blocked", "closed", "waived"}
VALID_EVIDENCE_KINDS = {"receipt", "artifact"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")

# Closure evidence is a typed contract.  A hash proves that a file is the file
# named by the record; it does not prove that the file describes a passing test.
# These schemas keep the release evaluator from accepting arbitrary JSON/text as
# campaign, timing, performance or package evidence.
ARTIFACT_SCHEMAS = {
    "candidate-manifest": "diablo-candidate-manifest-v1",
    "benchmark-analysis": "diablo-benchmark-analysis-v1",
    "physical-matrix": "diablo-physical-matrix-v1",
    "controller-multiplayer-matrix": "diablo-controller-multiplayer-matrix-v1",
    "timing-report": "diablo-timing-report-v1",
    "inventory": "diablo-source-inventory-v1",
    "snapshot-build": "diablo-snapshot-build-v1",
    "package-manifest": "diablo-package-manifest-v2",
}

REQUIRED_PHYSICAL_MODE = "HDMI framebuffer/scaler"
UNTESTED_PHYSICAL_MODES = ("Direct RGB", "Analog/scandoubler")
UNTESTED_PHYSICAL_DISPOSITION = "best_effort_untested"


class GateError(RuntimeError):
    """An invalid matrix or unusable closure record."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise GateError(f"JSON object required: {path}")
    return value


def relative_path(root: Path, text: object, label: str) -> Path:
    if not isinstance(text, str) or not text:
        raise GateError(f"{label} requires a non-empty relative path")
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise GateError(f"{label} must stay below the project root: {text}")
    result = (root / candidate).resolve()
    try:
        result.relative_to(root.resolve())
    except ValueError as error:
        raise GateError(f"{label} escapes the project root: {text}") from error
    return result


def matrix_digest(matrix: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(matrix)).hexdigest()


def documented_items(root: Path, plan: dict[str, Any]) -> set[str]:
    path = relative_path(root, plan.get("path"), "plan.path")
    if not path.is_file():
        raise GateError(f"plan file is missing: {path}")
    headings = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### C") and len(line) >= 7 and line[4:7] in ITEM_IDS:
            headings.add(line[4:7])
    return headings


def require_strings(value: object, label: str, minimum: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum or not all(isinstance(item, str) and item for item in value):
        raise GateError(f"{label} must be a list of at least {minimum} non-empty strings")
    return list(value)


def validate_physical_output_scope(scope: dict[str, Any]) -> None:
    policy = scope.get("physical_output")
    if not isinstance(policy, dict):
        raise GateError("scope.physical_output is missing")
    required = policy.get("required_modes")
    if required != [REQUIRED_PHYSICAL_MODE]:
        raise GateError("scope.physical_output.required_modes must require HDMI framebuffer/scaler only")
    untested = policy.get("untested_modes")
    if not isinstance(untested, list):
        raise GateError("scope.physical_output.untested_modes must be a list")
    if {entry.get("id") for entry in untested if isinstance(entry, dict)} != set(UNTESTED_PHYSICAL_MODES) or len(untested) != len(UNTESTED_PHYSICAL_MODES):
        raise GateError("scope.physical_output.untested_modes must enumerate Direct RGB and Analog/scandoubler")
    output_modes = scope.get("output_modes")
    if not isinstance(output_modes, list):
        raise GateError("scope.output_modes is required for physical output scope")
    for mode_id in (REQUIRED_PHYSICAL_MODE, *UNTESTED_PHYSICAL_MODES):
        matches = [mode for mode in output_modes if mode_id.casefold() in mode.casefold()]
        if len(matches) != 1:
            raise GateError(f"scope.output_modes must contain exactly one row for {mode_id}")
    for entry in untested:
        if not isinstance(entry, dict) or entry.get("status") != "untested" or entry.get("disposition") != UNTESTED_PHYSICAL_DISPOSITION:
            raise GateError("scope.physical_output untested rows require status=untested and best_effort_untested")
        if not isinstance(entry.get("rationale"), str) or not entry["rationale"]:
            raise GateError("scope.physical_output untested rows require a rationale")


def validate_output_mode_qualification(value: object, scope: dict[str, Any], label: str) -> None:
    validate_physical_output_scope(scope)
    if not isinstance(value, dict):
        raise GateError(f"{label} requires output_mode_qualification")
    expected = (REQUIRED_PHYSICAL_MODE, *UNTESTED_PHYSICAL_MODES)
    if set(value) != set(expected):
        missing = sorted(set(expected) - set(value))
        extra = sorted(set(value) - set(expected))
        raise GateError(f"{label} output_mode_qualification must enumerate all modes; missing={missing}, extra={extra}")
    hdmi = value[REQUIRED_PHYSICAL_MODE]
    if not isinstance(hdmi, dict) or hdmi.get("status") != "pass":
        raise GateError(f"{label} HDMI framebuffer/scaler qualification must be pass")
    if not isinstance(hdmi.get("evidence"), list) or not hdmi["evidence"]:
        raise GateError(f"{label} HDMI framebuffer/scaler qualification requires evidence")
    policy_rows = {entry["id"]: entry for entry in scope["physical_output"]["untested_modes"]}
    for mode_id in UNTESTED_PHYSICAL_MODES:
        entry = value[mode_id]
        if not isinstance(entry, dict) or entry.get("status") != "untested":
            raise GateError(f"{label} {mode_id} must remain explicitly untested")
        if entry.get("disposition") != policy_rows[mode_id]["disposition"]:
            raise GateError(f"{label} {mode_id} has an unauthorized disposition")
        if not isinstance(entry.get("rationale"), str) or not entry["rationale"]:
            raise GateError(f"{label} {mode_id} requires an untested rationale")


def validate_matrix(root: Path, matrix: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    try:
        if matrix.get("schema") != MATRIX_SCHEMA:
            raise GateError("unsupported gate matrix schema")
        plan = matrix.get("plan")
        if not isinstance(plan, dict):
            raise GateError("matrix plan section is missing")
        expected = require_strings(plan.get("items"), "plan.items")
        if tuple(expected) != ITEM_IDS:
            raise GateError("plan.items must list C01 through C34 exactly once and in order")
        if documented_items(root, plan) != set(ITEM_IDS):
            raise GateError("the linked plan must contain exactly the C01-C34 headings")
        scope = matrix.get("scope")
        if not isinstance(scope, dict):
            raise GateError("scope section is missing")
        for field in ("campaigns", "output_modes", "control_devices", "multiplayer", "workflows"):
            require_strings(scope.get(field), f"scope.{field}")
        # Output evidence is connector/mux specific.  Keep the release matrix
        # from silently collapsing back to the old two-line descriptions that
        # could make an HDMI result look like proof for analog/direct paths.
        output_modes = scope["output_modes"]
        required_mode_tokens = ("HDMI", "Direct RGB", "Analog/scandoubler")
        if len(output_modes) != len(required_mode_tokens) or any(
            not any(token.lower() in mode.lower() for mode in output_modes)
            for token in required_mode_tokens
        ):
            raise GateError("scope.output_modes must enumerate HDMI, Direct RGB and Analog/scandoubler rows")
        validate_physical_output_scope(scope)
        targets = matrix.get("targets")
        if not isinstance(targets, dict):
            raise GateError("numeric target section is missing")
        for field in ("cadence", "performance", "input", "durations"):
            if not isinstance(targets.get(field), dict) or not targets[field]:
                raise GateError(f"targets.{field} must be a non-empty object")
        required_numbers = {
            ("cadence", "refresh_hz"), ("cadence", "rtl_consecutive_refreshes"),
            ("performance", "target_fps"), ("performance", "p99_presentation_ms"),
            ("performance", "max_late_prepared_percent"), ("input", "p95_visible_ms"),
            ("input", "p99_visible_ms"), ("durations", "combined_gameplay_minutes_per_campaign"),
            ("durations", "idle_minutes"), ("durations", "lifecycle_cycles"),
            ("durations", "multiplayer_minutes_per_campaign_pairing"),
        }
        for section, name in required_numbers:
            value = targets[section].get(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise GateError(f"targets.{section}.{name} must be a positive number")
        classes = matrix.get("change_classes")
        if not isinstance(classes, dict) or not classes or not all(isinstance(key, str) and isinstance(value, str)
                                                                     for key, value in classes.items()):
            raise GateError("change_classes must map names to descriptions")
        items = matrix.get("items")
        if not isinstance(items, dict) or set(items) != set(ITEM_IDS):
            raise GateError("items must define C01 through C34 exactly once")
        for item_id in ITEM_IDS:
            specification = items[item_id]
            if not isinstance(specification, dict):
                raise GateError(f"{item_id} must be an object")
            require_strings(specification.get("requirements"), f"{item_id}.requirements")
            dependencies = specification.get("dependencies")
            if not isinstance(dependencies, list) or not all(isinstance(value, str) for value in dependencies):
                raise GateError(f"{item_id}.dependencies must be a list of item IDs")
            if len(set(dependencies)) != len(dependencies) or item_id in dependencies or any(value not in ITEM_IDS for value in dependencies):
                raise GateError(f"{item_id}.dependencies has an invalid or duplicate item")
            invalidated_by = require_strings(specification.get("invalidated_by"), f"{item_id}.invalidated_by")
            if any(value not in classes for value in invalidated_by):
                raise GateError(f"{item_id}.invalidated_by names an unknown change class")
            evidence = specification.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise GateError(f"{item_id}.evidence must be a non-empty list")
            evidence_ids: set[str] = set()
            for requirement in evidence:
                if not isinstance(requirement, dict):
                    raise GateError(f"{item_id}.evidence entries must be objects")
                evidence_id = requirement.get("id")
                kind = requirement.get("kind")
                if not isinstance(evidence_id, str) or not evidence_id or evidence_id in evidence_ids:
                    raise GateError(f"{item_id}.evidence ids must be unique non-empty strings")
                if kind not in VALID_EVIDENCE_KINDS:
                    raise GateError(f"{item_id}.{evidence_id} has an unsupported evidence kind")
                if kind == "receipt" and requirement.get("suite") not in {"foundation", "host", "rtl", "local", "arm", "board"}:
                    raise GateError(f"{item_id}.{evidence_id} requires a supported receipt suite")
                evidence_ids.add(evidence_id)
        release = matrix.get("release")
        if not isinstance(release, dict) or release.get("requires_all_items_closed") is not True:
            raise GateError("release must require every C-item to be closed or explicitly waived")
    except GateError as error:
        problems.append(str(error))
    return problems


def valid_identity(value: object) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def validate_log(root: Path, result: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    try:
        path = relative_path(root, result.get("log"), "receipt log path")
        if not path.is_file():
            raise GateError(f"receipt log is missing: {path}")
        observed_hash = sha256_file(path)
        if result.get("log_sha256") != observed_hash:
            raise GateError(f"receipt log hash does not match result: {path}")
        observed_bytes = path.stat().st_size
        if result.get("log_bytes") != observed_bytes:
            raise GateError(f"receipt log byte count does not match result: {path}")
    except GateError as error:
        problems.append(str(error))
    return problems


def validate_receipt(root: Path, evidence: dict[str, Any], requirement: dict[str, Any], record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    try:
        path = relative_path(root, evidence.get("path"), "receipt evidence path")
        if not path.is_file():
            raise GateError(f"receipt is missing: {path}")
        observed_hash = sha256_file(path)
        if evidence.get("sha256") != observed_hash:
            raise GateError(f"receipt hash does not match evidence record: {path}")
        receipt = read_json(path)
        if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") != "pass":
            raise GateError(f"receipt is not a passing {RECEIPT_SCHEMA} record: {path}")
        if receipt.get("suite") != requirement.get("suite"):
            raise GateError(f"receipt suite differs from {requirement.get('suite')}: {path}")
        candidate = receipt.get("candidate")
        if not isinstance(candidate, dict) or candidate.get("source_id") != record.get("source_id"):
            raise GateError(f"receipt source identity differs from closure record: {path}")
        expected_candidate = record.get("candidate_id")
        if not valid_identity(expected_candidate) or candidate.get("candidate_id") != expected_candidate:
            raise GateError(f"receipt candidate identity differs from closure record: {path}")
        results = receipt.get("results")
        if not isinstance(results, list) or not results:
            raise GateError(f"receipt has no result records: {path}")
        result_ids: set[str] = set()
        for result in results:
            if not isinstance(result, dict) or not isinstance(result.get("id"), str) or not result["id"]:
                raise GateError(f"receipt has an invalid result record: {path}")
            if result["id"] in result_ids:
                raise GateError(f"receipt has duplicate result id {result['id']}: {path}")
            result_ids.add(result["id"])
            if result.get("status") != "pass":
                raise GateError(f"receipt result {result['id']} is not pass: {path}")
            problems.extend(validate_log(root, result))
    except GateError as error:
        problems.append(str(error))
    return problems


def validate_artifact(root: Path, evidence: dict[str, Any], requirement: dict[str, Any],
                      matrix: dict[str, Any], record: dict[str, Any]) -> list[str]:
    try:
        path = relative_path(root, evidence.get("path"), "artifact evidence path")
        if not path.is_file():
            raise GateError(f"artifact is missing: {path}")
        if evidence.get("sha256") != sha256_file(path):
            raise GateError(f"artifact hash does not match evidence record: {path}")
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise GateError(f"typed artifact is not valid JSON: {path}") from error
        if not isinstance(artifact, dict):
            raise GateError(f"typed artifact must be a JSON object: {path}")
        evidence_id = requirement.get("id")
        expected_schema = ARTIFACT_SCHEMAS.get(evidence_id)
        if expected_schema is None:
            raise GateError(f"no typed schema is registered for artifact evidence {evidence_id}")
        if artifact.get("schema") != expected_schema:
            raise GateError(f"artifact schema does not match {evidence_id}: {path}")
        if artifact.get("status") != "pass":
            raise GateError(f"artifact status is not pass: {path}")
        if artifact.get("candidate_id") != record.get("candidate_id") or not valid_identity(artifact.get("candidate_id")):
            raise GateError(f"artifact candidate identity differs from closure record: {path}")
        expected_artifact_source = ((record.get("manifest_source_id") or record.get("source_id"))
                                    if evidence_id == "candidate-manifest" else record.get("source_id"))
        if artifact.get("source_id") != expected_artifact_source or not valid_identity(artifact.get("source_id")):
            raise GateError(f"artifact source identity differs from closure record: {path}")
        if evidence_id == "candidate-manifest":
            inputs = artifact.get("inputs")
            artifacts = artifact.get("artifacts")
            if not isinstance(inputs, dict) or not isinstance(inputs.get("source_files"), list) or not inputs["source_files"]:
                raise GateError(f"candidate manifest has no source input inventory: {path}")
            if not isinstance(artifacts, list) or not artifacts:
                raise GateError(f"candidate manifest has no build artifacts: {path}")
        elif evidence_id == "benchmark-analysis":
            targets = matrix["targets"]
            metrics = artifact.get("metrics")
            runs = artifact.get("runs")
            if not isinstance(metrics, dict) or not isinstance(runs, list) or len(runs) < targets["performance"]["paired_runs"]:
                raise GateError(f"benchmark artifact lacks the required paired runs: {path}")
            required_metrics = ("fps", "p99_presentation_ms", "late_prepared_percent")
            if any(not isinstance(metrics.get(name), (int, float)) or isinstance(metrics.get(name), bool)
                   or not math.isfinite(float(metrics[name])) for name in required_metrics):
                raise GateError(f"benchmark artifact lacks finite headline metrics: {path}")
            if metrics["fps"] < targets["performance"]["target_fps"]:
                raise GateError(f"benchmark FPS is below target: {path}")
            if metrics["p99_presentation_ms"] > targets["performance"]["p99_presentation_ms"]:
                raise GateError(f"benchmark p99 presentation time exceeds target: {path}")
            if metrics["late_prepared_percent"] > targets["performance"]["max_late_prepared_percent"]:
                raise GateError(f"benchmark late-prepared rate exceeds target: {path}")
        elif evidence_id in {"physical-matrix", "controller-multiplayer-matrix"}:
            coverage = artifact.get("coverage")
            if not isinstance(coverage, dict):
                raise GateError(f"physical artifact has no coverage object: {path}")
            for field, required in matrix["scope"].items():
                if field == "physical_output":
                    continue
                observed = coverage.get(field)
                if not isinstance(observed, list) or any(value not in observed for value in required):
                    raise GateError(f"physical artifact does not cover scope.{field}: {path}")
            validate_output_mode_qualification(artifact.get("output_mode_qualification"), matrix["scope"],
                                               "physical artifact")
        elif evidence_id == "timing-report":
            if artifact.get("all_corners") is not True or artifact.get("unconstrained_endpoints") != 0:
                raise GateError(f"timing artifact does not prove all-corner constrained timing: {path}")
        elif evidence_id == "inventory":
            if artifact.get("private_inputs_excluded") is not True or not isinstance(artifact.get("source_files"), list):
                raise GateError(f"inventory artifact lacks source/private-input disposition: {path}")
        elif evidence_id == "snapshot-build":
            if artifact.get("reproducible") is not True or not isinstance(artifact.get("tools"), dict) or not artifact["tools"]:
                raise GateError(f"snapshot-build artifact lacks reproducibility/tool evidence: {path}")
        elif evidence_id == "package-manifest":
            if artifact.get("private_data_excluded") is not True or not isinstance(artifact.get("files"), list) or not artifact["files"]:
                raise GateError(f"package artifact lacks allowlisted files/private-data disposition: {path}")
    except GateError as error:
        return [str(error)]
    return []


def evaluate(root: Path, matrix: dict[str, Any], record: dict[str, Any], expected_source: str | None,
             expected_candidate: str | None) -> dict[str, Any]:
    problems = validate_matrix(root, matrix)
    if record.get("schema") != RECORD_SCHEMA:
        problems.append("unsupported closure record schema")
    if record.get("matrix_sha256") != matrix_digest(matrix):
        problems.append("closure record was made for a different gate matrix")
    source_id = record.get("source_id")
    if not valid_identity(source_id):
        problems.append("closure record requires a 64-hex source_id")
    candidate_id = record.get("candidate_id")
    if not valid_identity(candidate_id):
        problems.append("closure record requires a non-null 64-hex candidate_id for release evaluation")
    manifest_source_id = record.get("manifest_source_id")
    if manifest_source_id is not None and not valid_identity(manifest_source_id):
        problems.append("closure record manifest_source_id must be a 64-hex identity")
    if expected_source is not None and source_id != expected_source:
        problems.append("closure record source_id does not match the expected current source")
    if expected_candidate is not None and record.get("candidate_id") != expected_candidate:
        problems.append("closure record candidate_id does not match the expected candidate")
    records = record.get("items")
    if not isinstance(records, dict) or set(records) != set(ITEM_IDS):
        problems.append("closure record must contain C01 through C34 exactly once")
        records = {}
    per_item: dict[str, list[str]] = {}
    for item_id in ITEM_IDS:
        item_problems: list[str] = []
        entry = records.get(item_id)
        specification = matrix.get("items", {}).get(item_id, {})
        if not isinstance(entry, dict):
            item_problems.append("missing closure record")
        else:
            status = entry.get("status")
            if status not in VALID_STATES:
                item_problems.append("invalid closure status")
            elif status == "closed":
                for dependency in specification.get("dependencies", []):
                    dependent = records.get(dependency)
                    if not isinstance(dependent, dict) or dependent.get("status") not in {"closed", "waived"}:
                        item_problems.append(f"dependency {dependency} is not closed")
                supplied = entry.get("evidence")
                if not isinstance(supplied, list):
                    item_problems.append("closed item has no evidence list")
                    supplied = []
                by_id: dict[str, dict[str, Any]] = {}
                required_ids = {requirement.get("id") for requirement in specification.get("evidence", [])}
                for value in supplied:
                    if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not value["id"]:
                        item_problems.append("closed item has an invalid evidence entry")
                        continue
                    evidence_id = value["id"]
                    if evidence_id in by_id:
                        item_problems.append(f"duplicate evidence id {evidence_id}")
                    by_id[evidence_id] = value
                for supplied_id in set(by_id) - required_ids:
                    item_problems.append(f"unexpected evidence {supplied_id}")
                for requirement in specification.get("evidence", []):
                    evidence = by_id.get(requirement.get("id"))
                    if evidence is None:
                        item_problems.append(f"missing evidence {requirement.get('id')}")
                    elif evidence.get("kind") != requirement.get("kind"):
                        item_problems.append(f"wrong evidence kind for {requirement.get('id')}")
                    elif requirement.get("kind") == "receipt":
                        item_problems.extend(validate_receipt(root, evidence, requirement, record))
                    else:
                        item_problems.extend(validate_artifact(root, evidence, requirement, matrix, record))
            elif status == "waived":
                decision = entry.get("scope_decision")
                if not isinstance(decision, dict) or not all(isinstance(decision.get(field), str) and decision[field]
                                                            for field in ("id", "approved_by", "rationale")):
                    item_problems.append("waived item needs a named approval, approver and rationale")
            else:
                item_problems.append(f"status is {status}; release remains blocked")
        if item_problems:
            per_item[item_id] = item_problems
    problems.extend(f"{item_id}: {problem}" for item_id, values in per_item.items() for problem in values)
    return {"schema": "diablo-closure-gate-result-v1", "eligible": not problems, "matrix_sha256": matrix_digest(matrix),
            "problems": problems, "items": per_item}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--matrix", type=Path, default=Path("support/qualification/closure-gates.json"))
    parser.add_argument("--check", action="store_true", help="Check matrix structure and linked C-item headings.")
    parser.add_argument("--evaluate", type=Path, help="Evaluate a closure record against the matrix.")
    parser.add_argument("--expected-source-id", help="Reject evidence made for another source identity.")
    parser.add_argument("--expected-candidate-id", help="Reject evidence made for another candidate identity.")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        matrix_path = args.matrix if args.matrix.is_absolute() else root / args.matrix
        matrix = read_json(matrix_path)
        matrix_problems = validate_matrix(root, matrix)
        if args.evaluate is None:
            result: dict[str, Any] = {"ok": not matrix_problems, "matrix_sha256": matrix_digest(matrix), "problems": matrix_problems}
        else:
            record_path = args.evaluate if args.evaluate.is_absolute() else root / args.evaluate
            result = evaluate(root, matrix, read_json(record_path), args.expected_source_id, args.expected_candidate_id)
            result["ok"] = result["eligible"]
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    except GateError as error:
        print(json.dumps({"ok": False, "problems": [str(error)]}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

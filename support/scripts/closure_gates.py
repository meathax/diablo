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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MATRIX_SCHEMA = "diablo-closure-gate-matrix-v1"
RECORD_SCHEMA = "diablo-closure-record-v1"
RECEIPT_SCHEMA = "diablo-verification-receipt-v1"
ITEM_IDS = tuple(f"C{number:02d}" for number in range(1, 35))
VALID_STATES = {"open", "in_progress", "blocked", "closed", "waived"}
VALID_EVIDENCE_KINDS = {"receipt", "artifact"}


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
        if expected_candidate is not None and candidate.get("candidate_id") != expected_candidate:
            raise GateError(f"receipt candidate identity differs from closure record: {path}")
    except GateError as error:
        problems.append(str(error))
    return problems


def validate_artifact(root: Path, evidence: dict[str, Any]) -> list[str]:
    try:
        path = relative_path(root, evidence.get("path"), "artifact evidence path")
        if not path.is_file():
            raise GateError(f"artifact is missing: {path}")
        if evidence.get("sha256") != sha256_file(path):
            raise GateError(f"artifact hash does not match evidence record: {path}")
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
    if not isinstance(source_id, str) or not source_id:
        problems.append("closure record requires a source_id")
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
                by_id = {value.get("id"): value for value in supplied if isinstance(value, dict) and isinstance(value.get("id"), str)}
                for requirement in specification.get("evidence", []):
                    evidence = by_id.get(requirement.get("id"))
                    if evidence is None:
                        item_problems.append(f"missing evidence {requirement.get('id')}")
                    elif evidence.get("kind") != requirement.get("kind"):
                        item_problems.append(f"wrong evidence kind for {requirement.get('id')}")
                    elif requirement.get("kind") == "receipt":
                        item_problems.extend(validate_receipt(root, evidence, requirement, record))
                    else:
                        item_problems.extend(validate_artifact(root, evidence))
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

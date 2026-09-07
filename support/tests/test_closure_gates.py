from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from support.scripts import closure_gates


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class ClosureGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        plan = self.root / "plan.md"
        plan.write_text("\n".join(f"### C{index:02d} — test" for index in range(1, 35)) + "\n", encoding="utf-8")
        self.matrix = json.loads((Path(__file__).resolve().parents[1] / "qualification" / "closure-gates.json").read_text(encoding="utf-8"))
        self.matrix["plan"]["path"] = "plan.md"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def passing_record(self) -> dict[str, object]:
        source_id = "source-for-test"
        receipts: dict[str, Path] = {}
        record: dict[str, object] = {
            "schema": closure_gates.RECORD_SCHEMA,
            "matrix_sha256": closure_gates.matrix_digest(self.matrix),
            "source_id": source_id,
            "items": {},
        }
        for item_id, specification in self.matrix["items"].items():
            evidence = []
            for requirement in specification["evidence"]:
                if requirement["kind"] == "receipt":
                    suite = requirement["suite"]
                    path = receipts.get(suite)
                    if path is None:
                        path = self.root / "receipts" / f"{suite}.json"
                        write_json(path, {"schema": closure_gates.RECEIPT_SCHEMA, "suite": suite, "status": "pass",
                                          "candidate": {"source_id": source_id, "candidate_id": None}})
                        receipts[suite] = path
                else:
                    path = self.root / "artifacts" / f"{item_id}-{requirement['id']}.txt"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"{item_id}:{requirement['id']}\n", encoding="utf-8")
                evidence.append({"id": requirement["id"], "kind": requirement["kind"],
                                 "path": path.relative_to(self.root).as_posix(),
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            record["items"][item_id] = {"status": "closed", "evidence": evidence}
        return record

    def test_matrix_covers_plan_and_declares_targets(self) -> None:
        self.assertEqual([], closure_gates.validate_matrix(self.root, self.matrix))

    def test_complete_synthetic_fixture_is_eligible(self) -> None:
        result = closure_gates.evaluate(self.root, self.matrix, self.passing_record(), "source-for-test", None)
        self.assertTrue(result["eligible"], result["problems"])

    def test_open_item_cannot_be_promoted(self) -> None:
        record = self.passing_record()
        record["items"]["C23"] = {"status": "blocked"}
        result = closure_gates.evaluate(self.root, self.matrix, record, "source-for-test", None)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("C23: status is blocked" in problem for problem in result["problems"]))

    def test_changed_source_identity_invalidates_evidence(self) -> None:
        result = closure_gates.evaluate(self.root, self.matrix, self.passing_record(), "changed-source", None)
        self.assertFalse(result["eligible"])
        self.assertIn("closure record source_id does not match the expected current source", result["problems"])

    def test_tampered_receipt_is_rejected(self) -> None:
        record = self.passing_record()
        receipt = self.root / record["items"]["C01"]["evidence"][0]["path"]
        receipt.write_text("{}\n", encoding="utf-8")
        result = closure_gates.evaluate(self.root, self.matrix, record, "source-for-test", None)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("receipt hash does not match" in problem for problem in result["problems"]))

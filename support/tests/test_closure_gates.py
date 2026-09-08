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
        source_id = "a" * 64
        candidate_id = "b" * 64
        receipts: dict[str, Path] = {}
        record: dict[str, object] = {
            "schema": closure_gates.RECORD_SCHEMA,
            "matrix_sha256": closure_gates.matrix_digest(self.matrix),
            "source_id": source_id,
            "candidate_id": candidate_id,
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
                        log = self.root / "logs" / f"{suite}.log"
                        log.parent.mkdir(parents=True, exist_ok=True)
                        log.write_text(f"{suite}: pass\n", encoding="utf-8")
                        write_json(path, {"schema": closure_gates.RECEIPT_SCHEMA, "suite": suite, "status": "pass",
                                          "candidate": {"source_id": source_id, "candidate_id": candidate_id},
                                          "results": [{"id": suite, "status": "pass", "log": log.relative_to(self.root).as_posix(),
                                                       "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                                                       "log_bytes": log.stat().st_size}]} )
                        receipts[suite] = path
                else:
                    path = self.root / "artifacts" / f"{item_id}-{requirement['id']}.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    evidence_id = requirement["id"]
                    artifact: dict[str, object] = {
                        "schema": closure_gates.ARTIFACT_SCHEMAS[evidence_id],
                        "status": "pass", "source_id": source_id, "candidate_id": candidate_id,
                    }
                    if evidence_id == "candidate-manifest":
                        artifact.update({"inputs": {"source_files": [{"path": "source", "bytes": 1, "sha256": "0" * 64}]},
                                         "artifacts": [{"path": "artifact", "bytes": 1, "sha256": "1" * 64}]})
                    elif evidence_id == "benchmark-analysis":
                        artifact.update({"metrics": {"fps": 60, "p99_presentation_ms": 16.0, "late_prepared_percent": 0.0},
                                         "runs": [{"id": "run-1"}, {"id": "run-2"}, {"id": "run-3"}]})
                    elif evidence_id in {"physical-matrix", "controller-multiplayer-matrix"}:
                        artifact["coverage"] = self.matrix["scope"]
                    elif evidence_id == "timing-report":
                        artifact.update({"all_corners": True, "unconstrained_endpoints": 0})
                    elif evidence_id == "inventory":
                        artifact.update({"private_inputs_excluded": True, "source_files": ["rtl/example.sv"]})
                    elif evidence_id == "snapshot-build":
                        artifact.update({"reproducible": True, "tools": {"quartus": "17"}})
                    elif evidence_id == "package-manifest":
                        artifact.update({"private_data_excluded": True, "files": [{"path": "Diablo.rbf"}]})
                    write_json(path, artifact)
                evidence.append({"id": requirement["id"], "kind": requirement["kind"],
                                 "path": path.relative_to(self.root).as_posix(),
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            record["items"][item_id] = {"status": "closed", "evidence": evidence}
        return record

    def test_matrix_covers_plan_and_declares_targets(self) -> None:
        self.assertEqual([], closure_gates.validate_matrix(self.root, self.matrix))

    def test_output_rows_cannot_collapse_to_generic_video_claim(self) -> None:
        self.matrix["scope"]["output_modes"] = ["native video", "framebuffer"]
        problems = closure_gates.validate_matrix(self.root, self.matrix)
        self.assertTrue(any("scope.output_modes must enumerate" in problem for problem in problems))

    def test_complete_synthetic_fixture_is_eligible(self) -> None:
        result = closure_gates.evaluate(self.root, self.matrix, self.passing_record(), "a" * 64, "b" * 64)
        self.assertTrue(result["eligible"], result["problems"])

    def test_open_item_cannot_be_promoted(self) -> None:
        record = self.passing_record()
        record["items"]["C23"] = {"status": "blocked"}
        result = closure_gates.evaluate(self.root, self.matrix, record, "a" * 64, "b" * 64)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("C23: status is blocked" in problem for problem in result["problems"]))

    def test_changed_source_identity_invalidates_evidence(self) -> None:
        result = closure_gates.evaluate(self.root, self.matrix, self.passing_record(), "c" * 64, "b" * 64)
        self.assertFalse(result["eligible"])
        self.assertIn("closure record source_id does not match the expected current source", result["problems"])

    def test_tampered_receipt_is_rejected(self) -> None:
        record = self.passing_record()
        receipt = self.root / record["items"]["C01"]["evidence"][0]["path"]
        receipt.write_text("{}\n", encoding="utf-8")
        result = closure_gates.evaluate(self.root, self.matrix, record, "a" * 64, "b" * 64)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("receipt hash does not match" in problem for problem in result["problems"]))

    def test_failing_result_is_rejected_even_with_valid_hash(self) -> None:
        record = self.passing_record()
        receipt = self.root / record["items"]["C01"]["evidence"][0]["path"]
        value = json.loads(receipt.read_text(encoding="utf-8"))
        value["results"][0]["status"] = "fail"
        write_json(receipt, value)
        record["items"]["C01"]["evidence"][0]["sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
        result = closure_gates.evaluate(self.root, self.matrix, record, "a" * 64, "b" * 64)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("is not pass" in problem for problem in result["problems"]))

    def test_bad_benchmark_is_rejected_even_with_valid_hash(self) -> None:
        record = self.passing_record()
        evidence = record["items"]["C21"]["evidence"][0]
        artifact = self.root / evidence["path"]
        value = json.loads(artifact.read_text(encoding="utf-8"))
        value["metrics"]["fps"] = 1
        write_json(artifact, value)
        evidence["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        result = closure_gates.evaluate(self.root, self.matrix, record, "a" * 64, "b" * 64)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("FPS is below target" in problem for problem in result["problems"]))

    def test_duplicate_evidence_is_rejected(self) -> None:
        record = self.passing_record()
        evidence = record["items"]["C18"]["evidence"][0]
        record["items"]["C18"]["evidence"].append(dict(evidence))
        result = closure_gates.evaluate(self.root, self.matrix, record, "a" * 64, "b" * 64)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("duplicate evidence id" in problem for problem in result["problems"]))

    def test_null_candidate_is_rejected(self) -> None:
        record = self.passing_record()
        record["candidate_id"] = None
        result = closure_gates.evaluate(self.root, self.matrix, record, "a" * 64, None)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("non-null 64-hex candidate_id" in problem for problem in result["problems"]))

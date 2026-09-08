import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "verification.py"
SPEC = importlib.util.spec_from_file_location("verification", SCRIPT)
verification = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = verification
SPEC.loader.exec_module(verification)


class VerificationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_receipt_publication_is_immutable(self):
        path = self.root / "receipts" / "run.json"
        receipt = {"schema": verification.SCHEMA, "run_id": "test"}
        verification.write_receipt(path, receipt)
        original = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "refusing to overwrite immutable receipt"):
            verification.write_receipt(path, receipt)
        self.assertEqual(path.read_bytes(), original)

    def test_failed_command_preserves_bounded_log(self):
        step = verification.Step("failing", ((sys.executable, "-c", "print('expected failure'); raise SystemExit(7)"),),
                                 timeout_seconds=10)
        result = verification.record_step(step, self.root, self.root / "logs")
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["exit_code"], 7)
        log = self.root / result["log"]
        self.assertIn("expected failure", log.read_text(encoding="utf-8"))

    def test_mutating_step_invalidates_isolated_source_snapshot(self):
        input_path = self.root / "input.txt"
        input_path.write_text("before", encoding="utf-8")
        step = verification.Step(
            "mutating", ((sys.executable, "-c", "from pathlib import Path; Path('input.txt').write_text('after')"),),
            timeout_seconds=10,
        )
        with patch.object(verification, "DEPENDENCY_INPUTS", ("input.txt",)), \
             patch.object(verification, "selected_steps", return_value=([step], [])):
            code, receipt, _ = verification.run(self.root, "foundation", None, None)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any(item.get("id") == "source-integrity" and item.get("status") == "fail"
                            for item in receipt["results"]))
        self.assertEqual(input_path.read_text(encoding="utf-8"), "before")

    def test_board_fallback_explains_configuration_path(self):
        steps, pending = verification.selected_steps(self.root, "board")
        self.assertEqual(steps, [])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["status"], "not_run")
        self.assertIn("--board-configuration", pending[0]["reason"])
        self.assertIn("board_runner.py", pending[0]["reason"])


if __name__ == "__main__":
    unittest.main()

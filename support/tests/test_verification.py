import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from support.scripts import board_runner


class BoardRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidate = "a" * 64
        self.source = "b" * 64
        observations = {
            name: {"status": "pass", "candidate_id": self.candidate, "method": "test-fixture",
                   "evidence": [f"{name}.json"]}
            for name in board_runner.REQUIRED_OBSERVATIONS
        }
        self.config = self.root / "board.json"
        self.config.write_text(json.dumps({
            "schema": board_runner.SCHEMA, "status": "pass", "candidate_id": self.candidate,
            "source_id": self.source, "target": {"name": "fixture-board"},
            "commands": [{"id": "probe", "argv": [sys.executable, "-c", "print('board ok')"]}],
            "observations": observations,
        }), encoding="utf-8")
        self.addCleanup(self.temporary.cleanup)

    def test_candidate_bound_profile_runs_without_shell(self) -> None:
        result = board_runner.run_configuration(self.root, self.config, self.candidate, self.source,
                                                self.root / "logs" / "board.log")
        self.assertEqual("pass", result["status"])
        self.assertEqual(0, result["commands"][0]["exit_code"])
        self.assertIn("board ok", (self.root / result["log"]).read_text(encoding="utf-8"))

    def test_missing_observation_blocks_execution(self) -> None:
        value = json.loads(self.config.read_text(encoding="utf-8"))
        del value["observations"]["audio"]
        self.config.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "physical observation audio"):
            board_runner.run_configuration(self.root, self.config, self.candidate, self.source,
                                           self.root / "logs" / "board.log")

    def test_command_failure_is_recorded(self) -> None:
        value = json.loads(self.config.read_text(encoding="utf-8"))
        value["commands"][0]["argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
        self.config.write_text(json.dumps(value), encoding="utf-8")
        result = board_runner.run_configuration(self.root, self.config, self.candidate, self.source,
                                                self.root / "logs" / "board.log")
        self.assertEqual("fail", result["status"])
        self.assertEqual(7, result["commands"][0]["exit_code"])

    def test_cli_publishes_immutable_result(self) -> None:
        output = self.root / "receipts" / "board.json"
        code = board_runner.main([
            "--root", str(self.root), "--configuration", "board.json",
            "--candidate-id", self.candidate, "--source-id", self.source,
            "--log", "logs/cli.log", "--output", str(output),
        ])
        self.assertEqual(0, code)
        value = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(board_runner.SCHEMA, value["schema"])
        self.assertEqual("pass", value["status"])
        self.assertEqual(1, board_runner.main([
            "--root", str(self.root), "--configuration", "board.json",
            "--candidate-id", self.candidate, "--source-id", self.source,
            "--log", "logs/cli-second.log", "--output", str(output),
        ]))


if __name__ == "__main__":
    unittest.main()

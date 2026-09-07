from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from support.scripts import guide_status


class GuideStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        plan = self.root / guide_status.PLAN
        plan.parent.mkdir(parents=True)
        plan.write_text("# plan\n", encoding="utf-8")
        (self.root / "README.md").write_text("[plan](reports/audit-2026-09-07/PROPOSED_PLAN.md) [.mister/state.json](.mister/state.json) accepted\n", encoding="utf-8")
        (self.root / "CORE_COMPLETION_AUDIT.md").write_text("[plan](reports/audit-2026-09-07/PROPOSED_PLAN.md) [.mister/state.json](.mister/state.json)\n", encoding="utf-8")
        arm = self.root / "support/ARM_RUNTIME.md"
        arm.parent.mkdir(parents=True)
        arm.write_text("[plan](../reports/audit-2026-09-07/PROPOSED_PLAN.md) diablo_launch.py DIABLO_MISTER_ADMISSION_FILE\n", encoding="utf-8")
        self.state = self.root / guide_status.STATE
        self.state.parent.mkdir(parents=True)
        self.write_state()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_state(self) -> None:
        plan = self.root / guide_status.PLAN
        self.state.write_text(json.dumps({"schema": "diablo-project-state-v2", "completion_document": guide_status.PLAN.as_posix(),
                                          "completion_document_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
                                          "next_action": "Build the current candidate.",
                                          "candidate": {"state": "no-current-accepted-candidate", "id": None},
                                          "accepted_build_id": None}), encoding="utf-8")

    def test_consistent_guides_pass(self) -> None:
        self.assertTrue(guide_status.validate(self.root)["ok"])

    def test_stale_plan_digest_fails(self) -> None:
        data = json.loads(self.state.read_text(encoding="utf-8"))
        data["completion_document_sha256"] = "0" * 64
        self.state.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("state completion_document_sha256 is stale", guide_status.validate(self.root)["problems"])

    def test_broken_link_and_prose_command_fail(self) -> None:
        (self.root / "README.md").write_text("[missing](missing.md) accepted\n", encoding="utf-8")
        data = json.loads(self.state.read_text(encoding="utf-8"))
        data["next_exact_command"] = "This is not a command"
        self.state.write_text(json.dumps(data), encoding="utf-8")
        problems = guide_status.validate(self.root)["problems"]
        self.assertTrue(any("broken local link" in problem for problem in problems))
        self.assertIn("state labels prose as next_exact_command; use next_action or an executable command", problems)

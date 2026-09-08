from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from support.scripts import deploy_package, package_release


class DeployPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = self.root / "source"
        source.mkdir()
        for name, content in (("engine.bin", b"engine"), ("core.rbf", b"rbf"),
                              ("abi.hex", b"abi"), ("launcher.py", b"launcher")):
            (source / name).write_bytes(content)
        (self.root / "assets" / "ui").mkdir(parents=True)
        (self.root / "assets" / "ui" / "font.dat").write_bytes(b"font")
        records = [{"path": f"source/{name}", "sha256": hashlib.sha256(content).hexdigest()}
                   for name, content in (("engine.bin", b"engine"), ("core.rbf", b"rbf"),
                                         ("abi.hex", b"abi"), ("launcher.py", b"launcher"))]
        records.append({"path": "assets/ui/font.dat", "sha256": hashlib.sha256(b"font").hexdigest()})
        self.candidate = self.root / "candidate.json"
        self.candidate.write_text(json.dumps({
            "schema": "diablo-candidate-manifest-v1", "status": "pass",
            "candidate_id": "a" * 64, "source_id": "b" * 64, "artifacts": records,
        }) + "\n", encoding="utf-8")
        self.board = "de10-nano-test"
        self.addCleanup(self.temporary.cleanup)

    def make_package(self, output: Path, candidate: Path | None = None) -> Path:
        with mock.patch.object(package_release.candidate_manifest, "verify_manifest", return_value=[]):
            package_release.create_package(
                self.root, candidate or self.candidate,
                (("engine", "source/engine.bin"), ("rbf", "source/core.rbf"),
                 ("abi", "source/abi.hex"), ("launcher", "source/launcher.py")),
                self.board, output, "assets")
        return output

    def test_install_preserves_user_data_and_second_install_is_idempotent(self) -> None:
        package = self.make_package(self.root / "package")
        target = self.root / "target"
        (target / "saves").mkdir(parents=True)
        (target / "saves" / "diablo.sav").write_bytes(b"user save")
        first = deploy_package.install_package(package, target, self.board)
        second = deploy_package.install_package(package, target, self.board)
        self.assertEqual(first["active_candidate_id"], second["active_candidate_id"])
        self.assertEqual(b"user save", (target / "saves" / "diablo.sav").read_bytes())
        self.assertTrue(deploy_package.verify_installation(target, self.board)["ok"])
        self.assertTrue((target / "saves").is_dir())

    def test_interrupted_update_leaves_previous_activation_untouched(self) -> None:
        package = self.make_package(self.root / "package")
        target = self.root / "target"
        before = deploy_package.install_package(package, target, self.board)
        candidate2 = self.root / "candidate2.json"
        value = json.loads(self.candidate.read_text(encoding="utf-8"))
        value["candidate_id"] = "c" * 64
        candidate2.write_text(json.dumps(value) + "\n", encoding="utf-8")
        package2 = self.make_package(self.root / "package2", candidate2)
        with self.assertRaises(deploy_package.InstallError):
            deploy_package.install_package(package2, target, self.board, fail_after=2)
        after = deploy_package.verify_installation(target, self.board)["state"]
        self.assertEqual(before["active_release"], after["active_release"])
        self.assertEqual([], list((target / deploy_package.STAGING_DIRNAME).iterdir()))

    def test_update_and_rollback_switch_only_activation_record(self) -> None:
        package1 = self.make_package(self.root / "package1")
        first = deploy_package.install_package(package1, self.root / "target", self.board)
        candidate2 = self.root / "candidate2.json"
        value = json.loads(self.candidate.read_text(encoding="utf-8"))
        value["candidate_id"] = "c" * 64
        candidate2.write_text(json.dumps(value) + "\n", encoding="utf-8")
        package2 = self.make_package(self.root / "package2", candidate2)
        updated = deploy_package.install_package(package2, self.root / "target", self.board)
        self.assertNotEqual(first["active_candidate_id"], updated["active_candidate_id"])
        rolled = deploy_package.rollback_installation(self.root / "target", self.board)
        self.assertEqual(first["active_candidate_id"], rolled["active_candidate_id"])
        self.assertTrue(deploy_package.verify_installation(self.root / "target", self.board)["ok"])

    def test_tampered_active_release_is_rejected(self) -> None:
        package = self.make_package(self.root / "package")
        target = self.root / "target"
        deploy_package.install_package(package, target, self.board)
        state = json.loads((target / deploy_package.STATE_FILENAME).read_text(encoding="utf-8"))
        release = target / state["active_release"]
        (release / "NOTICE.txt").write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(deploy_package.InstallError):
            deploy_package.verify_installation(target, self.board)


if __name__ == "__main__":
    unittest.main()

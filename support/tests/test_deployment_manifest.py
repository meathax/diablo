from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from support.scripts import deployment_manifest, diablo_launch


class DeploymentManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        (self.data / "DIABDAT.MPQ").write_bytes(b"private data is supplied separately")
        (self.root / "Diablo.rbf").write_bytes(b"rbf")
        (self.root / "devilutionx").write_bytes(b"engine")
        (self.root / "transport-abi.json").write_text('{"abi":"test"}\n', encoding="utf-8")
        self.manifest = self.root / "deployment.json"
        deployment_manifest.write_manifest(self.manifest, deployment_manifest.make_manifest(
            self.root, "a" * 64, "b" * 64, "c" * 64, "de10-nano", (
                ("rbf", "Diablo.rbf"), ("engine", "devilutionx"), ("abi", "transport-abi.json"))))
        self.boot = self.root / "boot-id"
        self.boot.write_text("12345678-1234-1234-1234-123456789abc\n", encoding="utf-8")
        self.addCleanup(self.temporary.cleanup)

    def test_runtime_only_manifest_verifies_without_git_checkout(self) -> None:
        self.assertEqual([], deployment_manifest.verify_manifest(self.root, self.manifest, "de10-nano"))
        context = diablo_launch.preflight(
            self.root, None, self.root / "Diablo.rbf", self.root / "devilutionx", "diablo", self.data,
            self.root / "saves", self.root / "runtime", self.boot, "0x3fe00000", Path("transport.lock"),
            self.manifest, "de10-nano")
        self.assertEqual("a" * 64, context.candidate_id)
        self.assertEqual("b" * 64, context.source_id)

    def test_runtime_artifact_mutation_is_rejected(self) -> None:
        (self.root / "devilutionx").write_bytes(b"changed")
        problems = deployment_manifest.verify_manifest(self.root, self.manifest, "de10-nano")
        self.assertTrue(any("hash mismatch" in problem for problem in problems))

    def test_private_data_flag_is_required(self) -> None:
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["private_data_excluded"] = False
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        problems = deployment_manifest.verify_manifest(self.root, self.manifest, "de10-nano")
        self.assertIn("deployment manifest does not declare private data exclusion", problems)


if __name__ == "__main__":
    unittest.main()

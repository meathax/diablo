from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from support.scripts import diablo_launch, mister_launcher, package_release


class PackageReleaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "source").mkdir()
        for name, content in (("engine.bin", b"engine"), ("core.rbf", b"rbf"), ("abi.hex", b"abi"),
                              ("launcher.py", b"launcher")):
            (self.root / "source" / name).write_bytes(content)
        (self.root / "assets" / "ui_art").mkdir(parents=True)
        (self.root / "assets" / "ui_art" / "diablo.pal").write_bytes(b"palette")
        (self.root / "source" / "unlisted.bin").write_bytes(b"unlisted")
        artifact_records = [
            {"path": "source/engine.bin", "sha256": hashlib.sha256(b"engine").hexdigest()},
            {"path": "source/core.rbf", "sha256": hashlib.sha256(b"rbf").hexdigest()},
            {"path": "source/abi.hex", "sha256": hashlib.sha256(b"abi").hexdigest()},
            {"path": "source/launcher.py", "sha256": hashlib.sha256(b"launcher").hexdigest()},
            {"path": "assets/ui_art/diablo.pal", "sha256": hashlib.sha256(b"palette").hexdigest()},
        ]
        self.candidate = self.root / "candidate.json"
        self.candidate.write_text(json.dumps({
            "schema": "diablo-candidate-manifest-v1",
            "status": "pass",
            "candidate_id": "a" * 64,
            "source_id": "b" * 64,
            "artifacts": artifact_records,
        }) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create(self) -> Path:
        output = self.root / "package"
        with mock.patch.object(package_release.candidate_manifest, "verify_manifest", return_value=[]):
            result = package_release.create_package(
                self.root,
                self.candidate,
                (("engine", "source/engine.bin"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                 ("launcher", "source/launcher.py")),
                "de10-nano-test",
                output,
                "assets",
            )
        self.assertEqual(str(output.resolve()), result["package"])
        return output

    def test_create_and_verify_runtime_only_package(self) -> None:
        package = self.create()
        self.assertEqual([], package_release.verify_package(package, "de10-nano-test"))
        self.assertEqual("a" * 64, mister_launcher.verify_package(package)["candidate_id"])
        self.assertEqual(
            {"devilutionx", "Diablo.rbf", "transport_abi.hex", "diablo_launcher.py", "deployment.json",
             "package-manifest.json", "NOTICE.txt", "SETUP.md", "assets"},
            {path.name for path in package.iterdir()},
        )
        self.assertIn("licensed Diablo and", (package / "NOTICE.txt").read_text(encoding="utf-8"))
        self.assertIn("update is interrupted", (package / "SETUP.md").read_text(encoding="utf-8"))

    def test_clean_package_supports_launcher_preflight(self) -> None:
        package = self.create()
        data = self.root / "data"
        data.mkdir()
        (data / "DIABDAT.MPQ").write_bytes(b"supplied privately")
        boot = self.root / "boot-id"
        boot.write_text("12345678-1234-1234-1234-123456789abc\n", encoding="utf-8")
        context = diablo_launch.preflight(
            package,
            None,
            package / "Diablo.rbf",
            package / "devilutionx",
            "diablo",
            data,
            self.root / "saves",
            self.root / "runtime",
            boot,
            "0x3fe00000",
            Path("transport.lock"),
            package / "deployment.json",
            "de10-nano-test",
        )
        self.assertEqual("a" * 64, context.candidate_id)
        self.assertEqual("b" * 64, context.source_id)

    def test_timedemo_requests_bounded_target_frame_pacing(self) -> None:
        self.assertTrue(mister_launcher._force_frame_pacing(["--spawn", "--timedemo"]))
        self.assertFalse(mister_launcher._force_frame_pacing(["--spawn", "--demo", "0"]))

    def test_mutation_and_private_file_are_rejected(self) -> None:
        package = self.create()
        (package / "Diablo.rbf").write_bytes(b"changed")
        problems = package_release.verify_package(package, "de10-nano-test")
        self.assertTrue(any("hash" in problem for problem in problems), problems)
        (package / "private.sav").write_bytes(b"private")
        problems = package_release.verify_package(package, "de10-nano-test")
        self.assertTrue(any("unexpected files" in problem for problem in problems), problems)
        self.assertTrue(any("private-data" in problem for problem in problems), problems)

    def test_existing_output_is_never_overwritten(self) -> None:
        package = self.create()
        with mock.patch.object(package_release.candidate_manifest, "verify_manifest", return_value=[]):
            with self.assertRaises(ValueError):
                package_release.create_package(
                    self.root,
                    self.candidate,
                    (("engine", "source/engine.bin"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                     ("launcher", "source/launcher.py")),
                    "de10-nano-test",
                    package,
                    "assets",
                )

    def test_non_candidate_or_private_source_cannot_be_packaged(self) -> None:
        private = self.root / "game"
        private.mkdir()
        (private / "secret.mpq").write_bytes(b"private")
        with mock.patch.object(package_release.candidate_manifest, "verify_manifest", return_value=[]):
            with self.assertRaises(ValueError):
                package_release.create_package(
                    self.root,
                    self.candidate,
                    (("engine", "game/secret.mpq"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                     ("launcher", "source/launcher.py")),
                    "de10-nano-test",
                    self.root / "private-package",
                    "assets",
                )
            with self.assertRaises(ValueError):
                package_release.create_package(
                    self.root,
                    self.candidate,
                    (("engine", "source/unlisted.bin"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                     ("launcher", "source/launcher.py")),
                    "de10-nano-test",
                    self.root / "mismatched-package",
                    "assets",
                )


if __name__ == "__main__":
    unittest.main()

"""Negative-admission tests use synthetic data; no commercial assets as fixtures."""
import importlib.util
import argparse
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("diablo", Path(__file__).parents[1] / "scripts/diablo.py")
diablo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diablo)


class MpqBoundsTests(unittest.TestCase):
    def probe(self, **changes):
        fields = dict(magic=b"MPQ\x1a", header=32, size=64, version=0, shift=3,
                      hashes=32, blocks=48, nhash=1, nblock=1)
        fields.update(changes)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.mpq"
            path.write_bytes(struct.pack("<4sIIHHIIII", *fields.values()) + bytes(32))
            return diablo.inspect_mpq(path)

    def test_valid_minimal_table_extents(self):
        self.assertEqual(self.probe()["structural_bounds"], "pass")

    def test_rejects_table_outside_archive(self):
        with self.assertRaises(diablo.GateError):
            self.probe(nblock=2)

    def test_rejects_declared_size_larger_than_file(self):
        with self.assertRaises(diablo.GateError):
            self.probe(size=65)

    def test_rejects_unknown_version_instead_of_assuming_v0(self):
        with self.assertRaises(diablo.GateError):
            self.probe(version=1)

    def test_rejects_missing_signature(self):
        with self.assertRaises(diablo.GateError):
            self.probe(magic=b"FAIL")

    def test_lock_has_only_immutable_source_commits(self):
        lock = diablo.load_lock()
        self.assertGreaterEqual(len(lock["sources"]), 7)
        self.assertEqual("1.5.5", lock["sources"]["devilutionx"]["release"])
        self.assertEqual("7223eeac9e8274fbf665b4de86fda26d3b22c52f",
                         lock["sources"]["devilutionx"]["commit"])


class PrivateDataTests(unittest.TestCase):
    def test_identity_change_is_rejected_without_replacing_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / "game").mkdir()
            asset = root / "game/test.mpq"
            original = struct.pack("<4sIIHHIIII", b"MPQ\x1a", 32, 64, 0, 3, 32, 48, 1, 1) + bytes(32)
            asset.write_bytes(original)
            with patch.object(diablo, "ROOT", root), patch.object(diablo, "DATA_FILES", {"test.mpq": 64}):
                diablo.verify_data(None)
                manifest = root / ".mister/evidence/private/game-data.json"
                identity = manifest.read_bytes()
                self.assertEqual(asset.read_bytes(), original)
                diablo.verify_data(None)
                asset.write_bytes(original[:-1] + b"X")
                with self.assertRaises(diablo.GateError):
                    diablo.verify_data(None)
                self.assertEqual(manifest.read_bytes(), identity)


class SourceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)
        diablo.git(self.path, "init")
        diablo.git(self.path, "config", "user.name", "Synthetic Test")
        diablo.git(self.path, "config", "user.email", "fixture@example.invalid")
        (self.path / "fixture.txt").write_text("fixture\n")
        diablo.git(self.path, "add", "fixture.txt")
        diablo.git(self.path, "commit", "-m", "synthetic fixture")
        self.source = {"commit": diablo.git(self.path, "rev-parse", "HEAD"),
                       "url": "https://github.com/example/fixture.git"}
        diablo.git(self.path, "remote", "add", "origin", self.source["url"])

    def test_accepts_clean_exact_identity(self):
        self.assertTrue(diablo.inspect_source(self.path, self.source)["clean"])

    def test_rejects_modified_tracked_file(self):
        (self.path / "fixture.txt").write_text("changed\n")
        with self.assertRaises(diablo.GateError):
            diablo.inspect_source(self.path, self.source)

    def test_rejects_untracked_file(self):
        (self.path / "extra.txt").write_text("unknown\n")
        with self.assertRaises(diablo.GateError):
            diablo.inspect_source(self.path, self.source)

    def test_rejects_wrong_commit(self):
        with self.assertRaises(diablo.GateError):
            diablo.inspect_source(self.path, {**self.source, "commit": "0" * 40})

    def test_rejects_wrong_origin(self):
        diablo.git(self.path, "remote", "set-url", "origin", "https://github.com/example/other.git")
        with self.assertRaises(diablo.GateError):
            diablo.inspect_source(self.path, self.source)


class DoctorTests(unittest.TestCase):
    def test_inventory_does_not_require_or_execute_legacy_runner(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / "quartus/bin64/quartus_sh.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"synthetic executable; never execute")
            (root / "quartus/version.txt").write_text("Version=synthetic")
            with patch.object(diablo, "command", side_effect=AssertionError("No tool execution during inventory")):
                result = diablo.doctor(argparse.Namespace(quartus_root=root))
            self.assertEqual(result["status"], "preflight-only")
            self.assertEqual(result["quartus_blockers"], [])
            self.assertFalse(result["production_build_ready"])
            self.assertEqual(result["quartus_installation"]["executable_sha256"], diablo.sha256(executable))

    def test_missing_compiler_still_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            result = diablo.doctor(argparse.Namespace(quartus_root=Path(folder)))
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["quartus_blockers"], ["quartusInstallation"])


if __name__ == "__main__":
    unittest.main()

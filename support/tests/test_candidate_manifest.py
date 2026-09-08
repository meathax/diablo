import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "candidate_manifest.py"
SPEC = importlib.util.spec_from_file_location("candidate_manifest", SCRIPT)
candidate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(candidate)


class CandidateManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

        for input_name in candidate.SOURCE_INPUTS:
            path = self.root / input_name
            path.parent.mkdir(parents=True, exist_ok=True)
            if input_name in candidate.DIRECTORY_INPUTS:
                source = path / "source.txt"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(input_name, encoding="utf-8")
            else:
                path.write_text(input_name, encoding="utf-8")
        self.artifact = self.root / "output_files" / "Diablo.rbf"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_bytes(b"candidate-one")

    def test_git_identity_preserves_leading_porcelain_space(self):
        def fake_run(args, **_kwargs):
            if args[1:3] == ["status", "--porcelain=v1"]:
                return mock.Mock(returncode=0, stdout=" M .gitignore\\n", stderr="")
            return mock.Mock(returncode=0, stdout="head\\n", stderr="")

        with mock.patch.object(candidate.subprocess, "run", side_effect=fake_run):
            identity = candidate.git_identity(self.root, [".gitignore"])

        self.assertEqual(identity["status_porcelain_v1"], " M .gitignore")

    def test_source_and_artifact_changes_invalidate_identity(self):
        first = candidate.make_manifest(self.root, [self.artifact], {"quartus": "17.1"})
        tracked = self.root / "rtl" / "source.txt"
        tracked.write_text("changed", encoding="utf-8")
        second = candidate.make_manifest(self.root, [self.artifact], {"quartus": "17.1"})
        self.assertNotEqual(first["source_id"], second["source_id"])
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])
        self.artifact.write_bytes(b"candidate-two")
        third = candidate.make_manifest(self.root, [self.artifact], {"quartus": "17.1"})
        self.assertEqual(second["source_id"], third["source_id"])
        self.assertNotEqual(second["candidate_id"], third["candidate_id"])

    def test_interpreter_caches_are_excluded_from_source_identity(self):
        cache = self.root / "support" / "scripts" / "__pycache__"
        cache.mkdir()
        generated = cache / "candidate_manifest.cpython-314.pyc"
        generated.write_bytes(b"cache-one")
        first = candidate.make_manifest(self.root, [self.artifact])
        generated.write_bytes(b"cache-two")
        second = candidate.make_manifest(self.root, [self.artifact])
        self.assertEqual(first["source_id"], second["source_id"])
        self.assertFalse(any(record["path"].endswith(".pyc")
                             or "__pycache__" in record["path"]
                             for record in first["inputs"]["source_files"]))

    def test_verification_rejects_mutated_artifact(self):
        manifest = candidate.make_manifest(self.root, [self.artifact])
        path = self.root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(candidate.verify_manifest(self.root, path), [])
        self.artifact.write_bytes(b"mutated")
        self.assertIn("artifact content no longer matches manifest", candidate.verify_manifest(self.root, path))

    def test_verification_rejects_malformed_manifest_without_throwing(self):
        path = self.root / "manifest.json"
        path.write_text("{not-json", encoding="utf-8")
        self.assertTrue(any("manifest is invalid JSON" in problem
                            for problem in candidate.verify_manifest(self.root, path)))

    def test_verification_rejects_redirected_manifest(self):
        manifest = candidate.make_manifest(self.root, [self.artifact])
        path = self.root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        def manifest_only(candidate_path: Path) -> bool:
            return candidate_path == path
        with mock.patch.object(Path, "is_symlink", manifest_only):
            self.assertTrue(any("manifest must not be a symlink" in problem
                                for problem in candidate.verify_manifest(self.root, path)))

    def test_manifest_publication_refuses_to_replace_a_record(self):
        manifest = candidate.make_manifest(self.root, [self.artifact])
        path = self.root / "manifests" / "candidate.json"
        candidate.write_new_manifest(path, manifest)
        original = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "refusing to overwrite immutable manifest"):
            candidate.write_new_manifest(path, manifest)
        self.assertEqual(path.read_bytes(), original)

    def test_symlink_artifact_is_rejected_before_hashing(self):
        redirected = self.root / "redirected.rbf"
        def redirected_only(path: Path) -> bool:
            return path == redirected
        with mock.patch.object(Path, "is_symlink", redirected_only):
            with self.assertRaisesRegex(RuntimeError, "must not be a symlink"):
                candidate.artifact_records(self.root, [redirected])

    def test_symlinked_input_directory_entry_is_rejected_before_hashing(self):
        redirected = self.root / "support" / "scripts" / "source.txt"
        def redirected_only(path: Path) -> bool:
            return path == redirected
        with mock.patch.object(Path, "is_symlink", redirected_only):
            with self.assertRaisesRegex(RuntimeError, "must not contain a symlink"):
                candidate.files_for_inputs(self.root, ["support/scripts"])

    def test_symlinked_input_parent_is_rejected_before_resolution(self):
        redirected = self.root / "support" / "scripts"
        def redirected_only(path: Path, stop: Path | None = None) -> Path | None:
            return redirected if path == redirected else None
        with mock.patch.object(candidate, "first_symlink_component", side_effect=redirected_only):
            with self.assertRaisesRegex(RuntimeError, "candidate input path must not contain a symlink"):
                candidate.files_for_inputs(self.root, ["support/scripts"])

    def test_symlinked_artifact_parent_is_rejected_before_resolution(self):
        redirected_parent = self.artifact.parent
        with mock.patch.object(candidate, "first_symlink_component", return_value=redirected_parent):
            with self.assertRaisesRegex(RuntimeError, "path must not contain a symlink"):
                candidate.artifact_records(self.root, [self.artifact])


if __name__ == "__main__":
    unittest.main()

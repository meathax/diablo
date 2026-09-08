import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "mister_preflight.py"
SPEC = importlib.util.spec_from_file_location("mister_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(preflight)


class MisterPreflightTests(unittest.TestCase):
    def test_safe_relative_rejects_escape_and_absolute_paths(self):
        for value in (".", "./", "../outside", "/absolute", "C:/absolute", "a/../b", "a//b"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    preflight.safe_relative(value)

    def test_remote_package_hashes_and_sizes_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local = root / "local"
            remote = root / "remote"
            local.mkdir()
            remote.mkdir()
            payload = b"candidate package"
            (local / "package-manifest.json").write_text(
                '{"files":[{"path":"devilutionx","bytes":17,"sha256":"'
                + __import__("hashlib").sha256(payload).hexdigest() + '"}]}', encoding="utf-8")
            (local / "devilutionx").write_bytes(payload)
            (remote / "package-manifest.json").write_bytes((local / "package-manifest.json").read_bytes())
            (remote / "devilutionx").write_bytes(payload)
            records, problems = preflight.verify_remote_package(remote, local)
            self.assertEqual(problems, [])
            self.assertEqual(records[0]["path"], "package-manifest.json")
            self.assertEqual(records[0]["match"], True)
            (remote / "devilutionx").write_bytes(b"tampered")
            _, problems = preflight.verify_remote_package(remote, local)
            self.assertIn("remote package file hash/size mismatch: devilutionx", problems)
            (remote / "devilutionx").write_bytes(payload)
            (remote / "package-manifest.json").write_bytes(b'{"files":[]}')
            _, problems = preflight.verify_remote_package(remote, local)
            self.assertIn("remote package file hash/size mismatch: package-manifest.json", problems)

    def test_probe_requires_target_files_and_arm_elf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "MiSTer").write_bytes(bytes([0x7F]) + b"ELF" + b"x")
            (root / "menu.rbf").write_bytes(b"rbf")
            records, problems = preflight.probe_target(root, ("MiSTer", "menu.rbf", "MiSTer.ini"))
            self.assertEqual(len(records), 3)
            self.assertIn("target probe is missing: MiSTer.ini", problems)
            self.assertFalse(any(item.get("path") == "MiSTer" and not item.get("elf_header") for item in records))

    def test_receipt_writer_emits_json_and_is_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = Path(temporary) / "receipt.json"
            preflight._write_immutable(receipt, {"status": "pass"})
            self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["status"], "pass")
            with self.assertRaises(RuntimeError):
                preflight._write_immutable(receipt, {"status": "changed"})

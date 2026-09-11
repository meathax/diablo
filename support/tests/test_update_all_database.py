from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate_update_all.py"

SPEC = importlib.util.spec_from_file_location("generate_update_all", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
generate_update_all = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_update_all)


class UpdateAllDatabaseTests(unittest.TestCase):
    def test_external_csv_generates_only_the_five_audited_game_files(self) -> None:
        rows = generate_update_all.load_external_files()
        expected = {
            "games/Diablo/DIABDAT.MPQ",
            "games/Diablo/hellfire.mpq",
            "games/Diablo/hfmonk.mpq",
            "games/Diablo/hfmusic.mpq",
            "games/Diablo/hfvoice.mpq",
        }
        self.assertEqual({entry["path"] for entry in rows}, expected)

        database = generate_update_all.build_database(rows)
        self.assertEqual(database["db_id"], "diablo_mister")
        self.assertEqual(set(database["folders"]), {"games/", "games/Diablo/"})
        self.assertEqual(set(database["files"]), expected)
        for name, entry in database["files"].items():
            self.assertTrue(entry["url"].startswith("https://archive.org/download/diablohellfire/"))
            self.assertIn(".iso/", entry["url"])
            self.assertFalse(entry["url"].endswith(".iso"))
            self.assertEqual(len(entry["hash"]), 32, name)
            self.assertGreater(entry["size"], 0, name)
            self.assertEqual(entry["tags"], ["diablo"])

        rendered = generate_update_all.rendered_database(rows).encode("utf-8")
        self.assertEqual((ROOT / "distribution/diablo_mister.json").read_bytes(), rendered)
        with zipfile.ZipFile(ROOT / "distribution/diablo_mister.json.zip") as archive:
            self.assertEqual(archive.namelist(), ["diablo_mister.json"])
            self.assertEqual(archive.read("diablo_mister.json"), rendered)

    def test_legacy_inventory_matches_external_csv(self) -> None:
        self.assertEqual(
            generate_update_all.build_database(generate_update_all.load_inventory()),
            generate_update_all.build_database(generate_update_all.load_external_files()),
        )

    def test_external_csv_rejects_extra_missing_or_changed_payload(self) -> None:
        original = (ROOT / "external_files.csv").read_text(encoding="utf-8")
        cases = (
            original + "games/Diablo/extra.mpq,https://example.com/extra,1," + "0" * 32 + ",diablo,overwrite:true,\n",
            "\n".join(original.splitlines()[:-1]) + "\n",
            original.replace("517501282", "517501281", 1),
        )
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "external_files.csv"
            for text in cases:
                with self.subTest(text=text[-80:]):
                    csv_path.write_text(text, encoding="utf-8")
                    with self.assertRaises(generate_update_all.InventoryError):
                        generate_update_all.load_external_files(csv_path)

    def test_runtime_inventory_excludes_local_sd_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory)
            (ready / "Diablo").write_bytes(b"runtime")
            (ready / "Diablo Test.zip").write_bytes(b"local game-data export")
            self.assertEqual([ready / "Diablo"], generate_update_all._runtime_files(ready))

    def test_runtime_archive_matches_ready_tree_and_official_schema(self) -> None:
        database_path = ROOT / "distribution/diablo_runtime.json"
        archive_path = ROOT / "distribution/diablo_runtime.zip"
        generate_update_all.check_runtime_artifacts(
            ROOT / "ready",
            database_path,
            ROOT / "distribution/diablo_runtime.json.zip",
            archive_path,
        )
        database = json.loads(database_path.read_text(encoding="utf-8"))
        self.assertEqual(database["files"], {})
        self.assertEqual(database["folders"], {})
        self.assertEqual(set(database["archives"]), {"diablo_runtime_bundle"})
        descriptor = database["archives"]["diablo_runtime_bundle"]
        self.assertEqual(descriptor["format"], "zip")
        self.assertEqual(descriptor["extract"], "selective")
        self.assertNotIn("target_folder", descriptor)
        self.assertEqual(
            descriptor["archive_file"]["url"],
            "https://raw.githubusercontent.com/meathax/diablo/main/distribution/diablo_runtime.zip",
        )
        self.assertEqual(
            descriptor["base_files_url"],
            "https://raw.githubusercontent.com/meathax/diablo/main/ready",
        )
        ready_files = {path.relative_to(ROOT / "ready").as_posix()
                       for path in (ROOT / "ready").rglob("*") if path.is_file()
                       and not path.relative_to(ROOT / "ready").as_posix().startswith("games/")
                       and not (path.parent == ROOT / "ready" and path.suffix.lower() == ".zip")}
        staged_game_files = {path.relative_to(ROOT / "ready").as_posix()
                             for path in (ROOT / "ready/games").rglob("*") if path.is_file()}
        self.assertEqual(staged_game_files,
                         {entry["path"] for entry in generate_update_all.load_external_files()})
        summary = descriptor["summary_inline"]
        self.assertEqual(set(summary["files"]), ready_files)
        for destination, entry in summary["files"].items():
            self.assertEqual(entry["arc_id"], "diablo_runtime_bundle")
            self.assertEqual(entry["arc_at"], destination)
            self.assertEqual(entry["tags"], ["diablo"])
        self.assertEqual(
            descriptor["archive_file"]["hash"],
            hashlib.md5(archive_path.read_bytes()).hexdigest(),
        )

    def test_drop_in_ini_registers_both_matching_database_ids(self) -> None:
        ini = (ROOT / "distribution/downloader_meathax_diablo.ini").read_text(encoding="utf-8")
        self.assertIn("[diablo_runtime]", ini)
        self.assertIn("diablo_runtime.json.zip", ini)
        self.assertIn("[diablo_mister]", ini)
        self.assertIn("diablo_mister.json.zip", ini)
        self.assertNotIn("MiSTer.ini", ini)


if __name__ == "__main__":
    unittest.main()

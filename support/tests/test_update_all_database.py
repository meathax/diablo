from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate_update_all.py"

SPEC = importlib.util.spec_from_file_location("generate_update_all", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
generate_update_all = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_update_all)


class UpdateAllDatabaseTests(unittest.TestCase):
    def test_generated_database_is_current_and_limited_to_required_game_files(self) -> None:
        inventory = generate_update_all.load_inventory()
        expected = {"DIABDAT.MPQ", "hellfire.mpq", "hfmonk.mpq", "hfmusic.mpq", "hfvoice.mpq"}
        self.assertEqual({entry["name"] for entry in inventory["files"]}, expected)

        database = generate_update_all.build_database(inventory)
        self.assertEqual(database["db_id"], "diablo_mister")
        self.assertEqual(set(database["folders"]), {"games/", "games/Diablo/"})
        self.assertEqual(set(database["files"]), {f"games/Diablo/{name}" for name in expected})
        for name, entry in database["files"].items():
            self.assertTrue(entry["url"].startswith("https://archive.org/download/diablohellfire/"))
            self.assertIn(".iso/", entry["url"])
            self.assertFalse(entry["url"].endswith(".iso"))
            self.assertEqual(len(entry["hash"]), 32, name)
            self.assertGreater(entry["size"], 0, name)

        self.assertEqual(
            (ROOT / "distribution" / "diablo_mister.json").read_text(encoding="utf-8"),
            generate_update_all.rendered_database(inventory),
        )

    def test_extra_or_missing_payload_is_rejected(self) -> None:
        data = generate_update_all.load_inventory()
        data["files"].append({
            "name": "unneeded.iso",
            "archive": "Diablo.iso",
            "size": 1,
            "md5": "0" * 32,
            "kind": "unneeded",
        })
        with tempfile.TemporaryDirectory() as directory:
            inventory_path = Path(directory) / "game_files.json"
            inventory_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(generate_update_all.InventoryError):
                generate_update_all.load_inventory(inventory_path)


if __name__ == "__main__":
    unittest.main()

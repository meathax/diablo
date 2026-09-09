from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "controller_preset.py"
SPEC = importlib.util.spec_from_file_location("controller_preset", SCRIPT)
controller_preset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = controller_preset
SPEC.loader.exec_module(controller_preset)


class ControllerPresetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ini = Path(self.temporary.name) / "diablo.ini"

    def write(self, content: bytes) -> None:
        self.ini.write_bytes(content)

    def test_existing_temporary_file_is_preserved_on_refusal(self) -> None:
        original = b"[Game]\nQuick Cast=0\n"
        self.write(original)
        temporary = self.ini.with_name(self.ini.name + ".controller-preset.tmp")
        temporary.write_bytes(b"another writer's pending data")
        with self.assertRaises(FileExistsError):
            controller_preset.apply_preset(self.ini)
        self.assertEqual(self.ini.read_bytes(), original)
        self.assertEqual(temporary.read_bytes(), b"another writer's pending data")

    def test_apply_preserves_unrelated_sections_and_settings(self) -> None:
        self.write(
            b"; keep this comment\r\n[Graphics]\r\nWidth=640\r\nCustom Flag=unchanged\r\n"
            b"\r\n[Game]\r\nRun in Town=0\r\nQuick Cast=0\r\n"
            b"\r\n[Padmapping]\r\nPrimaryAction=B\r\nCustom Mapping=keep\r\n"
            b"\r\n[Other]\r\nValue=remain\r\n"
        )

        result = controller_preset.apply_preset(self.ini)

        self.assertTrue(result.changed)
        self.assertTrue(result.check.complete)
        rendered = self.ini.read_bytes().decode("utf-8")
        self.assertIn("; keep this comment\r\n[Graphics]\r\nWidth=640\r\nCustom Flag=unchanged\r\n", rendered)
        self.assertIn("Run in Town=0\r\n", rendered)
        self.assertIn("Custom Mapping=keep\r\n", rendered)
        self.assertIn("[Other]\r\nValue=remain\r\n", rendered)
        self.assertIn("PrimaryAction=A\r\n", rendered)
        self.assertIn("Quick Cast=1\r\n", rendered)
        self.assertIn("Auto Refill Belt=1\r\n", rendered)
        self.assertIn("Auto Gold Pickup=1\r\n", rendered)

    def test_backup_preserves_original_bytes_exactly(self) -> None:
        original = b"[Game]\r\nQuick Cast=0\r\n\r\n[Padmapping]\r\nPrimaryAction=B\r\nTitle=\xc3\xa9\r\n"
        self.write(original)

        result = controller_preset.apply_preset(self.ini)

        self.assertEqual(controller_preset.backup_path_for(self.ini), result.backup)
        self.assertEqual(original, result.backup.read_bytes())

    def test_apply_is_idempotent_and_does_not_replace_first_backup(self) -> None:
        original = b"[Game]\nQuick Cast=0\n\n[Padmapping]\nPrimaryAction=B\n"
        self.write(original)
        first = controller_preset.apply_preset(self.ini)
        after_first = self.ini.read_bytes()
        backup = controller_preset.backup_path_for(self.ini)

        second = controller_preset.apply_preset(self.ini)

        self.assertTrue(first.changed)
        self.assertFalse(second.changed)
        self.assertIsNone(second.backup)
        self.assertEqual(after_first, self.ini.read_bytes())
        self.assertEqual(original, backup.read_bytes())

    def test_apply_replaces_conflicting_and_duplicate_padmapping_entries(self) -> None:
        self.write(
            b"[Game]\nQuick Cast=0\nAuto Refill Belt=0\nAuto Gold Pickup=0\n"
            b"\n[Padmapping]\nPrimaryAction=B\nPrimaryAction=X\n"
            b"MoveUp=Up\nMoveDown=Down\nMoveLeft=Left\nMoveRight=Right\n"
            b"MouseUp=Select+Up\nMouseDown=Select+Down\n"
            b"MouseLeft=Select+Left\nMouseRight=Select+Right\n"
            b"LeftMouseClick2=Select+LB\n"
            b"PadHotspellMenu=Select\nPadMenuNavigator=Start\nToggleGameMenu2=Start+Select\n"
        )

        result = controller_preset.apply_preset(self.ini)
        lines = self.ini.read_text(encoding="utf-8").splitlines()

        self.assertTrue(result.check.complete)
        self.assertEqual(1, lines.count("PrimaryAction=A"))
        for mapping in (
            "MoveUp",
            "MoveDown",
            "MoveLeft",
            "MoveRight",
            "MouseUp",
            "MouseDown",
            "MouseLeft",
            "MouseRight",
        ):
            self.assertIn(f"{mapping}=", lines)
        self.assertIn("LeftMouseClick2=", lines)
        self.assertIn("PadHotspellMenu=", lines)
        self.assertIn("PadMenuNavigator=", lines)
        self.assertIn("ToggleGameMenu2=", lines)
        self.assertIn("RightMouseClick1=RT+RS", lines)
        self.assertIn("AutomapMoveDown=RT+Down", lines)
        self.assertIn("QuickSpell4=RT+B", lines)

    def test_malformed_config_refuses_before_backup_or_write(self) -> None:
        malformed = b"[Game\nQuick Cast=0\n"
        self.write(malformed)

        with self.assertRaisesRegex(controller_preset.PresetError, "malformed section header"):
            controller_preset.apply_preset(self.ini)

        self.assertEqual(malformed, self.ini.read_bytes())
        self.assertFalse(controller_preset.backup_path_for(self.ini).exists())

    def test_default_check_is_read_only_and_reports_incomplete(self) -> None:
        original = b"[Game]\nQuick Cast=0\n\n[Padmapping]\nPrimaryAction=B\n"
        self.write(original)

        exit_code = controller_preset.main([str(self.ini)])

        self.assertEqual(1, exit_code)
        self.assertEqual(original, self.ini.read_bytes())
        self.assertFalse(controller_preset.backup_path_for(self.ini).exists())


if __name__ == "__main__":
    unittest.main()

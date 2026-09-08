import re
import unittest
from pathlib import Path


class ShowControlsOsdTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.source = (self.root / "Diablo.sv").read_text(encoding="utf-8")

    def test_show_controls_is_a_single_gamepad_only_osd_page(self):
        self.assertIn('"P1,Show controls;"', self.source)
        lines = re.findall(r'"P1-,([^;]+);"', self.source)
        self.assertEqual(len(lines), 14)
        self.assertLessEqual(max(map(len, lines)), 53)

        required = (
            "A: Attack / talk / lift-place / confirm",
            "X: Cast / quick equip-belt / hold drop",
            "Y: Interact / loot / use-equip-stash",
            "B: Speedbook / panel back / safe stow",
            "LB/RB: Healing / mana potion",
            "LT: Stand ground",
            "RT: Modifier only (no action alone)",
            "RT+X/Y/A/B: Quick spells 1/2/3/4",
            "Left stick: Move / Right stick: Cursor",
            "L3: Labels / R3: Left click / RT+R3: Right click",
            "D-pad up: Spellbook / right: Inventory",
            "D-pad down: Quests / left: Character",
            "RT+D-pad: Pan automap",
            "View: Automap / Menu: Game menu / Guide: OSD",
        )
        page = "\n".join(lines)
        for control in required:
            self.assertIn(control, page)

        self.assertNotRegex(page.lower(), r"\b(keyboard|mouse|wasd|arrow key)\b")


if __name__ == "__main__":
    unittest.main()

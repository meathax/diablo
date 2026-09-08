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
        self.assertLessEqual(max(map(len, lines)), 28)

        required = (
            "A: Attack/talk/lift/confirm",
            "X: Cast/belt equip/hold drop",
            "Y: Interact/loot/equip/stash",
            "B: Speedbook/panel back/stow",
            "LB: health / RB: mana",
            "LT: Stand ground",
            "RT: Modifier (no action)",
            "RT+X/Y/A/B: spells 1-4",
            "LS: move / RS: cursor",
            "L3 labels/R3: LMB/RT+R3: RMB",
            "D-pad: up spells/right inv",
            "D-pad: down quests/left char",
            "RT+D-pad: Pan automap",
            "View map/Menu game/Guide OSD",
        )
        page = "\n".join(lines)
        for control in required:
            self.assertIn(control, page)

        self.assertNotRegex(page.lower(), r"\b(keyboard|mouse|wasd|arrow key)\b")


if __name__ == "__main__":
    unittest.main()

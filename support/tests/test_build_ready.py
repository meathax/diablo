import tempfile
import unittest
from pathlib import Path

from support.scripts.build_ready import verify_menu_palettes


class MenuPaletteTests(unittest.TestCase):
    def test_rejects_assets_that_boot_hellfire_but_cannot_open_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            assets = Path(temporary)
            ui = assets / 'ui_art'
            ui.mkdir()
            (ui / 'diablo.pal').write_bytes(bytes(768))
            # Main-menu art alone does not provide the Settings palette.
            (ui / 'mainmenuw.clx').write_bytes(b'main menu')
            with self.assertRaisesRegex(ValueError, 'hellfire Settings palette'):
                verify_menu_palettes(assets)
            (ui / 'hellfire.pal').write_bytes(bytes(767))
            with self.assertRaisesRegex(ValueError, 'hellfire Settings palette'):
                verify_menu_palettes(assets)
            (ui / 'hellfire.pal').write_bytes(bytes(768))
            verify_menu_palettes(assets)


if __name__ == '__main__':
    unittest.main()

"""The stock menus own multiplayer connection and game selection."""
from pathlib import Path
import unittest
ROOT = Path(__file__).parents[2]

class NetplayContractTest(unittest.TestCase):
    def test_native_transports_remain_enabled_without_menu_overlays(self):
        source = (ROOT / "support/cmake/arm-transport.cmake").read_text()
        for setting in ("NONET", "DISABLE_TCP", "DISABLE_ZERO_TIER"):
            self.assertIn(f"set({setting} OFF", source)
        self.assertIn("set(PACKET_ENCRYPTION ON", source)
        self.assertNotIn("mister_netplay", source)
        self.assertNotIn("set(multi_source", source)
        self.assertNotIn("set(selgame_source", source)
        self.assertIn("DIABLO_MISTER_TEXT_INPUT_ACTIVE", source)

    def test_provider_fixture_tracks_the_local_player_after_join(self):
        source = (ROOT / "support/tests/netplay_peer.cpp").read_text()
        self.assertIn("MyPlayerId = static_cast<size_t>(id);", source)

    def test_osd_and_launcher_do_not_control_multiplayer(self):
        hdl = (ROOT / "Diablo.sv").read_text()
        self.assertNotIn(",Netplay,", hdl)
        self.assertNotIn(",Code 1,", hdl)
        for name in ("support/mister/diablo_main.cpp", "support/scripts/mister_launcher.py"):
            source = (ROOT / name).read_text()
            self.assertNotIn("diablo-netplay.command", source)
            self.assertNotIn("DIABLO_MISTER_NETPLAY", source)

    def test_boot_closes_inherited_osd_before_core_reset_release(self):
        source = (ROOT / "support/mister/diablo_main.cpp").read_text()
        init = source.index("user_io_init(")
        close = source.index("OsdDisable();")
        reset = source.index("release_core_reset();")
        self.assertLess(init, close)
        self.assertLess(close, reset)

    def test_release_video_cannot_reenable_retained_diagnostic_status(self):
        source = (ROOT / "Diablo.sv").read_text()
        self.assertIn("wire diagnostic_video = 1'b0;", source)

    def test_resident_rbf_handoff_uses_shared_save_root(self):
        source = (ROOT / "support/mister/diablo_main.cpp").read_text()
        self.assertIn('"--save-root"', source)
        self.assertIn('"/media/fat/saves/Diablo"', source)
        self.assertNotIn('"/media/fat/games/Diablo/Saves"', source)

if __name__ == "__main__":
    unittest.main()

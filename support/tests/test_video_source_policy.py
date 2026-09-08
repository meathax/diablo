from pathlib import Path
import unittest


class VideoSourceContractTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[2]

    def test_top_level_policy_is_explicit_and_frame_gated(self) -> None:
        source = (self.root / "Diablo.sv").read_text(encoding="utf-8")
        required = (
            "diablo_video_source_policy video_source_policy",
            ".vga_scaler_enable(VGA_SCALER)",
            ".framebuffer_enable(FB_EN)",
            ".diagnostic_enable(video_direct_diagnostic)",
            ".startup_error(video_startup_error)",
        )
        for token in required:
            self.assertIn(token, source)

    def test_release_matrix_names_each_connector_row(self) -> None:
        matrix = (self.root / "support/qualification/closure-gates.json").read_text(encoding="utf-8")
        for token in ("HDMI framebuffer/scaler", "Direct RGB", "Analog/scandoubler"):
            self.assertIn(token, matrix)

    def test_scandoubler_sync_disposition_is_not_a_silent_todo(self) -> None:
        source = (self.root / "sys/scandoubler.v").read_text(encoding="utf-8")
        self.assertNotIn("TODO: Delay vsync one line", source)
        self.assertIn("same three-line pipeline as VBlank", source)
        self.assertIn(".mono(1'b0)", source)


if __name__ == "__main__":
    unittest.main()

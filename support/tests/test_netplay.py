"""Static contract checks for the OSD-to-engine netplay bridge."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[2]


class NetplayContractTest(unittest.TestCase):
    def test_osd_fields_are_non_overlapping_and_preserve_reserved_bits(self):
        source = (ROOT / "Diablo.sv").read_text(encoding="utf-8")
        fields = {
            label: (int(high), int(low))
            for high, low, label in re.findall(r'"O\[(\d+):(\d+)\],([^,;]+)', source)
        }
        expected = {
            "Netplay": (8, 7),
            "Code 1": (14, 10),
            "Code 2": (19, 15),
            "Code 3": (24, 20),
            "Code 4": (29, 25),
            "Code 5": (34, 30),
        }
        self.assertEqual(expected, {key: fields[key] for key in expected})
        bits = []
        for high, low in expected.values():
            bits.extend(range(low, high + 1))
        self.assertEqual(len(bits), len(set(bits)))
        self.assertTrue(set(bits).isdisjoint({1, 6, 121, 122}))

    def test_frontend_and_engine_use_the_same_status_fields(self):
        hdl = (ROOT / "Diablo.sv").read_text(encoding="utf-8")
        frontend = (ROOT / "support/mister/diablo_main.cpp").read_text(encoding="utf-8")
        for field in ("[8:7]", "[14:10]", "[19:15]", "[24:20]", "[29:25]", "[34:30]"):
            self.assertIn(field, hdl)
            self.assertIn(field, frontend)

    def test_arm_overlay_keeps_native_transports_enabled(self):
        cmake = (ROOT / "support/cmake/arm-transport.cmake").read_text(encoding="utf-8")
        self.assertIn("set(NONET OFF", cmake)
        self.assertIn("set(DISABLE_TCP OFF", cmake)
        self.assertIn("set(DISABLE_ZERO_TIER OFF", cmake)
        self.assertIn("mister_netplay.cpp", cmake)
        self.assertIn("if(NONET)", cmake)

    def test_plan_documents_simulator_then_mister_acceptance(self):
        plan = (ROOT / "netplay.md").read_text(encoding="utf-8")
        self.assertIn("Verilator", plan)
        self.assertIn("Final MiSTer checks", plan)
        self.assertIn("two to four", plan)


if __name__ == "__main__":
    unittest.main()

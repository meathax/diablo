import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("audit", Path(__file__).parents[1] / "scripts/quartus_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def table(name, rows):
    return "; " + name + " ;\n" + "\n".join("; " + " ; ".join(r) + " ;" for r in rows) + "\n"


def timing_fixture():
    text = ""
    for corner in ("Slow Model", "Fast Model"):
        for kind in audit.TIMING_KINDS:
            text += table(f"{corner} {kind} Summary", [["Clock", "Slack", "End Point TNS"], ["clk", "0.100", "0.000"]])
    return text + table("Unconstrained Paths Summary", [["Property", "Setup", "Hold"]] +
                        [[name, "0", "0"] for name in ["Illegal Clocks", "Unconstrained Clocks", "Unconstrained Input Ports", "Unconstrained Output Ports"]])


class TimingTests(unittest.TestCase):
    contract = {"required_corners": ["Slow Model", "Fast Model"], "required_clocks": ["clk"]}

    def test_all_checks_and_corners(self):
        self.assertEqual(len(audit.timing(timing_fixture(), self.contract)["corners"]), 2)

    def test_negative_slack_in_later_corner(self):
        early, late = timing_fixture().split("; Fast Model Setup Summary", 1)
        text = early + "; Fast Model Setup Summary" + late.replace("; clk ; 0.100", "; clk ; -0.001", 1)
        with self.assertRaises(audit.AuditError): audit.timing(text, self.contract)

    def test_nonzero_tns_even_with_positive_slack(self):
        with self.assertRaises(audit.AuditError): audit.timing(timing_fixture().replace("0.000", "-0.010", 1), self.contract)

    def test_nan_does_not_pass_comparison(self):
        with self.assertRaises(audit.AuditError): audit.timing(timing_fixture().replace("0.100", "NaN", 1), self.contract)

    def test_missing_corner(self):
        with self.assertRaises(audit.AuditError): audit.timing(timing_fixture(), {**self.contract, "required_corners": ["Slow Model"]})

    def test_missing_hold(self):
        with self.assertRaises(audit.AuditError): audit.timing(timing_fixture().replace("Fast Model Hold Summary", "Unknown Summary"), self.contract)

    def test_missing_active_clock(self):
        with self.assertRaises(audit.AuditError): audit.timing(timing_fixture(), {**self.contract, "required_clocks": ["missing"]})

    def test_unconstrained_nonzero_requires_actual_names(self):
        text = timing_fixture().replace("Unconstrained Output Ports ; 0", "Unconstrained Output Ports ; 1")
        with self.assertRaises(audit.AuditError): audit.timing(text, self.contract)

    def test_duplicate_table(self):
        with self.assertRaises(audit.AuditError): audit.timing(timing_fixture() * 2, self.contract)

    def test_repeated_detail_headings_do_not_hide_unique_summary(self):
        details = table("Unconstrained Input Ports", [["Name"], ["fixture"]])
        self.assertEqual(len(audit.timing(timing_fixture() + details * 2, self.contract)["corners"]), 2)


class InferenceTests(unittest.TestCase):
    contract = {"device": "5CSEBA6U23I7", "required_memories": {"cache": {"bits": 4096}}}
    text = "; Analysis & Synthesis Status ; Successful - fixture ;\n; Device ; 5CSEBA6U23I7 ;\n" + table(
        "Analysis & Synthesis RAM Summary", [["Name", "Type", "Mode", "Port A Depth", "Port A Width", "Port B Depth", "Port B Width", "Size", "MIF"],
        ["cache", "AUTO", "Simple Dual Port", "512", "8", "512", "8", "4096", "None"]])

    def test_inferred_shape_matches(self):
        self.assertEqual(audit.inference(self.text, self.contract)["inferred_memory_count"], 1)

    def test_missing_memory_rejects_silent_register_implementation(self):
        with self.assertRaises(audit.AuditError): audit.inference(self.text.replace("; cache ;", "; other ;"), self.contract)

    def test_wrong_device(self):
        with self.assertRaises(audit.AuditError): audit.inference(self.text.replace("5CSEBA6U23I7", "OTHER"), self.contract)

    def test_wrong_size(self):
        with self.assertRaises(audit.AuditError): audit.inference(self.text.replace("4096", "8192"), self.contract)

    def test_unreviewed_ram_diagnostic(self):
        text = self.text + '\nInfo (276004): RAM logic "other" is uninferred due to asynchronous read logic File: fixture.sv Line: 1'
        with self.assertRaises(audit.AuditError): audit.inference(text, self.contract)

    def test_stale_allowlist(self):
        with self.assertRaises(audit.AuditError): audit.inference(self.text, {**self.contract, "reviewed_uninferred": [{"name":"gone", "reason":"tiny", "evidence":"fixture"}]})


class FitTests(unittest.TestCase):
    text = "; Fitter Status ; Successful - fixture ;\n; Device ; 5CSEBA6U23I7 ;\n" + "\n".join(
        f"; {label} ; 10 / 100 ( 10 % ) ;" for label in
        ["Logic utilization (in ALMs)", "Total block memory bits", "Total DSP Blocks"])

    def test_capacity_accounting(self):
        self.assertEqual(len(audit.fit(self.text, {"device":"5CSEBA6U23I7"})), 3)

    def test_over_capacity(self):
        with self.assertRaises(audit.AuditError):
            audit.fit(self.text.replace("10 / 100", "101 / 100", 1), {"device":"5CSEBA6U23I7"})

    def test_zero_capacity(self):
        with self.assertRaises(audit.AuditError):
            audit.fit(self.text.replace("10 / 100", "0 / 0", 1), {"device":"5CSEBA6U23I7"})


if __name__ == "__main__": unittest.main()

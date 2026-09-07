import importlib.util
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
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


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.text = timing_fixture().replace("Unconstrained Output Ports ; 0 ; 0",
                                             "Unconstrained Output Ports ; 2 ; 1")
        self.raw = self.text.encode("utf-8")
        self.digest = hashlib.sha256(self.raw).hexdigest()
        groups = {domain: {category: [] for category in audit.UNCONSTRAINED_PROPERTIES}
                  for domain in audit.DOMAINS}
        groups["Setup"]["Unconstrained Output Ports"] = ["top|port[1]", "top|port[0]"]
        groups["Hold"]["Unconstrained Output Ports"] = ["top|port[0]"]
        self.export = audit.normalize_unconstrained(self.raw, groups)
        self.contract = {**TimingTests.contract, "reviewed_unconstrained": [
            {"domain": domain, "property": category, "name": name, "evidence": "synthetic review"}
            for domain, properties in groups.items() for category, names in properties.items() for name in names]}

    def run_audit(self):
        return audit.timing(self.text, self.contract, self.export, self.digest)

    def test_exact_names_counts_and_domain_identity(self):
        self.assertEqual(self.run_audit()["unconstrained"]["reviewed_endpoint_count"], 3)
        self.assertEqual(self.export["domains"]["Setup"]["Unconstrained Output Ports"],
                         ["top|port[0]", "top|port[1]"])

    def test_stale_report_hash(self):
        self.export["report_sha256"] = "0" * 64
        with self.assertRaises(audit.AuditError): self.run_audit()

    def test_hash_of_original_bytes_including_crlf(self):
        raw = self.raw.replace(b"\n", b"\r\n")
        export = audit.normalize_unconstrained(raw, self.export["domains"])
        with self.assertRaises(audit.AuditError):
            audit.timing(self.text, self.contract, export, self.digest)
        audit.timing(raw.decode(), self.contract, export, hashlib.sha256(raw).hexdigest())

    def test_missing_domain_or_empty_category(self):
        for mutation in (lambda x: x.pop("Hold"), lambda x: x["Hold"].pop("Illegal Clocks")):
            export = copy.deepcopy(self.export)
            mutation(export["domains"])
            with self.assertRaises(audit.AuditError):
                audit.timing(self.text, self.contract, export, self.digest)

    def test_swapped_domains(self):
        groups = self.export["domains"]
        groups["Setup"], groups["Hold"] = groups["Hold"], groups["Setup"]
        with self.assertRaises(audit.AuditError): self.run_audit()

    def test_missing_extra_duplicate_and_wrong_names(self):
        for names in (["top|port[0]"], ["top|port[0]", "top|port[1]", "extra"],
                      ["top|port[0]", "top|port[0]"], ["top|port[0]", "wrong"]):
            self.export["domains"]["Setup"]["Unconstrained Output Ports"] = names
            with self.subTest(names=names), self.assertRaises(audit.AuditError): self.run_audit()

    def test_reviews_cannot_be_wildcards_or_stale_or_duplicated(self):
        original = copy.deepcopy(self.contract["reviewed_unconstrained"])
        cases = [original[:-1], original + [original[0]],
                 original + [{**original[0], "name": "stale"}],
                 [{**entry, "name": "top|*"} for entry in original],
                 [{**entry, "evidence": " "} for entry in original]]
        for reviews in cases:
            self.contract["reviewed_unconstrained"] = reviews
            with self.subTest(reviews=reviews), self.assertRaises(audit.AuditError): self.run_audit()

    def test_zero_summary_rejects_stale_reviews_and_extra_exports(self):
        with self.assertRaises(audit.AuditError): audit.timing(timing_fixture(), self.contract)
        self.text = timing_fixture()
        with self.assertRaises(audit.AuditError): self.run_audit()

    def test_fractional_negative_or_unknown_counts(self):
        for count in ("0.0", "-1", "NaN", "1e0", "+1"):
            text = timing_fixture().replace("Illegal Clocks ; 0", "Illegal Clocks ; " + count)
            with self.subTest(count=count), self.assertRaises(audit.AuditError):
                audit.timing(text, TimingTests.contract)

    def test_unknown_summary_category(self):
        text = timing_fixture() + "; Unknown Ports ; 0 ; 0 ;\n"
        with self.assertRaises(audit.AuditError): audit.timing(text, TimingTests.contract)

    def test_invalid_export_shapes(self):
        for groups in ([], {}, {"Setup": [], "Hold": {}},
                       {"Setup": {}, "Hold": {}, "Recovery": {}}):
            with self.subTest(groups=groups), self.assertRaises(audit.AuditError):
                audit.normalize_unconstrained(self.raw, groups)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(audit.AuditError): audit.strict_json(b'{"Setup": {}, "Setup": {}}')

    def test_cli_hashes_inputs_and_remains_report_only(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            report, contract, export, output = [directory / name for name in
                                                ("sta.rpt", "contract.json", "export.json", "receipt.json")]
            report.write_bytes(self.raw)
            contract.write_text(json.dumps(self.contract), encoding="utf-8")
            export.write_text(json.dumps(self.export), encoding="utf-8")
            command = [sys.executable, str(Path(audit.__file__)), "timing", "--report", str(report),
                       "--contract", str(contract), "--unconstrained-export", str(export),
                       "--output", str(output), "--encoding", "utf-8"]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            receipt = json.loads(output.read_bytes())
            self.assertFalse(receipt["release_acceptance"])
            self.assertEqual(receipt["report_sha256"], self.digest)
            self.assertEqual(receipt["unconstrained_export_sha256"], hashlib.sha256(export.read_bytes()).hexdigest())
            saved = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), saved)
            self.export["report_sha256"] = "0" * 64
            export.write_text(json.dumps(self.export), encoding="utf-8")
            command[command.index(str(output))] = str(directory / "failed.json")
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            failure = json.loads((directory / "failed.json").read_bytes())
            self.assertEqual(failure["status"], "fail")
            self.assertFalse(failure["release_acceptance"])


class InferenceTests(unittest.TestCase):
    contract = {"device": "5CSEBA6U23I7", "required_memories": {"cache": {
        "bits": 4096, "mode": "Simple Dual Port", "port_a_depth": 512,
        "port_a_width": 8, "port_b_depth": 512, "port_b_width": 8}},
        "required_entities": {"|top|cache": {"max_registers_inclusive": 12, "block_memory_bits": 4096}}}
    text = "; Analysis & Synthesis Status ; Successful - fixture ;\n; Device ; 5CSEBA6U23I7 ;\n" + table(
        "Analysis & Synthesis RAM Summary", [["Name", "Type", "Mode", "Port A Depth", "Port A Width", "Port B Depth", "Port B Width", "Size", "MIF"],
        ["cache", "AUTO", "Simple Dual Port", "512", "8", "512", "8", "4096", "None"]]) + table(
        "Analysis & Synthesis Resource Utilization by Entity", [
        ["Compilation Hierarchy Node", "Combinational ALUTs", "Dedicated Logic Registers", "Block Memory Bits",
         "DSP Blocks", "Pins", "Virtual Pins", "Full Hierarchy Name", "Entity Name", "Library Name"],
        ["|cache", "8 (8)", "12 (10)", "4096", "0", "0", "0", "|top|cache", "cache", "work"]])

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

    def test_empty_or_incomplete_contract(self):
        for value in ({}, None, {"cache": {"bits": 4096}}):
            with self.subTest(value=value), self.assertRaises(audit.AuditError):
                audit.inference(self.text, {**self.contract, "required_memories": value})

    def test_wrong_port_shape_same_size(self):
        with self.assertRaises(audit.AuditError):
            audit.inference(self.text.replace("512 ; 8", "256 ; 16"), self.contract)

    def test_missing_entity_and_register_explosion(self):
        for text in (self.text.replace("|top|cache", "|top|other"),
                     self.text.replace("12 (10)", "4096 (4096)"),
                     self.text.replace("12 (10)", "12 (13)")):
            with self.subTest(text=text), self.assertRaises(audit.AuditError):
                audit.inference(text, self.contract)

    def test_entity_counts_not_summed_across_hierarchy(self):
        entity = audit.inference(self.text, self.contract)["entities"]["|top|cache"]
        self.assertEqual(entity, {"registers_inclusive": 12, "registers_local": 10, "block_memory_bits": 4096})

    def test_empty_entity_contract(self):
        with self.assertRaises(audit.AuditError):
            audit.inference(self.text, {**self.contract, "required_entities": {}})

    def test_malformed_comma_count(self):
        with self.assertRaises(audit.AuditError):
            audit.inference(self.text.replace("4096", "4,,096"), self.contract)


class DiagnosticTests(unittest.TestCase):
    message = "Critical Warning (127005): synthetic mismatch File: fixture.sv Line: 1"

    def setUp(self):
        self.text = InferenceTests.text + self.message + "\n"
        self.digest = hashlib.sha256(self.text.encode()).hexdigest()
        self.review = {"message": self.message, "count": 1, "report_sha256": self.digest,
                       "evidence": "synthetic fixture review"}

    def test_exact_review(self):
        result = audit.inference(self.text, {**InferenceTests.contract, "reviewed_diagnostics": [self.review]}, self.digest)
        self.assertEqual(result["diagnostics"]["reviewed_critical_warnings"][self.message], 1)

    def test_changed_message_count_hash_or_review(self):
        cases = [(self.text, []), (self.text + self.message, [self.review]),
                 (self.text.replace("Line: 1", "Line: 2"), [self.review]),
                 (self.text, [self.review, self.review]),
                 (self.text, [{**self.review, "report_sha256": "0" * 64}]),
                 (self.text, [{**self.review, "count": True}]),
                 (self.text, [{**self.review, "evidence": " "}]),
                 (InferenceTests.text, [self.review])]
        for text, reviews in cases:
            with self.subTest(reviews=reviews), self.assertRaises(audit.AuditError):
                audit.diagnostics(text, {"reviewed_diagnostics": reviews}, self.digest)

    def test_errors_and_tabular_criticals_cannot_be_waived(self):
        for line in ("Error (1): failure", "; port ; Input ; Critical Warning ; mismatch ;",
                     "Critical Warning: unknown format"):
            with self.subTest(line=line), self.assertRaises(audit.AuditError):
                audit.diagnostics(line, {}, self.digest)

    def test_timing_cannot_ignore_error_diagnostics(self):
        with self.assertRaises(audit.AuditError):
            audit.timing(timing_fixture() + "Error (1): failure", TimingTests.contract)


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

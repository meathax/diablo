"""Run a read-only C25 SDC trial against the fitted C34 Quartus netlist.

The trial copies the immutable fitted project into a disposable directory,
reads the copied original SDC files, and then applies only the C25 additions
extracted from the working-tree ``Diablo.sdc``.  The C34 snapshot is never used
as a Quartus working directory.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / ".work" / "c34"
C25_MARKER = "# C25 HDMI_MCLK forwarded-clock decision"
FULL_STA_METRICS = (
    "setup",
    "hold",
    "recovery",
    "removal",
    "minimum_pulse_width",
)
FULL_STA_METRIC_LABELS = {
    "setup": "setup",
    "hold": "hold",
    "recovery": "recovery",
    "removal": "removal",
    "minimum pulse width": "minimum_pulse_width",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_immutable(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise RuntimeError(f"refusing to replace immutable C25 receipt: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def snapshot_records() -> list[dict[str, object]]:
    manifest = SNAPSHOT / ".mister" / "fpga-source-snapshot.json"
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    records: list[dict[str, object]] = []
    for item in data["files"]:
        path = SNAPSHOT / str(item["path"])
        records.append({
            "path": str(item["path"]),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    return sorted(records, key=lambda item: str(item["path"]))


def copy_snapshot(source: Path, destination: Path) -> None:
    def ignore(path: str, names: list[str]) -> set[str]:
        ignored = {".mister"} if Path(path).resolve() == source.resolve() else set()
        return ignored

    shutil.copytree(source, destination, ignore=ignore)


def extract_c25_additions(sdc: Path, output: Path) -> str:
    text = sdc.read_text(encoding="utf-8")
    mclk_marker = "# C25 HDMI_MCLK forwarded-clock decision"
    exception_marker = "# C25 core-specific asynchronous/status exceptions"
    mclk_end_marker = "create_generated_clock -name HDMI_TX_CORE"
    if mclk_marker not in text or exception_marker not in text or mclk_end_marker not in text:
        raise RuntimeError(f"C25 additions marker missing from {sdc}")
    mclk_start = text.index(mclk_marker)
    mclk_end = text.index(mclk_end_marker, mclk_start)
    exception_start = text.index(exception_marker)
    additions = (text[mclk_start:mclk_end].rstrip() + "\n\n"
                 + text[exception_start:].rstrip() + "\n")
    output.write_text(additions, encoding="utf-8")
    return additions


def write_trial_tcl(path: Path) -> None:
    path.write_text(
        r'''package require ::quartus::project
package require ::quartus::sta

set project_root [file normalize [lindex $argv 0]]
set additions [file normalize [lindex $argv 1]]
set summary_path [file normalize [lindex $argv 2]]
set baseline_sdc_report [file normalize [lindex $argv 3]]
set after_sdc_report [file normalize [lindex $argv 4]]
set summary [open $summary_path w]

proc emit {channel key value} {
    puts $channel "$key\t$value"
    flush $channel
}

proc names {collection} {
    set result {}
    foreach_in_collection item $collection {
        lappend result [get_port_info -name $item]
    }
    return [join [lsort $result] ,]
}

proc count_paths {kind direction collection} {
    set args [list -npaths 0]
    if {$kind eq "hold"} {
        lappend args -hold
    } else {
        lappend args -setup
    }
    lappend args $direction $collection
    if {[catch {set paths [eval get_timing_paths $args]}]} {
        return -1
    }
    return [get_collection_size $paths]
}

proc timing_summary {kind} {
    set args [list -npaths 1 -detail summary]
    if {$kind eq "hold"} {
        lappend args -hold
    } else {
        lappend args -setup
    }
    if {[catch {set result [eval report_timing $args]}]} {
        return "error"
    }
    return [join $result ,]
}

proc internal_timing_summary {kind} {
    set registers [get_registers *]
    set args [list -npaths 1 -detail summary]
    if {$kind eq "hold"} {
        lappend args -hold
    } else {
        lappend args -setup
    }
    lappend args -from $registers -to $registers
    if {[catch {set result [eval report_timing $args]}]} {
        return "error"
    }
    return [join $result ,]
}

proc exact_ports {label names expected} {
    set collection [get_ports $names]
    set actual [get_collection_size $collection]
    if {$actual != $expected} {
        error "C25 $label expected $expected ports, resolved $actual: $names"
    }
    return $collection
}

proc exact_mclk_collections {} {
    set pin [get_pins -compatibility_mode {pll_audio*PLL_OUTPUT_COUNTER|divclk}]
    set source [get_clocks {pll_audio*PLL_OUTPUT_COUNTER|divclk}]
    set output [get_ports {HDMI_MCLK}]
    if {[get_collection_size $pin] != 1 ||
        [get_collection_size $source] != 1 ||
        [get_collection_size $output] != 1} {
        error "C25 HDMI_MCLK source/clock/output collection mismatch"
    }
    return [list $pin $source $output]
}

proc emit_port_paths {channel prefix direction ports} {
    foreach_in_collection port $ports {
        set port_name [get_port_info -name $port]
        emit $channel "${prefix}_${port_name}_setup" [count_paths setup $direction $port]
        emit $channel "${prefix}_${port_name}_hold" [count_paths hold $direction $port]
    }
}

cd $project_root
project_open Diablo -revision Diablo
create_timing_netlist

# Read only the original fitted-project constraints first.
read_sdc [file join $project_root sys sys_top.sdc]
read_sdc [file join $project_root Diablo.sdc]
update_timing_netlist

set led [exact_ports "LED status vector" {LED[0] LED[2] LED[6]} 3]
set sdcd [exact_ports "SDCD_SPDIF mode-multiplexed pin" {SDCD_SPDIF} 1]
set analog [exact_ports "Diablo analog aliases" {
    SDIO_CLK SDIO_CMD SDIO_DAT[0] SDIO_DAT[1] SDIO_DAT[2] SDIO_DAT[3] SD_SPI_CS
} 7]
set forbidden_outputs [exact_ports "forbidden output audit" {
    HDMI_I2C_SCL HDMI_I2C_SDA HDMI_I2S HDMI_LRCLK HDMI_SCLK IO_SCL IO_SDA
    USER_IO[2] USER_IO[4] USER_IO[5]
} 10]
set forbidden_inputs [exact_ports "forbidden input audit" {
    HDMI_TX_INT HDMI_I2C_SDA IO_SDA
} 3]
set mclk_before [exact_mclk_collections]
set mclk_source [lindex $mclk_before 1]

emit $summary "baseline_led_count" [get_collection_size $led]
emit $summary "baseline_led_names" [names $led]
emit $summary "baseline_sdcd_count" [get_collection_size $sdcd]
emit $summary "baseline_sdcd_names" [names $sdcd]
emit $summary "baseline_analog_count" [get_collection_size $analog]
emit $summary "baseline_analog_names" [names $analog]
emit $summary "baseline_forbidden_output_names" [names $forbidden_outputs]
emit $summary "baseline_forbidden_input_names" [names $forbidden_inputs]
emit $summary "baseline_mclk_source_period" [get_clock_info -period $mclk_source]
emit $summary "baseline_mclk_source_waveform" [get_clock_info -waveform $mclk_source]
emit $summary "baseline_setup" [timing_summary setup]
emit $summary "baseline_hold" [timing_summary hold]
emit $summary "baseline_internal_setup" [internal_timing_summary setup]
emit $summary "baseline_internal_hold" [internal_timing_summary hold]
emit_port_paths $summary baseline_from -from $sdcd
emit_port_paths $summary baseline_to -to [get_ports {LED[0] LED[2] LED[6] SDCD_SPDIF SDIO_CLK SDIO_CMD SDIO_DAT[0] SDIO_DAT[1] SDIO_DAT[2] SDIO_DAT[3] SD_SPI_CS}]
emit_port_paths $summary baseline_forbidden_to -to $forbidden_outputs
emit_port_paths $summary baseline_forbidden_from -from $forbidden_inputs
report_sdc -file $baseline_sdc_report

# Apply only the additions extracted from the working-tree Diablo.sdc.
read_sdc $additions
update_timing_netlist

set led_after [exact_ports "LED status vector after" {LED[0] LED[2] LED[6]} 3]
set sdcd_after [exact_ports "SDCD_SPDIF mode-multiplexed pin after" {SDCD_SPDIF} 1]
set analog_after [exact_ports "Diablo analog aliases after" {
    SDIO_CLK SDIO_CMD SDIO_DAT[0] SDIO_DAT[1] SDIO_DAT[2] SDIO_DAT[3] SD_SPI_CS
} 7]
set mclk_after [exact_mclk_collections]
set mclk_after_source [lindex $mclk_after 1]
set mclk_generated [get_clocks {HDMI_MCLK_FWD}]
if {[get_collection_size $mclk_generated] != 1} {
    error "C25 HDMI_MCLK_FWD expected one generated clock"
}

emit $summary "after_led_count" [get_collection_size $led_after]
emit $summary "after_led_names" [names $led_after]
emit $summary "after_sdcd_count" [get_collection_size $sdcd_after]
emit $summary "after_sdcd_names" [names $sdcd_after]
emit $summary "after_analog_count" [get_collection_size $analog_after]
emit $summary "after_analog_names" [names $analog_after]
emit $summary "after_mclk_generated_count" [get_collection_size $mclk_generated]
emit $summary "after_mclk_source_period" [get_clock_info -period $mclk_after_source]
emit $summary "after_mclk_source_waveform" [get_clock_info -waveform $mclk_after_source]
emit $summary "after_mclk_generated_period" [get_clock_info -period $mclk_generated]
emit $summary "after_mclk_generated_waveform" [get_clock_info -waveform $mclk_generated]
emit $summary "after_setup" [timing_summary setup]
emit $summary "after_hold" [timing_summary hold]
emit $summary "after_internal_setup" [internal_timing_summary setup]
emit $summary "after_internal_hold" [internal_timing_summary hold]
emit_port_paths $summary after_from -from $sdcd_after
emit_port_paths $summary after_to -to [get_ports {LED[0] LED[2] LED[6] SDCD_SPDIF SDIO_CLK SDIO_CMD SDIO_DAT[0] SDIO_DAT[1] SDIO_DAT[2] SDIO_DAT[3] SD_SPI_CS}]
emit_port_paths $summary after_forbidden_to -to $forbidden_outputs
emit_port_paths $summary after_forbidden_from -from $forbidden_inputs
report_sdc -file $after_sdc_report
emit $summary "status" pass
close $summary
delete_timing_netlist
project_close
''', encoding="utf-8")


def parse_summary(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" in line:
            key, value = line.split("\t", 1)
            result[key] = value
    return result


def parse_sta_report(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    counts: dict[str, dict[str, int]] = {}
    for line in lines:
        match = re.search(
            r"; Unconstrained (Input|Output) Ports\s*;\s*(\d+)\s*;\s*(\d+)\s*;",
            line,
        )
        if match:
            counts.setdefault(match.group(1).lower(), {
                "setup": int(match.group(2)),
                "hold": int(match.group(3)),
            })

    def port_rows(kind: str) -> list[str]:
        heading = f"; Unconstrained {kind} Ports"
        label = f"; {kind} Port"
        for index, line in enumerate(lines):
            if heading not in line or index + 2 >= len(lines) or label not in lines[index + 2]:
                continue
            rows: list[str] = []
            for row in lines[index + 4:]:
                if row.startswith("+"):
                    break
                match = re.match(r";\s*([^;]+?)\s*;", row)
                if match:
                    name = match.group(1).strip()
                    if name and name != f"{kind} Port":
                        rows.append(name)
            return rows
        return []

    return {
        "path": str(path),
        "sha256": sha256(path),
        "counts": counts,
        "input_ports": port_rows("Input"),
        "output_ports": port_rows("Output"),
    }


def parse_c25_sdc_report(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows: list[str] = []
    for index, line in enumerate(lines):
        if "c25-additions.sdc:" in line:
            rows.extend(lines[index:index + 3])
    forbidden = [
        "HDMI_I2C_SCL", "HDMI_I2C_SDA", "HDMI_I2S", "HDMI_LRCLK", "HDMI_SCLK",
        "IO_SCL", "IO_SDA", "HDMI_TX_INT", "USER_IO[2]", "USER_IO[4]", "USER_IO[5]",
    ]
    row_text = "\n".join(rows)
    return {
        "rows": rows,
        "forbidden_names_in_c25_rows": [name for name in forbidden if name in row_text],
    }


def parse_timing_corners(path: Path) -> list[dict[str, object]]:
    pattern = re.compile(
        r"Report Timing: Found (\d+) ([A-Za-z ]+) paths .*Worst case slack is ([^ ]+)"
    )
    corner = ""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Diablo timing corner:"):
            corner = line.split(":", 1)[1].strip()
        match = pattern.search(line)
        if match:
            rows.append({
                "corner": corner,
                "kind": match.group(2).strip(),
                "paths": int(match.group(1)),
                "worst_slack": match.group(3),
            })
    return rows


def validate_full_sta_metrics(path: Path) -> dict[str, object]:
    """Validate every full-STA corner's required worst-case slack metrics.

    Quartus writes one ``Info: Analyzing ... Model`` block per timing corner in
    ``Diablo.sta.rpt``.  The summary table near the front of the report only
    exposes the overall worst case, so validation deliberately consumes the
    per-corner diagnostics and fails closed when a corner or metric is absent,
    malformed, non-finite, or non-positive.
    """
    result: dict[str, object] = {
        "path": str(path),
        "sha256": None,
        "required_metrics": list(FULL_STA_METRICS),
        "corners": [],
        "failures": [],
        "ok": False,
    }
    if not path.is_file():
        result["failures"] = ["report-missing"]
        return result

    result["sha256"] = sha256(path)
    corner_pattern = re.compile(r"^Info:\s+Analyzing\s+(.+?)\s*$")
    metric_pattern = re.compile(
        r"^Info(?:\s+\([^)]*\))?:\s+Worst-case\s+"
        r"(setup|hold|recovery|removal|minimum pulse width)\s+slack\s+is\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$",
        re.IGNORECASE,
    )
    corners: list[dict[str, object]] = []
    parse_failures: list[str] = []
    current: dict[str, object] | None = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        corner_match = corner_pattern.match(line)
        if corner_match:
            current = {"name": corner_match.group(1).strip(), "metrics": {}}
            corners.append(current)
            continue
        metric_match = metric_pattern.match(line)
        if not metric_match:
            continue
        if current is None:
            parse_failures.append(f"line-{line_number}:metric-before-corner")
            continue
        metric_name = FULL_STA_METRIC_LABELS[metric_match.group(1).lower()]
        metrics = current["metrics"]
        assert isinstance(metrics, dict)
        if metric_name in metrics:
            parse_failures.append(f"{current['name']}:duplicate:{metric_name}")
            continue
        try:
            metric_value = float(metric_match.group(2))
        except ValueError:
            parse_failures.append(f"{current['name']}:invalid:{metric_name}")
            continue
        metrics[metric_name] = metric_value

    failures = list(parse_failures)
    if not corners:
        failures.append("no-full-sta-corners")
    for corner in corners:
        name = str(corner["name"])
        metrics = corner["metrics"]
        assert isinstance(metrics, dict)
        missing = [metric for metric in FULL_STA_METRICS if metric not in metrics]
        failures.extend(f"{name}:missing:{metric}" for metric in missing)
        for metric_name, value in metrics.items():
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                failures.append(f"{name}:non-finite:{metric_name}")
            elif value <= 0:
                failures.append(f"{name}:non-positive:{metric_name}:{value:g}")

    result["corners"] = corners
    result["failures"] = failures
    result["ok"] = bool(corners) and not failures
    return result


def compare_full_sta_metrics(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    """Reject missing corners or any full-STA worst-case slack regression."""
    failures: list[str] = []
    if not before.get("ok"):
        failures.append("baseline-full-sta-invalid")
    if not after.get("ok"):
        failures.append("after-full-sta-invalid")
    before_corners = {
        str(corner.get("name")): corner for corner in before.get("corners", [])
        if isinstance(corner, dict)
    }
    after_corners = {
        str(corner.get("name")): corner for corner in after.get("corners", [])
        if isinstance(corner, dict)
    }
    for corner_name in sorted(set(before_corners) | set(after_corners)):
        if corner_name not in before_corners:
            failures.append(f"unexpected-corner:{corner_name}")
            continue
        if corner_name not in after_corners:
            failures.append(f"missing-after-corner:{corner_name}")
            continue
        before_metrics = before_corners[corner_name].get("metrics", {})
        after_metrics = after_corners[corner_name].get("metrics", {})
        if not isinstance(before_metrics, dict) or not isinstance(after_metrics, dict):
            failures.append(f"{corner_name}:metrics-malformed")
            continue
        for metric_name in FULL_STA_METRICS:
            if metric_name not in before_metrics or metric_name not in after_metrics:
                failures.append(f"{corner_name}:comparison-missing:{metric_name}")
                continue
            before_value = before_metrics[metric_name]
            after_value = after_metrics[metric_name]
            if not isinstance(before_value, (int, float)) or not isinstance(after_value, (int, float)):
                failures.append(f"{corner_name}:comparison-invalid:{metric_name}")
            elif after_value < before_value - 1e-9:
                failures.append(
                    f"{corner_name}:regression:{metric_name}:{before_value:g}->{after_value:g}"
                )
    return {"ok": not failures, "failures": failures}


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def validate_existing_receipt(receipt_path: Path) -> int:
    """Re-check existing baseline/trial full-STA reports without running Quartus."""
    receipt_path = root_path(receipt_path).resolve()
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "fail", "receipt": str(receipt_path), "error": str(error)}, sort_keys=True))
        return 1

    reports: dict[str, dict[str, object]] = {}
    all_ok = True
    artifacts = receipt.get("artifacts", {})
    for label in ("baseline_sta_report", "after_sta_report"):
        entry = artifacts.get(label) if isinstance(artifacts, dict) else None
        if not isinstance(entry, dict) or not entry.get("path"):
            reports[label] = {"ok": False, "failures": ["receipt-artifact-missing"]}
            all_ok = False
            continue
        report = root_path(str(entry["path"])).resolve()
        metrics = validate_full_sta_metrics(report)
        expected_sha = entry.get("sha256")
        actual_sha = metrics.get("sha256")
        hash_ok = bool(expected_sha and actual_sha == expected_sha)
        if not hash_ok:
            failures = list(metrics.get("failures", []))
            failures.append("receipt-sha256-mismatch" if expected_sha else "receipt-sha256-missing")
            metrics["failures"] = failures
            metrics["ok"] = False
        reports[label] = metrics
        all_ok = all_ok and bool(metrics.get("ok"))

    comparison = compare_full_sta_metrics(
        reports.get("baseline_sta_report", {}), reports.get("after_sta_report", {})
    )
    all_ok = all_ok and bool(comparison["ok"])

    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    validation_receipt = ROOT / ".mister" / "evidence" / "receipts" / f"{run_id}-c25-validator-metrics.json"
    output = {
        "schema": "diablo-c25-validator-metrics-v1",
        "status": "pass" if all_ok else "fail",
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv],
        "source_receipt": {
            "path": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(receipt_path),
        },
        "validator": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "reports": reports,
        "full_sta_metrics_unchanged": comparison,
    }
    write_immutable(validation_receipt, output)
    print(json.dumps({
        "status": output["status"],
        "receipt": str(validation_receipt.relative_to(ROOT)).replace("\\", "/"),
        "receipt_sha256": sha256(validation_receipt),
        "reports": {label: {"ok": value.get("ok"), "corners": len(value.get("corners", [])), "failures": value.get("failures", [])}
                    for label, value in reports.items()},
    }, sort_keys=True))
    return 0 if all_ok else 1


def _self_test_fixture(values: dict[str, dict[str, float]], omit: tuple[str, str] | None = None) -> str:
    lines: list[str] = []
    for corner, metrics in values.items():
        lines.append(f"Info: Analyzing {corner}")
        for metric_name in FULL_STA_METRICS:
            if omit == (corner, metric_name):
                continue
            label = metric_name.replace("_", " ")
            lines.append(f"Info (332146): Worst-case {label} slack is {metrics[metric_name]:.3f}")
    return "\n".join(lines) + "\n"


def run_validator_self_test() -> int:
    """Exercise the full-STA validator with bounded positive/negative fixtures."""
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    fixture_dir = ROOT / ".work" / "c25" / "validator-self-test" / run_id
    fixture_dir.mkdir(parents=True, exist_ok=False)
    base_values = {
        "Slow 1100mV 100C Model": {metric: 1.0 + index for index, metric in enumerate(FULL_STA_METRICS)},
        "Fast 1100mV -40C Model": {metric: 2.0 + index for index, metric in enumerate(FULL_STA_METRICS)},
    }
    cases: list[dict[str, object]] = []

    def run_case(name: str, text: str, expected_ok: bool) -> None:
        path = fixture_dir / f"{name}.sta.rpt"
        path.write_text(text, encoding="utf-8")
        result = validate_full_sta_metrics(path)
        passed = bool(result["ok"]) == expected_ok
        cases.append({
            "name": name,
            "expected": "accept" if expected_ok else "reject",
            "observed": "accept" if result["ok"] else "reject",
            "passed": passed,
            "failures": result["failures"],
        })

    valid_text = _self_test_fixture(base_values)
    run_case("valid", valid_text, True)
    for metric_name in FULL_STA_METRICS:
        run_case(
            f"missing_{metric_name}",
            _self_test_fixture(base_values, ("Slow 1100mV 100C Model", metric_name)),
            False,
        )
    run_case("missing_data_empty", "", False)
    run_case("missing_data_malformed", "Info: Analyzing Slow 1100mV 100C Model\nnot a timing metric\n", False)
    for metric_name in FULL_STA_METRICS:
        values = {corner: dict(metrics) for corner, metrics in base_values.items()}
        values["Slow 1100mV 100C Model"][metric_name] = 0.0
        run_case(f"nonpositive_{metric_name}", _self_test_fixture(values), False)

    baseline_fixture = fixture_dir / "regression_baseline.sta.rpt"
    baseline_fixture.write_text(valid_text, encoding="utf-8")
    baseline_result = validate_full_sta_metrics(baseline_fixture)
    for metric_name in FULL_STA_METRICS:
        values = {corner: dict(metrics) for corner, metrics in base_values.items()}
        values["Slow 1100mV 100C Model"][metric_name] -= 0.5
        after_fixture = fixture_dir / f"regression_{metric_name}.sta.rpt"
        after_fixture.write_text(_self_test_fixture(values), encoding="utf-8")
        after_result = validate_full_sta_metrics(after_fixture)
        comparison = compare_full_sta_metrics(baseline_result, after_result)
        cases.append({
            "name": f"regression_{metric_name}",
            "expected": "reject",
            "observed": "accept" if comparison["ok"] else "reject",
            "passed": not comparison["ok"],
            "failures": comparison["failures"],
        })

    all_passed = all(bool(case["passed"]) for case in cases)
    receipt = ROOT / ".mister" / "evidence" / "receipts" / f"{run_id}-c25-validator-self-test.json"
    output = {
        "schema": "diablo-c25-validator-self-test-v1",
        "status": "pass" if all_passed else "fail",
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv],
        "validator": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "fixture_root": str(fixture_dir.relative_to(ROOT)).replace("\\", "/"),
        "case_count": len(cases),
        "cases": cases,
    }
    write_immutable(receipt, output)
    print(json.dumps({
        "status": output["status"],
        "case_count": len(cases),
        "failed_cases": [case["name"] for case in cases if not case["passed"]],
        "receipt": str(receipt.relative_to(ROOT)).replace("\\", "/"),
        "receipt_sha256": sha256(receipt),
    }, sort_keys=True))
    return 0 if all_passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quartus-sta", default=os.getenv("DIABLO_QUARTUS_STA", r"D:\q17\quartus\bin64\quartus_sta.exe"))
    parser.add_argument("--validate-receipt", type=Path,
                        help="revalidate reports named by an existing C25 receipt without running Quartus")
    parser.add_argument("--self-test", action="store_true",
                        help="run bounded positive/negative full-STA metric fixtures")
    args = parser.parse_args()
    if args.validate_receipt and args.self_test:
        parser.error("--validate-receipt and --self-test are mutually exclusive")
    if args.validate_receipt:
        return validate_existing_receipt(args.validate_receipt)
    if args.self_test:
        return run_validator_self_test()
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"missing immutable C34 snapshot: {SNAPSHOT}")
    source_before = snapshot_records()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    run_dir = ROOT / ".work" / "c25" / "runs" / run_id
    trial = run_dir / "fitted-trial"
    run_dir.mkdir(parents=True, exist_ok=False)
    additions = run_dir / "c25-additions.sdc"
    additions_text = extract_c25_additions(ROOT / "Diablo.sdc", additions)
    tcl = run_dir / "c25-trial.tcl"
    summary_path = run_dir / "summary.tsv"
    baseline_report = run_dir / "baseline.report_sdc.rpt"
    after_report = run_dir / "after.report_sdc.rpt"
    copy_snapshot(SNAPSHOT, trial)
    write_trial_tcl(tcl)
    command = [str(Path(args.quartus_sta).resolve()), "-t", str(tcl),
               str(trial), str(additions), str(summary_path),
               str(baseline_report), str(after_report)]
    completed = subprocess.run(command, cwd=run_dir, text=True, encoding="utf-8", errors="replace",
                                capture_output=True, check=False, timeout=900)
    quartus_log = run_dir / "quartus_sta.log"
    quartus_log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    full_sta_log = run_dir / "full-sta.log"
    timing_corners_log = run_dir / "timing-corners.log"
    full_sta_command: list[str] = []
    timing_corners_command: list[str] = []
    full_sta_completed: subprocess.CompletedProcess[str] | None = None
    timing_corners_completed: subprocess.CompletedProcess[str] | None = None
    full_sta_report = trial / "output_files" / "Diablo.sta.rpt"
    timing_corners_report = trial / "output_files" / "Diablo.timing_corners.rpt"
    if completed.returncode == 0 and summary_path.is_file():
        # Run the normal full STA report only in the disposable trial project.
        # The fitted C34 source tree remains the baseline input and is never a
        # Quartus working directory.
        shutil.copy2(ROOT / "Diablo.sdc", trial / "Diablo.sdc")
        full_sta_command = [str(Path(args.quartus_sta).resolve()), "Diablo", "--do_report_timing"]
        full_sta_completed = subprocess.run(
            full_sta_command, cwd=trial, text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False, timeout=900,
        )
        full_sta_log.write_text(full_sta_completed.stdout + full_sta_completed.stderr, encoding="utf-8")
        if full_sta_completed.returncode == 0:
            timing_script = trial / "support" / "scripts" / "report_fpga_timing.tcl"
            timing_corners_command = [str(Path(args.quartus_sta).resolve()), "-t", str(timing_script), "Diablo"]
            timing_corners_completed = subprocess.run(
                timing_corners_command, cwd=trial, text=True, encoding="utf-8", errors="replace",
                capture_output=True, check=False, timeout=900,
            )
            timing_corners_log.write_text(
                timing_corners_completed.stdout + timing_corners_completed.stderr, encoding="utf-8"
            )
    source_after = snapshot_records()
    summary = parse_summary(summary_path) if summary_path.is_file() else {}
    baseline_sta_report = parse_sta_report(SNAPSHOT / "output_files" / "Diablo.sta.rpt")
    after_sta_report = parse_sta_report(full_sta_report) if full_sta_report.is_file() else None
    baseline_full_sta_metrics = validate_full_sta_metrics(SNAPSHOT / "output_files" / "Diablo.sta.rpt")
    after_full_sta_metrics = validate_full_sta_metrics(full_sta_report)
    full_sta_metrics_valid = bool(
        baseline_full_sta_metrics["ok"] and after_full_sta_metrics["ok"]
    )
    full_sta_metrics_unchanged = compare_full_sta_metrics(
        baseline_full_sta_metrics, after_full_sta_metrics
    )
    baseline_timing_corners = parse_timing_corners(SNAPSHOT / "output_files" / "Diablo.timing_corners.rpt")
    after_timing_corners = parse_timing_corners(timing_corners_report) if timing_corners_report.is_file() else []
    timing_corners_unchanged = baseline_timing_corners == after_timing_corners
    expected_after_inputs = ["HDMI_I2C_SDA", "HDMI_TX_INT", "IO_SDA"]
    expected_after_outputs = [
        "HDMI_I2C_SCL", "HDMI_I2C_SDA", "HDMI_I2S", "HDMI_LRCLK", "HDMI_SCLK",
        "IO_SCL", "IO_SDA", "USER_IO[2]", "USER_IO[4]", "USER_IO[5]",
    ]
    unconstrained_check = {
        "baseline": baseline_sta_report,
        "after": after_sta_report,
        "expected_after_input_ports": expected_after_inputs,
        "expected_after_output_ports": expected_after_outputs,
        "after_matches_expected": bool(
            after_sta_report
            and after_sta_report["input_ports"] == expected_after_inputs
            and after_sta_report["output_ports"] == expected_after_outputs
            and after_sta_report["counts"].get("input") == {"setup": 3, "hold": 3}
            and after_sta_report["counts"].get("output") == {"setup": 10, "hold": 10}
        ),
        "forbidden_inputs_remain": bool(
            after_sta_report and set(expected_after_inputs).issubset(set(after_sta_report["input_ports"]))
        ),
        "forbidden_outputs_remain": bool(
            after_sta_report and set(expected_after_outputs).issubset(set(after_sta_report["output_ports"]))
        ),
    }
    c25_sdc_audit = parse_c25_sdc_report(after_report) if after_report.is_file() else {
        "rows": [], "forbidden_names_in_c25_rows": ["report-missing"]
    }
    no_unintended_port_exceptions = not c25_sdc_audit["forbidden_names_in_c25_rows"]
    internal_timing_unchanged = all(
        summary.get(before) == summary.get(after)
        for before, after in (
            ("baseline_setup", "after_setup"),
            ("baseline_hold", "after_hold"),
            ("baseline_internal_setup", "after_internal_setup"),
            ("baseline_internal_hold", "after_internal_hold"),
        )
    )
    mclk_waveform_preserved = (
        summary.get("baseline_mclk_source_period") == "40.682"
        and summary.get("after_mclk_generated_count") == "1"
        and summary.get("after_mclk_generated_period") == "40.682"
        and " ".join(summary.get("after_mclk_generated_waveform", "").split()) == "0.000 20.341"
    )
    status = "pass" if all((
        completed.returncode == 0,
        summary_path.is_file(),
        full_sta_completed is not None and full_sta_completed.returncode == 0,
        timing_corners_completed is not None and timing_corners_completed.returncode == 0,
        timing_corners_report.is_file(),
        source_before == source_after,
        timing_corners_unchanged,
        bool(unconstrained_check["after_matches_expected"]),
        bool(unconstrained_check["forbidden_inputs_remain"]),
        bool(unconstrained_check["forbidden_outputs_remain"]),
        no_unintended_port_exceptions,
        internal_timing_unchanged,
        mclk_waveform_preserved,
        full_sta_metrics_valid,
        full_sta_metrics_unchanged["ok"],
    )) else "fail"
    receipt = {
        "schema": "diablo-c25-sdc-trial-v1",
        "run_id": run_id,
        "status": status,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "quartus_sta": str(Path(args.quartus_sta).resolve()),
        "immutable_snapshot": str(SNAPSHOT),
        "immutable_snapshot_manifest_sha256": sha256(SNAPSHOT / ".mister" / "fpga-source-snapshot.json"),
        "snapshot_inputs_unchanged": source_before == source_after,
        "source": {
            "sdc": str((ROOT / "Diablo.sdc").relative_to(ROOT)),
            "sdc_sha256": sha256(ROOT / "Diablo.sdc"),
            "c25_additions_sha256": sha256(additions),
            "decision_packets": {
                "io_timing": sha256(ROOT / ".work/c34/C25_IO_TIMING_DECISION.md"),
                "hdmi_mclk": sha256(ROOT / ".work/c34/C25_HDMI_MCLK_CLOCK_DECISION.md"),
            },
        },
        "command": command,
        "full_sta_command": full_sta_command,
        "timing_corners_command": timing_corners_command,
        "artifacts": {
            "trial_root": str(trial.relative_to(ROOT)).replace("\\", "/"),
            "tcl": str(tcl.relative_to(ROOT)).replace("\\", "/"),
            "additions": str(additions.relative_to(ROOT)).replace("\\", "/"),
            "quartus_log": {"path": str(quartus_log.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(quartus_log)},
            "full_sta_log": {"path": str(full_sta_log.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(full_sta_log)} if full_sta_log.exists() else None,
            "timing_corners_log": {"path": str(timing_corners_log.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(timing_corners_log)} if timing_corners_log.exists() else None,
            "summary": {"path": str(summary_path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(summary_path)} if summary_path.exists() else None,
            "baseline_report_sdc": {"path": str(baseline_report.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(baseline_report)} if baseline_report.exists() else None,
            "after_report_sdc": {"path": str(after_report.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(after_report)} if after_report.exists() else None,
            "baseline_sta_report": {"path": str((SNAPSHOT / "output_files" / "Diablo.sta.rpt").relative_to(ROOT)).replace("\\", "/"), "sha256": baseline_sta_report["sha256"]},
            "after_sta_report": {"path": str(full_sta_report.relative_to(ROOT)).replace("\\", "/"), "sha256": after_sta_report["sha256"]} if after_sta_report else None,
            "timing_corners_report": {"path": str(timing_corners_report.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(timing_corners_report)} if timing_corners_report.exists() else None,
        },
        "summary": summary,
        "full_sta_metrics_before": baseline_full_sta_metrics,
        "full_sta_metrics_after": after_full_sta_metrics,
        "full_sta_metrics_valid": full_sta_metrics_valid,
        "full_sta_metrics_unchanged": full_sta_metrics_unchanged,
        "unconstrained_port_check": unconstrained_check,
        "c25_sdc_audit": c25_sdc_audit,
        "no_unintended_port_exceptions": no_unintended_port_exceptions,
        "timing_corners_before": baseline_timing_corners,
        "timing_corners_after": after_timing_corners,
        "timing_corners_unchanged": timing_corners_unchanged,
        "internal_timing_unchanged": internal_timing_unchanged,
        "mclk_waveform_preserved": mclk_waveform_preserved,
        "scope": "Read-only fitted-netlist C25 SDC trial: exact LED/SDCD/analog alias false paths plus HDMI_MCLK forwarded clock; no I2S, I2C, HDMI_TX_INT, USER_IO exceptions or external data delays.",
        "exit_code": completed.returncode,
        "full_sta_exit_code": full_sta_completed.returncode if full_sta_completed else None,
        "timing_corners_exit_code": timing_corners_completed.returncode if timing_corners_completed else None,
    }
    receipt_path = ROOT / ".mister" / "evidence" / "receipts" / f"{run_id}-c25-sdc-trial.json"
    write_immutable(receipt_path, receipt)
    print(json.dumps({"status": status, "receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
                      "receipt_sha256": sha256(receipt_path), "run_dir": str(run_dir.relative_to(ROOT)).replace("\\", "/"),
                      "source_snapshot_unchanged": source_before == source_after}, sort_keys=True))
    return 0 if status == "pass" and source_before == source_after else 1


if __name__ == "__main__":
    raise SystemExit(main())

import json
from pathlib import Path
import tempfile
import unittest

from support.scripts.analyze_presentation_trace import TraceError, analyze, load_trace


def trace_lines(records, dropped=0, invalid=0):
    header = {
        "schema": "diablo-presentation-trace-v1",
        "records": len(records),
        "dropped_records": dropped,
        "timing_invalid_records": invalid,
    }
    return "\n".join(json.dumps(value) for value in [header, *records]) + "\n"


class PresentationTraceTests(unittest.TestCase):
    def write_trace(self, contents):
        temporary = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        self.addCleanup(lambda: Path(temporary.name).unlink(missing_ok=True))
        temporary.write(contents)
        temporary.close()
        return Path(temporary.name)

    def test_analyze_reconciles_mixed_outcomes_and_nearest_rank_percentiles(self):
        path = self.write_trace(trace_lines([
            {"sequence": 0, "start_ns": 100, "finish_ns": 110, "elapsed_ns": 10,
             "timing_valid": True, "published": False, "backpressure": True, "outcome": "publish_failed"},
            {"sequence": 1, "start_ns": 120, "finish_ns": 140, "elapsed_ns": 20,
             "timing_valid": True, "published": True, "backpressure": False, "outcome": "frame_published"},
            {"sequence": 2, "start_ns": 0, "finish_ns": 0, "elapsed_ns": 0,
             "timing_valid": False, "published": False, "backpressure": False, "outcome": "runtime_unavailable"},
        ], invalid=1))
        result = analyze(path)
        self.assertTrue(result["trace_complete"])
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["published"], 1)
        self.assertEqual(result["backpressure"], 1)
        self.assertEqual(result["timing_invalid"], 1)
        self.assertEqual(result["outcomes"], {
            "frame_published": 1, "publish_failed": 1, "runtime_unavailable": 1,
        })
        self.assertEqual(result["present_duration_ns"]["p99"], 20)
        self.assertEqual(result["presentation_interval_ns"]["p99"], 20)

    def test_dropped_records_reject_acceptance_but_can_be_inspected(self):
        path = self.write_trace(trace_lines([
            {"sequence": 2, "start_ns": 100, "finish_ns": 110, "elapsed_ns": 10,
             "timing_valid": True, "published": True, "backpressure": False, "outcome": "frame_published"},
        ], dropped=2))
        with self.assertRaisesRegex(TraceError, "incomplete"):
            analyze(path)
        result = analyze(path, require_complete=False)
        self.assertFalse(result["trace_complete"])
        self.assertEqual(result["attempts"], 1)

    def test_invalid_timing_and_discontinuous_sequence_are_rejected(self):
        bad_timing = self.write_trace(trace_lines([
            {"sequence": 0, "start_ns": 20, "finish_ns": 10, "elapsed_ns": 1,
             "timing_valid": True, "published": False, "backpressure": False, "outcome": "publish_failed"},
        ]))
        with self.assertRaisesRegex(TraceError, "inconsistent timing"):
            load_trace(bad_timing)

        bad_sequence = self.write_trace(trace_lines([
            {"sequence": 1, "start_ns": 0, "finish_ns": 0, "elapsed_ns": 0,
             "timing_valid": False, "published": False, "backpressure": False, "outcome": "runtime_unavailable"},
        ], invalid=1))
        with self.assertRaisesRegex(TraceError, "discontinuous"):
            load_trace(bad_sequence)


if __name__ == "__main__":
    unittest.main()

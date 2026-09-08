"""Scene oracle receipts require matching metadata and complete exact captures."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("scene_oracle", ROOT / "scripts/scene_oracle.py")
oracle = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(oracle)


class SceneOracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.host, self.arm = root / "host", root / "arm"
        for directory in (self.host, self.arm):
            (directory / "frames").mkdir(parents=True)
        raw = struct.pack("<8sIIQQ", b"D8RGB001", 640, 480, 128, 6400) + bytes(768 + 640 * 480)
        for directory in (self.host, self.arm):
            (directory / "frames" / "frame-128.d8f").write_bytes(raw)
        (self.host / "run.json").write_text(json.dumps({
            "scenario": "town-v1", "campaign": "diablo", "passed": True,
            "demo_sha256": "demo", "executable_sha256": "host-bin",
        }))
        (self.arm / "run.json").write_text(json.dumps({
            "scenario": "town-v1", "campaign": "diablo", "status": "passed",
            "demo_sha256": "demo", "binary_sha256": "arm-bin",
        }))

    def test_exact_metadata_and_capture_pass(self):
        result = oracle.qualify(self.host, self.arm)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["scenario"]["frames_compared"], 1)
        self.assertEqual(result["comparison"]["equal"], True)

    def test_metadata_mismatch_fails(self):
        data = json.loads((self.arm / "run.json").read_text())
        data["demo_sha256"] = "different"
        (self.arm / "run.json").write_text(json.dumps(data))
        result = oracle.qualify(self.host, self.arm)
        self.assertEqual(result["status"], "fail")
        self.assertIn("run metadata differs: demo_sha256", result["errors"])

    def test_receipt_is_immutable(self):
        output = Path(self.temp.name) / "receipt.json"
        oracle._immutable_write(output, {"schema": oracle.SCHEMA})
        with self.assertRaises(RuntimeError):
            oracle._immutable_write(output, {"schema": oracle.SCHEMA, "changed": True})

    def test_role_aware_qualification_rejects_transport_binary_role(self):
        host = json.loads((self.host / "run.json").read_text())
        arm = json.loads((self.arm / "run.json").read_text())
        host["build_role"] = "host-reference"
        arm["build_role"] = "arm-transport"
        (self.host / "run.json").write_text(json.dumps(host))
        (self.arm / "run.json").write_text(json.dumps(arm))
        result = oracle.qualify(self.host, self.arm, host_role="host-reference", arm_role="arm-reference")
        self.assertEqual(result["status"], "fail")
        self.assertIn("ARM run build role is not arm-reference", result["errors"])

    def dungeon_records(self):
        for directory, side in ((self.host, "host"), (self.arm, "arm")):
            data = json.loads((directory / "run.json").read_text())
            data["scenario"] = "dungeon-v1"
            data["capture_start_logic_ms"] = 5000
            if side == "host":
                data["build_role"] = "host-reference"
            else:
                data["build_role"] = "arm-reference"
            if side == "arm":
                data["status"] = "passed"
            (directory / "run.json").write_text(json.dumps(data))
            (directory / "frames/frame-128.d8f.state.json").write_text(json.dumps({
                "schema": "diablo-capture-scene-state-v1", "frame": 128, "logic_ms": 6400,
                "level": 1, "player_level": 1, "player_active": True, "transition_complete": True,
            }))

    def test_dungeon_scenario_requires_typed_capture_boundary(self):
        self.dungeon_records()
        result = oracle.qualify(
            self.host, self.arm,
            host_role="host-reference", arm_role="arm-reference", scenario="dungeon-v1")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["scenario"]["name"], "dungeon-v1")

    def test_dungeon_scenario_rejects_missing_capture_boundary(self):
        host = json.loads((self.host / "run.json").read_text())
        arm = json.loads((self.arm / "run.json").read_text())
        host.update(scenario="dungeon-v1", build_role="host-reference")
        arm.update(scenario="dungeon-v1", build_role="arm-reference", status="passed")
        (self.host / "run.json").write_text(json.dumps(host))
        (self.arm / "run.json").write_text(json.dumps(arm))
        result = oracle.qualify(
            self.host, self.arm,
            host_role="host-reference", arm_role="arm-reference", scenario="dungeon-v1")
        self.assertEqual(result["status"], "fail")
        self.assertIn("host capture start is not 5000ms for dungeon-v1", result["errors"])

    def test_dungeon_label_cannot_admit_town_loading_or_mismatched_frame_state(self):
        self.dungeon_records()
        state_path = self.host / "frames/frame-128.d8f.state.json"
        original = json.loads(state_path.read_text())
        for field, value in (("level", 0), ("player_level", 0), ("transition_complete", False),
                             ("player_active", False), ("frame", 0), ("logic_ms", 1)):
            with self.subTest(field=field):
                state_path.write_text(json.dumps({**original, field: value}))
                result = oracle.qualify(self.host, self.arm, scenario="dungeon-v1")
                self.assertEqual("fail", result["status"])
                self.assertTrue(any("not a completed level-1" in e for e in result["errors"]))
        state_path.unlink()
        self.assertEqual("fail", oracle.qualify(self.host, self.arm, scenario="dungeon-v1")["status"])


if __name__ == "__main__":
    unittest.main()

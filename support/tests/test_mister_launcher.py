"""Exercise launcher ownership loss with real, isolated child processes."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from support.scripts import mister_launcher


class LinuxMemoryAdmissionTest(unittest.TestCase):
    def test_current_reserved_aperture_is_outside_linux_ram(self):
        ranges = mister_launcher._validate_linux_memory(
            0x3FE00000, "00000000-1fefffff : System RAM\n  00008000-00ffffff : Kernel code\n")
        self.assertEqual(ranges, [{"start": 0, "end_inclusive": 0x1FEFFFFF}])

    def test_kernel_allocating_full_ddr_is_rejected(self):
        with self.assertRaisesRegex(mister_launcher.LaunchError, "overlaps Linux"):
            mister_launcher._validate_linux_memory(0x3FE00000, "00000000-3fffffff : System RAM\n")

    def test_split_ram_and_boundary_overlap_are_rejected(self):
        for second in ("3fe00000-3fffffff", "3fdfffff-3fe00000"):
            with self.subTest(second=second), self.assertRaisesRegex(mister_launcher.LaunchError, "overlaps Linux"):
                mister_launcher._validate_linux_memory(
                    0x3FE00000, "00000000-1fefffff : System RAM\n" + second + " : System RAM\n")

    def test_hidden_missing_or_malformed_ram_cannot_authorize_mapping(self):
        for text in ("", "00000000-00000000 : System RAM", "bad : System RAM"):
            with self.subTest(text=text), self.assertRaises(mister_launcher.LaunchError):
                mister_launcher._validate_linux_memory(0x3FE00000, text)

    def test_transport_must_fit_physical_board_memory(self):
        for base in (-4096, 0x3FE00001, 0x3FE01000, 0x80000000):
            with self.subTest(base=base), self.assertRaises(mister_launcher.LaunchError):
                mister_launcher._validate_linux_memory(base, "00000000-1fefffff : System RAM")


@unittest.skipUnless(hasattr(os, "killpg"), "MiSTer process groups require POSIX")
class EngineOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.children = []

    def tearDown(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
        self.temporary.cleanup()

    def engine(self, name):
        ready = self.root / (name + ".ready")
        stopped = self.root / (name + ".stopped")
        code = (
            "import signal,time,sys\nfrom pathlib import Path\n"
            "def stop(*args):\n Path(sys.argv[2]).write_text('graceful')\n sys.exit(0)\n"
            "signal.signal(signal.SIGTERM,stop)\n"
            "Path(sys.argv[1]).write_text('ready')\n"
            "while True: time.sleep(0.05)\n"
        )
        child = subprocess.Popen([sys.executable, "-c", code, str(ready), str(stopped)],
                                 start_new_session=True)
        self.children.append(child)
        deadline = time.monotonic() + 5
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(ready.exists(), "test engine did not become ready")
        return child, stopped

    def test_unlimited_session_stops_own_engine_after_core_replacement(self):
        engine, stopped = self.engine("owned")
        foreign, foreign_stopped = self.engine("foreign")
        with mock.patch.object(mister_launcher, "_core_process_matches",
                               side_effect=[True, False]):
            result = mister_launcher._wait_for_engine(engine, Path("/package/Diablo.rbf"), 0)
        self.assertEqual((0, False, True), result)
        self.assertEqual("graceful", stopped.read_text())
        self.assertIsNone(foreign.poll(), "replacement workload must remain running")
        self.assertFalse(foreign_stopped.exists())

    def test_requested_duration_remains_distinct_from_core_loss(self):
        engine, stopped = self.engine("duration")
        with mock.patch.object(mister_launcher, "_core_process_matches", return_value=True):
            result = mister_launcher._wait_for_engine(engine, Path("/package/Diablo.rbf"), 0.1)
        self.assertEqual((0, True, False), result)
        self.assertEqual("graceful", stopped.read_text())

    def test_finished_engine_never_signals_another_process_group(self):
        child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"],
                                 start_new_session=True)
        self.children.append(child)
        child.wait(timeout=5)
        with mock.patch.object(mister_launcher.os, "killpg") as kill, \
                mock.patch.object(mister_launcher, "_core_process_matches") as matches:
            self.assertEqual((7, False, False),
                             mister_launcher._wait_for_engine(child, Path("/package/Diablo.rbf"), 0))
        kill.assert_not_called()
        matches.assert_not_called()


if __name__ == "__main__":
    unittest.main()

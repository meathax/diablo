"""Exercise launcher ownership loss with real, isolated child processes."""
import argparse
from pathlib import Path
import errno
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


class LanguagePersistenceTest(unittest.TestCase):
    def _args(self, lang=None):
        return argparse.Namespace(campaign="diablo", data_root=Path("/game-data"), lang=lang, engine_arg=[])

    def test_saved_in_game_language_is_not_overridden(self):
        command = mister_launcher._engine_args(
            self._args(), Path("/package"), Path("/save"), Path("/config"), Path("/log"))
        self.assertNotIn("--lang", command)

    def test_explicit_language_remains_a_one_run_override(self):
        command = mister_launcher._engine_args(
            self._args("pl"), Path("/package"), Path("/save"), Path("/config"), Path("/log"))
        position = command.index("--lang")
        self.assertEqual(command[position:position + 2], ["--lang", "pl"])


class CoreLoadRequestTest(unittest.TestCase):
    def test_unread_fifo_is_reported_without_blocking(self):
        unavailable = OSError(errno.ENXIO, "no reader")
        with mock.patch.object(mister_launcher.os, "open", side_effect=unavailable):
            self.assertFalse(mister_launcher._request_core_load(
                Path("/dev/MiSTer_cmd"), Path("/package/Diablo.rbf")))

    def test_fifo_request_is_written_as_one_ascii_command(self):
        with mock.patch.object(mister_launcher.os, "open", return_value=17) as opened, \
                mock.patch.object(mister_launcher.os, "write") as write, \
                mock.patch.object(mister_launcher.os, "close") as close:
            self.assertTrue(mister_launcher._request_core_load(
                Path("/dev/MiSTer_cmd"), Path("/package/Diablo.rbf")))
        opened.assert_called_once()
        expected = f"load_core {Path('/package/Diablo.rbf')}\n".encode("ascii")
        write.assert_called_once_with(17, expected)
        close.assert_called_once_with(17)

    def test_missing_frontend_is_started_with_the_requested_rbf(self):
        with tempfile.TemporaryDirectory() as temporary:
            frontend = Path(temporary) / "MiSTer"
            frontend.write_text("frontend")
            frontend.chmod(0o700)
            child = mock.Mock()
            with mock.patch.object(mister_launcher, "MISTER_FRONTEND_PATH", frontend), \
                    mock.patch.object(mister_launcher.subprocess, "Popen", return_value=child) as launch:
                self.assertIs(child, mister_launcher._start_frontend(Path("/package/Diablo.rbf")))
        launch.assert_called_once_with([str(frontend), str(Path("/package/Diablo.rbf"))],
                                       stdin=mister_launcher.subprocess.DEVNULL,
                                       stdout=mister_launcher.subprocess.DEVNULL,
                                       stderr=mister_launcher.subprocess.DEVNULL,
                                       start_new_session=True)

    def test_loader_starts_frontend_when_the_fifo_has_no_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            command_path = Path(temporary) / "MiSTer_cmd"
            command_path.touch()
            state = mock.Mock()
            state.read_text.return_value = "operating\n"
            frontend = mock.Mock()
            with mock.patch.object(mister_launcher, "_core_process_matches",
                                   side_effect=[False, True]), \
                    mock.patch.object(mister_launcher, "_frontend_process_present", return_value=False), \
                    mock.patch.object(mister_launcher, "_start_frontend", return_value=frontend) as start, \
                    mock.patch.object(mister_launcher, "Path", return_value=state), \
                    mock.patch.object(mister_launcher.time, "monotonic", side_effect=[0, 0]):
                mister_launcher._load_core(command_path, Path("/package/Diablo.rbf"), 1)
        start.assert_called_once_with(Path("/package/Diablo.rbf"))


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



@unittest.skipUnless(hasattr(os, "sched_getaffinity"), "requires Linux affinity")
class EngineAffinityTest(unittest.TestCase):
    def test_engine_and_new_thread_use_cpu0_without_changing_launcher(self):
        original = os.sched_getaffinity(0)
        if not {0, 1}.issubset(original):
            self.skipTest("requires CPUs 0 and 1 for MiSTer inheritance regression")
        code = (
            "import os,threading\n"
            "print(sorted(os.sched_getaffinity(0)), flush=True)\n"
            "t=threading.Thread(target=lambda: print(sorted(os.sched_getaffinity(0)), flush=True))\n"
            "t.start(); t.join()\n"
        )
        try:
            os.sched_setaffinity(0, {1})
            child = mister_launcher._start_engine(
                [sys.executable, "-c", code], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                output, errors = child.communicate(timeout=5)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
            self.assertEqual(child.returncode, 0, errors)
            self.assertEqual(output.splitlines(), ["[0]", "[0]"])
            self.assertEqual(os.sched_getaffinity(0), {1})
        finally:
            os.sched_setaffinity(0, original)

    def test_affinity_failure_does_not_run_engine_on_inherited_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "unexpected-engine"
            with mock.patch.object(mister_launcher.os, "sched_setaffinity",
                                   side_effect=OSError("affinity unavailable")):
                with self.assertRaises(subprocess.SubprocessError):
                    mister_launcher._start_engine(
                        [sys.executable, "-c", "from pathlib import Path; Path(__import__('sys').argv[1]).touch()", str(marker)])
            self.assertFalse(marker.exists())

if __name__ == "__main__":
    unittest.main()

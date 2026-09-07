"""The FPGA snapshot helper must copy complete inputs and refuse unsafe reuse."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "support" / "scripts" / "compile_fpga_snapshot.ps1"


def powershell() -> str | None:
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    return None


@unittest.skipUnless(powershell(), "PowerShell is required for FPGA snapshot tests")
class FpgaSnapshotTests(unittest.TestCase):
    def run_helper(self, destination: Path, action: str, *extra: str) -> subprocess.CompletedProcess[str]:
        command = [powershell(), "-NoProfile", "-File", str(SCRIPT),
                   "-SourceDirectory", str(destination), "-Action", action, *extra]
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", check=False)

    def temporary_snapshot(self):
        return tempfile.TemporaryDirectory(
            dir=ROOT / ".work" / "build", prefix="fpga snapshot test "
        )

    def test_sync_copies_complete_manifest_and_revalidates(self) -> None:
        with self.temporary_snapshot() as name:
            destination = Path(name)
            result = self.run_helper(destination, "sync")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = destination / ".mister" / "fpga-source-snapshot.json"
            self.assertTrue(manifest.is_file())
            self.assertTrue((destination / "sys" / "sys_top.v").is_file())
            self.assertTrue((destination / "rtl" / "native_test_pattern.sv").is_file())
            validation = self.run_helper(destination, "compile", "-QuartusRoot",
                                          str(destination / "missing-quartus"))
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Configured Quartus root does not exist", validation.stderr + validation.stdout)

    def test_sync_refuses_non_empty_destination(self) -> None:
        with self.temporary_snapshot() as name:
            destination = Path(name)
            marker = destination / "stale-file.txt"
            marker.write_text("must remain", encoding="utf-8")
            result = self.run_helper(destination, "sync")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-empty snapshot", result.stderr + result.stdout)
            self.assertEqual(marker.read_text(encoding="utf-8"), "must remain")

    def test_tampered_snapshot_is_rejected_before_quartus(self) -> None:
        with self.temporary_snapshot() as name:
            destination = Path(name)
            result = self.run_helper(destination, "sync")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            source = destination / "Diablo.sv"
            with source.open("ab") as stream:
                stream.write(b"\n// test tamper\n")
            validation = self.run_helper(destination, "compile", "-QuartusRoot",
                                          str(destination / "missing-quartus"))
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Snapshot files no longer match", validation.stderr + validation.stdout)


if __name__ == "__main__":
    unittest.main()

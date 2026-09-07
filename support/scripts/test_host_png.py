"""Run the host PNG regression from an explicitly configured CMake build tree."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", default=os.getenv("DIABLO_HOST_BUILD_DIR"))
    args = parser.parse_args()
    if not args.build_dir:
        raise SystemExit("--build-dir is required (or set DIABLO_HOST_BUILD_DIR)")
    build = Path(args.build_dir)
    if not (build / "CMakeCache.txt").is_file():
        raise SystemExit(f"not a configured CMake build directory: {build}")
    executable = build / "text_render_integration_test.exe"
    if not executable.is_file():
        raise SystemExit(f"host PNG test executable is missing: {executable}")
    registration = build / "text_render_integration_test[1]_tests.cmake"
    if not registration.is_file() or "HostPngLoading.EmptyPathReturnsNull" not in registration.read_text(
            encoding="utf-8", errors="replace"):
        raise SystemExit("configured build does not register the project HostPngLoading regression")
    ctest = shutil.which("ctest") or shutil.which("ctest.exe")
    if ctest is None:
        raise SystemExit("ctest is unavailable")
    subprocess.run([ctest, "--test-dir", str(build), "--output-on-failure", "-R", r"^HostPngLoading\."],
                   check=True)
    print("host PNG regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

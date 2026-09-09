"""Build the SDL transport-input regression with explicitly supplied SDL paths."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def windows_posix_shims(directory: Path) -> list[Path]:
    """Supply declarations only; the test exercises SDL's Windows backend."""
    directory.mkdir(parents=True, exist_ok=True)
    sys_directory = directory / "sys"
    sys_directory.mkdir(exist_ok=True)
    mman = sys_directory / "mman.h"
    file = sys_directory / "file.h"
    unistd = directory / "unistd.h"
    mman.write_text(
        "#pragma once\n#include <cstddef>\n#include <sys/types.h>\n"
        "#define PROT_READ 0x1\n#define PROT_WRITE 0x2\n#define MAP_SHARED 0x01\n"
        "#define MAP_FAILED reinterpret_cast<void *>(-1)\n#define MS_SYNC 0x4\n"
        "inline void *mmap(void *, std::size_t, int, int, int, off_t) { return MAP_FAILED; }\n"
        "inline int munmap(void *, std::size_t) { return 0; }\n"
        "inline int msync(void *, std::size_t, int) { return 0; }\n",
        encoding="utf-8")
    file.write_text(
        "#pragma once\n#define LOCK_EX 2\n#define LOCK_NB 4\n#define LOCK_UN 8\n"
        "inline int flock(int, int) { return 0; }\n", encoding="utf-8")
    unistd.write_text(
        "#pragma once\n#include <cstddef>\n#include <sys/types.h>\n#include <time.h>\n"
        "#define _SC_PAGESIZE 30\n#define O_CLOEXEC 0\n#define O_SYNC 0\n#define O_NOFOLLOW 0\n"
        "inline int close(int) { return 0; }\ninline off_t lseek(int, off_t, int) { return -1; }\n"
        "inline long sysconf(int) { return -1; }\ninline int getpid() { return 1; }\n"
        "inline ssize_t read(int, void *, std::size_t) { return -1; }\n",
        encoding="utf-8")
    return [directory]


def required(value: str | None, name: str) -> Path:
    if value is None or not value:
        raise SystemExit(f"{name} is required (or set its DIABLO_TRANSPORT_SDL_* environment variable)")
    path = Path(value)
    if not path.is_dir() and name != "--sdl-library":
        raise SystemExit(f"{name} is not a directory: {path}")
    if name == "--sdl-library" and not path.is_file():
        raise SystemExit(f"{name} is not a file: {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdl-build-include", default=os.getenv("DIABLO_TRANSPORT_SDL_BUILD_INCLUDE"))
    parser.add_argument("--sdl-source-include", default=os.getenv("DIABLO_TRANSPORT_SDL_SOURCE_INCLUDE"))
    parser.add_argument("--sdl-library", default=os.getenv("DIABLO_TRANSPORT_SDL_LIBRARY"))
    args = parser.parse_args()
    build_include = required(args.sdl_build_include, "--sdl-build-include")
    source_include = required(args.sdl_source_include, "--sdl-source-include")
    library = required(args.sdl_library, "--sdl-library")
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        raise SystemExit("no C++ compiler found")
    build = ROOT / ".work" / "build" / "transport-input"
    build.mkdir(parents=True, exist_ok=True)
    includes = [ROOT / "support" / "reference", build_include, source_include]
    if os.name == "nt":
        includes = windows_posix_shims(build / "posix") + includes
    command = [compiler, "-std=c++23", "-Wall", "-Wextra", "-Werror", "-Wno-error=maybe-uninitialized",
               "-DDIABLO_MISTER_INPUT_TEST"]
    for include in includes:
        command += ["-I", str(include)]
    link_flags = [str(library)]
    if os.name == "nt":
        link_flags += ["-lsetupapi", "-lole32", "-loleaut32", "-limm32", "-lgdi32", "-lwinmm",
                    "-lversion", "-luser32"]
    for name in ("mister_transport_input_test", "mister_gamepad_state_test",
                 "mister_virtual_gamepad_test"):
        executable = build / (name + ".exe")
        compile_command = command + [str(ROOT / "support" / "tests" / (name + ".cpp"))]
        compile_command += link_flags + ["-o", str(executable)]
        subprocess.run(compile_command, cwd=ROOT, check=True)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
    print("transport SDL input regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

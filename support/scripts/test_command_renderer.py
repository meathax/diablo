from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', default=None)
    args = parser.parse_args()
    compiler = args.compiler or shutil.which('g++') or shutil.which('clang++')
    if compiler is None:
        raise SystemExit('no C++ compiler found')
    build = ROOT / '.work' / 'build' / 'command-renderer'
    build.mkdir(parents=True, exist_ok=True)
    executable = build / 'mister_command_renderer_test.exe'
    command = [
        compiler,
        '-std=c++23', '-Wall', '-Wextra', '-Werror',
        '-I', str(ROOT / 'support' / 'reference'),
        str(ROOT / 'support' / 'tests' / 'mister_command_renderer_test.cpp'),
        '-o', str(executable),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    subprocess.run([str(executable)], cwd=ROOT, check=True)
    print('software command renderer test passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

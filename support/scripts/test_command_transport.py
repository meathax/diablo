from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    compiler = shutil.which('g++') or shutil.which('clang++')
    if compiler is None:
        raise SystemExit('no C++ compiler found')
    build = ROOT / '.work' / 'build' / 'command-renderer'
    build.mkdir(parents=True, exist_ok=True)
    executable = build / 'mister_command_transport_test.exe'
    subprocess.run([
        compiler, '-std=c++23', '-Wall', '-Wextra', '-Werror',
        '-I', str(ROOT / 'support' / 'reference'),
        str(ROOT / 'support' / 'tests' / 'mister_command_transport_test.cpp'),
        '-o', str(executable),
    ], cwd=ROOT, check=True)
    subprocess.run([str(executable)], cwd=ROOT, check=True)
    config_executable = build / 'mister_transport_config_test.exe'
    subprocess.run([
        compiler, '-std=c++23', '-Wall', '-Wextra', '-Werror',
        '-I', str(ROOT / 'support' / 'reference'),
        str(ROOT / 'support' / 'tests' / 'mister_transport_config_test.cpp'),
        '-o', str(config_executable),
    ], cwd=ROOT, check=True)
    subprocess.run([str(config_executable)], cwd=ROOT, check=True)
    admission_executable = build / 'mister_transport_admission_test.exe'
    subprocess.run([
        compiler, '-std=c++23', '-Wall', '-Wextra', '-Werror',
        '-I', str(ROOT / 'support' / 'reference'),
        str(ROOT / 'support' / 'tests' / 'mister_transport_admission_test.cpp'),
        '-o', str(admission_executable),
    ], cwd=ROOT, check=True)
    subprocess.run([str(admission_executable)], cwd=ROOT, check=True)
    print('command transport publication test passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

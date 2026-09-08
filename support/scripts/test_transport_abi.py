"""Build and run the generated transport ABI checks on host, RTL and ARM QEMU."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import diablo


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], commands: list[list[str]], *, cwd: Path | None = None, env: dict | None = None) -> None:
    print(' '.join(command), flush=True)
    commands.append(command)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def wsl_environment() -> dict:
    # The runner can execute under MSYS, which otherwise rewrites native WSL
    # paths such as /home/... before wsl.exe receives them.
    os.environ['MSYS_NO_PATHCONV'] = '1'
    os.environ['MSYS2_ARG_CONV_EXCL'] = '*'
    return os.environ.copy()


def wsl_command(arguments: list[str], distribution: str) -> list[str]:
    executable = shutil.which('wsl.exe') or shutil.which('wsl')
    if executable is None:
        raise RuntimeError('WSL is unavailable')
    return [executable, '-d', distribution, '--', *arguments]


def as_wsl_path(path: Path, environment: dict, distribution: str) -> str:
    source = str(path).replace('\\', '/')
    if os.name != 'nt':
        source = subprocess.check_output(['cygpath', '-m', source], text=True).strip()
    return subprocess.check_output(wsl_command(['wslpath', '-a', source], distribution),
                                   text=True, env=environment).strip()


def run_state_dump_diagnostic(root: Path, build: Path, cxx: str,
                              distribution: str | None,
                              commands: list[list[str]]) -> None:
    state_dump = build / 'transport_state_dump.exe'
    state_dump_test = build / 'transport_state_dump_test.exe'
    source = root / 'support/transport/transport_state_dump.cpp'
    test_source = root / 'support/tests/transport_state_dump_test.cpp'
    include = root / 'support/reference'
    if os.name != 'nt':
        run([cxx, '-std=c++23', '-Wall', '-Wextra', '-Werror', '-I', str(include),
             str(source), '-o', str(state_dump)], commands)
        run([cxx, '-std=c++23', '-Wall', '-Wextra', '-Werror', '-I', str(include),
             str(test_source), '-o', str(state_dump_test)], commands)
        run([str(state_dump_test), str(state_dump)], commands)
        return

    selected_distribution = distribution or 'Ubuntu'
    wsl_env = wsl_environment()
    source_wsl = as_wsl_path(source, wsl_env, selected_distribution)
    test_source_wsl = as_wsl_path(test_source, wsl_env, selected_distribution)
    include_wsl = as_wsl_path(include, wsl_env, selected_distribution)
    state_dump_wsl = as_wsl_path(state_dump, wsl_env, selected_distribution)
    state_dump_test_wsl = as_wsl_path(state_dump_test, wsl_env, selected_distribution)
    run(wsl_command(['g++', '-std=c++23', '-Wall', '-Wextra', '-Werror', '-I', include_wsl,
                     source_wsl, '-o', state_dump_wsl], selected_distribution),
        commands, env=wsl_env)
    run(wsl_command(['g++', '-std=c++23', '-Wall', '-Wextra', '-Werror', '-I', include_wsl,
                     test_source_wsl, '-o', state_dump_test_wsl], selected_distribution),
        commands, env=wsl_env)
    run(wsl_command([state_dump_test_wsl, state_dump_wsl], selected_distribution),
        commands, env=wsl_env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-arm', action='store_true')
    parser.add_argument('--diagnostic-only', action='store_true')
    parser.add_argument('--wsl-distribution', default=os.getenv('DIABLO_WSL_DISTRIBUTION'))
    parser.add_argument('--arm-cxx', default=os.getenv('DIABLO_ARM_CXX'))
    parser.add_argument('--arm-sysroot', default=os.getenv('DIABLO_ARM_SYSROOT'))
    parser.add_argument('--qemu', default=os.getenv('DIABLO_ARM_QEMU'))
    parser.add_argument('--arm-work-dir', default=os.getenv('DIABLO_ARM_WORK_DIR', '/tmp/diablo-verify'))
    args = parser.parse_args()
    root = diablo.ROOT
    commands: list[list[str]] = []
    python = Path(shutil.which('python') or shutil.which('python.exe') or '')
    if not python.is_file():
        raise RuntimeError('Python interpreter is unavailable')
    cxx = shutil.which('g++') or shutil.which('g++.exe')
    iverilog = shutil.which('iverilog') or shutil.which('iverilog.exe')
    vvp = shutil.which('vvp') or shutil.which('vvp.exe')
    if not cxx or (not args.diagnostic_only and (not iverilog or not vvp)):
        raise RuntimeError('g++ is required' if args.diagnostic_only else 'g++, iverilog and vvp are required')
    build = root / '.work/build/transport-abi'
    build.mkdir(parents=True, exist_ok=True)
    if args.diagnostic_only:
        run_state_dump_diagnostic(root, build, cxx, args.wsl_distribution, commands)
        print(json.dumps({'status': 'passed', 'checks': [
            'transport state dump file-backed output and missing/short/malformed fixture rejection']}))
        return 0
    run([str(python), str(root / 'support/scripts/generate_transport_abi.py'), '--check'], commands)
    native = build / 'transport_abi_test.exe'
    fixture = build / 'header.hex'
    run([cxx, '-std=c++23', '-Wall', '-Wextra', '-Werror', '-I', str(root / 'support/reference'),
         str(root / 'support/tests/transport_abi_test.cpp'), '-o', str(native)], commands)
    run([str(native), str(fixture)], commands)
    run_state_dump_diagnostic(root, build, cxx, args.wsl_distribution, commands)
    rtl = build / 'transport_abi_tb.vvp'
    run([iverilog, '-g2012', '-I', str(root / 'rtl'), '-s', 'transport_abi_tb', '-o', str(rtl),
         str(root / 'support/tests/transport_abi_tb.sv')], commands)
    run([vvp, str(rtl)], commands)
    ownership_rtl = build / 'frame-ownership.vvp'
    run([iverilog, '-g2012', '-I', str(root / 'rtl'), '-s', 'diablo_frame_ownership_tb', '-o', str(ownership_rtl),
         str(root / 'rtl/diablo_frame_ownership.sv'), str(root / 'support/tests/diablo_frame_ownership_tb.sv')], commands)
    run([vvp, str(ownership_rtl)], commands)
    if args.skip_arm:
        arm_status = 'not requested'
        runtime_status = 'not requested'
    else:
        required = {
            'DIABLO_WSL_DISTRIBUTION': args.wsl_distribution,
            'DIABLO_ARM_CXX': args.arm_cxx,
            'DIABLO_ARM_SYSROOT': args.arm_sysroot,
            'DIABLO_ARM_QEMU': args.qemu,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError('ARM/QEMU configuration is required: ' + ', '.join(missing))
        distribution = str(args.wsl_distribution)
        arm_cxx = str(args.arm_cxx)
        sysroot = str(args.arm_sysroot)
        qemu = str(args.qemu)
        work_dir = str(args.arm_work_dir)
        wsl_env = wsl_environment()
        source = as_wsl_path(root / 'support/tests/transport_abi_test.cpp', wsl_env, distribution)
        include = as_wsl_path(root / 'support/reference', wsl_env, distribution)
        arm_fixture = as_wsl_path(fixture, wsl_env, distribution)
        run(wsl_command(['mkdir', '-p', work_dir], distribution), commands, env=wsl_env)
        arm_binary = work_dir + '/transport-abi-test'
        run(wsl_command([arm_cxx, '-std=c++23', '-O2', '-mcpu=cortex-a9', '-mfpu=neon',
              '-mfloat-abi=hard', '-I', include, source, '-o', arm_binary], distribution), commands, env=wsl_env)
        run(wsl_command([qemu, '-cpu', 'cortex-a9', '-L', sysroot, arm_binary, arm_fixture],
                        distribution), commands, env=wsl_env)
        arm_status = 'passed under QEMU Cortex-A9 user-mode emulation'
        runtime_fixture = build / 'transport-runtime-memory.bin'
        with runtime_fixture.open('wb') as stream:
            stream.truncate(2 * 1024 * 1024)
        runtime_lock = build / 'transport-runtime.lock'
        runtime_lock.unlink(missing_ok=True)
        runtime_source = as_wsl_path(root / 'support/transport/transport_runtime_probe.cpp', wsl_env, distribution)
        runtime_memory = as_wsl_path(runtime_fixture, wsl_env, distribution)
        runtime_lock_path = as_wsl_path(runtime_lock, wsl_env, distribution)
        runtime_binary = work_dir + '/transport-runtime-probe'
        run(wsl_command([arm_cxx, '-std=c++23', '-O2', '-mcpu=cortex-a9', '-mfpu=neon',
              '-mfloat-abi=hard', '-static', '-I', include, runtime_source, '-o', runtime_binary],
                        distribution),
            commands, env=wsl_env)
        run(wsl_command(['env', 'DIABLO_MISTER_SHARED_PATH=' + runtime_memory,
              'DIABLO_MISTER_TRANSPORT_LOCK=' + runtime_lock_path,
              'DIABLO_MISTER_SESSION_EPOCH=0xB6020305', qemu, '-cpu', 'cortex-a9',
              '-L', sysroot, runtime_binary], distribution), commands, env=wsl_env)
        runtime_status = 'file-backed mapping and frame publication passed under QEMU Cortex-A9'
    evidence = {
        'schema': 'diablo-transport-abi-test-v1',
        'status': 'passed',
        'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'commands': commands,
        'inputs': {str(path.relative_to(root)): sha256(path) for path in (
            root / 'support/transport/transport_abi.json',
            root / 'support/scripts/generate_transport_abi.py',
            root / 'support/reference/transport_abi.hpp',
            root / 'support/reference/transport_input.hpp',
            root / 'support/reference/mister_transport.hpp',
            root / 'support/reference/mister_transport_runtime.hpp',
            root / 'rtl/diablo_transport_abi.svh',
            root / 'rtl/diablo_frame_ownership.sv',
            root / 'support/tests/transport_abi_test.cpp',
            root / 'support/transport/transport_state_dump.cpp',
            root / 'support/tests/transport_state_dump_test.cpp',
            root / 'support/transport/transport_runtime_probe.cpp',
            root / 'support/tests/transport_abi_tb.sv',
            root / 'support/tests/diablo_frame_ownership_tb.sv')},
        'fixture_sha256': sha256(fixture),
        'checks': [
            'generator freshness',
            'C++ record sizes, offsets, bounded attachment, epoch rejection, frame ownership, fault publication, input reduction and snapshot recovery',
            'transport state dump file-backed output and missing/short/malformed fixture rejection',
            'ARM transport session: indexed frame/palette publication, CRC metadata, slot backpressure and recycling',
            'ARM runtime mapping: explicit source selection, epoch initialization, file-backed frame publication and flush',
            'C++ walking-bit fixture decoded by RTL constants',
            'FPGA frame ownership: vblank-only switch, grant/deny, displayed-buffer protection, malformed/stale descriptor rejection',
            arm_status, runtime_status],
        'scope': 'Host/RTL and QEMU ARM ABI preparation. No shared-DDR reservation, cache-coherency, transport DMA or MiSTer hardware claim.'
    }
    diablo.write_json(root / '.mister/evidence/transport-abi-layout-test.json', evidence)
    print(json.dumps({'status': 'passed', 'receipt': '.mister/evidence/transport-abi-layout-test.json'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

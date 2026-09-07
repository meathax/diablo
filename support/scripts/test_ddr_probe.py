#!/usr/bin/env python3
"""Reproducibly verify the target DDR preflight on host, RTL, and ARM/QEMU."""
import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess


def run(command, commands, env=None):
    commands.append(command)
    subprocess.run(command, check=True, env=env)


def wsl_environment():
    # This runner may itself execute under MSYS. Do not let it rewrite native
    # WSL paths such as /mnt/d/... before wsl.exe receives them.
    os.environ['MSYS_NO_PATHCONV'] = '1'
    os.environ['MSYS2_ARG_CONV_EXCL'] = '*'
    return os.environ.copy()


def wsl_command(arguments):
    return ['C:/Windows/System32/wsl.exe', '-d', 'Ubuntu', '--', *arguments]


def as_wsl_path(path, environment):
    source_for_wslpath = str(path).replace('\\', '/')
    if os.name != 'nt':
        source_for_wslpath = subprocess.check_output(['cygpath', '-m', source_for_wslpath], text=True).strip()
    return subprocess.check_output(wsl_command(['wslpath', '-a', source_for_wslpath]), text=True, env=environment).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-arm', action='store_true')
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[2]
    build = root / '.work' / 'test-ddr-probe'
    build.mkdir(parents=True, exist_ok=True)
    commands = []

    rtl = build / 'diablo_ddr_probe_tb.vvp'
    run(['iverilog', '-g2012', '-s', 'diablo_ddr_probe_tb', '-o', str(rtl),
         str(root / 'rtl' / 'diablo_ddr_probe.sv'), str(root / 'support' / 'tests' / 'diablo_ddr_probe_tb.sv')], commands)
    run(['vvp', str(rtl)], commands)

    source = root / 'support' / 'transport' / 'transport_probe.cpp'
    include = root / 'support' / 'reference'
    wsl_env = wsl_environment()
    linux_source = as_wsl_path(source, wsl_env)
    linux_include = as_wsl_path(include, wsl_env)
    linux_binary = '/home/meath/.cache/diablo-transport-probe-host'
    run(wsl_command(['g++', '-std=c++23', '-O2', '-Wall', '-Wextra', '-I', linux_include,
                     linux_source, '-o', linux_binary]), commands, wsl_env)
    run(wsl_command([linux_binary, '--self-test']), commands, wsl_env)

    arm_status = 'not requested'
    if not args.skip_arm:
        arm_root = '/home/meath/.cache/diablo-toolchain-1.3.1/x-tools/armv7-neon-linux-gnueabihf'
        arm_cxx = arm_root + '/bin/armv7-neon-linux-gnueabihf-g++'
        sysroot = arm_root + '/armv7-neon-linux-gnueabihf/sysroot'
        qemu = '/home/meath/.cache/diablo-qemu/root/usr/bin/qemu-arm'
        arm_binary = as_wsl_path(build / 'transport-probe-arm', wsl_env)
        run(wsl_command([arm_cxx, '-std=c++23', '-O2', '-mcpu=cortex-a9', '-mfpu=neon',
             '-mfloat-abi=hard', '-static', linux_source, '-o', arm_binary]), commands, wsl_env)
        run(wsl_command([qemu, '-cpu', 'cortex-a9', '-L', sysroot, arm_binary, '--self-test']), commands, wsl_env)
        arm_status = 'passed under QEMU Cortex-A9 user-mode emulation'

    evidence = {
        'schema': 'diablo-ddr-probe-test-v1',
        'status': 'passed',
        'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'arm': arm_status,
        'commands': commands,
        'scope': 'RTL protocol and ARM mapping constants only; target hardware evidence is recorded separately.'
    }
    (root / '.mister' / 'evidence' / 'ddr-probe-test.json').write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()

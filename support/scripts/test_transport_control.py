#!/usr/bin/env python3
"""Verify ABI control-page attachment on host, RTL and ARM/QEMU."""
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
    build = root / '.work' / 'test-transport-control'
    build.mkdir(parents=True, exist_ok=True)
    commands = []

    run(['python', str(root / 'support/scripts/generate_transport_abi.py'), '--check'], commands)
    rtl = build / 'diablo_transport_control_reader_tb.vvp'
    run(['iverilog', '-g2012', '-I', str(root / 'rtl'), '-s', 'diablo_transport_control_reader_tb', '-o', str(rtl),
         str(root / 'rtl/diablo_transport_control_reader.sv'),
         str(root / 'support/tests/diablo_transport_control_reader_tb.sv')], commands)
    run(['vvp', str(rtl)], commands)

    scanout_rtl = build / 'diablo_framebuffer_scanout_tb.vvp'
    run(['iverilog', '-g2012', '-I', str(root / 'rtl'), '-s', 'diablo_framebuffer_scanout_tb', '-o', str(scanout_rtl),
         str(root / 'rtl/diablo_framebuffer_scanout.sv'),
         str(root / 'support/tests/diablo_framebuffer_scanout_tb.sv')], commands)
    run(['vvp', str(scanout_rtl)], commands)

    pcm_rtl = build / 'diablo_pcm_player_tb.vvp'
    run(['iverilog', '-g2012', '-I', str(root / 'rtl'), '-s', 'diablo_pcm_player_tb', '-o', str(pcm_rtl),
         str(root / 'rtl/diablo_pcm_player.sv'),
         str(root / 'support/tests/diablo_pcm_player_tb.sv')], commands)
    run(['vvp', str(pcm_rtl)], commands)

    pcm_long_rtl = build / 'diablo_pcm_player_long_tb.vvp'
    run(['iverilog', '-g2012', '-I', str(root / 'rtl'), '-s', 'diablo_pcm_player_long_tb', '-o', str(pcm_long_rtl),
         str(root / 'rtl/diablo_pcm_player.sv'),
         str(root / 'support/tests/diablo_pcm_player_long_tb.sv')], commands)
    run(['vvp', str(pcm_long_rtl)], commands)

    arbiter_rtl = build / 'diablo_transport_ddram_arbiter_tb.vvp'
    run(['iverilog', '-g2012', '-s', 'diablo_transport_ddram_arbiter_tb', '-o', str(arbiter_rtl),
         str(root / 'rtl/diablo_transport_ddram_arbiter.sv'),
         str(root / 'support/tests/diablo_transport_ddram_arbiter_tb.sv')], commands)
    run(['vvp', str(arbiter_rtl)], commands)

    input_rtl = build / 'diablo_input_capture_tb.vvp'
    run(['iverilog', '-g2012', '-I', str(root / 'rtl'), '-s', 'diablo_input_capture_tb', '-o', str(input_rtl),
         str(root / 'rtl/diablo_input_capture.sv'),
         str(root / 'support/tests/diablo_input_capture_tb.sv')], commands)
    run(['vvp', str(input_rtl)], commands)

    policy_rtl = build / 'diablo_video_source_policy_tb.vvp'
    run(['iverilog', '-g2012', '-s', 'diablo_video_source_policy_tb', '-o', str(policy_rtl),
         str(root / 'rtl/diablo_video_source_policy.sv'),
         str(root / 'support/tests/diablo_video_source_policy_tb.sv')], commands)
    run(['vvp', str(policy_rtl)], commands)

    source = root / 'support' / 'transport' / 'transport_header_probe.cpp'
    include = root / 'support' / 'reference'
    wsl_env = wsl_environment()
    linux_source = as_wsl_path(source, wsl_env)
    linux_include = as_wsl_path(include, wsl_env)
    linux_binary = '/home/meath/.cache/diablo-transport-header-probe-host'
    run(wsl_command(['g++', '-std=c++23', '-O2', '-Wall', '-Wextra', '-I', linux_include,
                     linux_source, '-o', linux_binary]), commands, wsl_env)
    run(wsl_command([linux_binary, '--self-test']), commands, wsl_env)

    arm_status = 'not requested'
    if not args.skip_arm:
        arm_root = '/home/meath/.cache/diablo-toolchain-1.3.1/x-tools/armv7-neon-linux-gnueabihf'
        arm_cxx = arm_root + '/bin/armv7-neon-linux-gnueabihf-g++'
        sysroot = arm_root + '/armv7-neon-linux-gnueabihf/sysroot'
        qemu = '/home/meath/.cache/diablo-qemu/root/usr/bin/qemu-arm'
        arm_binary = as_wsl_path(build / 'transport-header-probe-arm', wsl_env)
        run(wsl_command([arm_cxx, '-std=c++23', '-O2', '-mcpu=cortex-a9', '-mfpu=neon',
                         '-mfloat-abi=hard', '-static', '-I', linux_include, linux_source, '-o', arm_binary]), commands, wsl_env)
        run(wsl_command([qemu, '-cpu', 'cortex-a9', '-L', sysroot, arm_binary, '--self-test']), commands, wsl_env)
        arm_status = 'passed under QEMU Cortex-A9 user-mode emulation'

    evidence = {
        'schema': 'diablo-transport-control-test-v1',
        'status': 'passed',
        'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'arm': arm_status,
        'commands': commands,
        'scope': 'ABI identity, frame-descriptor validation, indexed palette staging and vblank-delayed frame ownership. Board evidence is recorded separately after a timing-clean RBF is loaded.'
    }
    (root / '.mister' / 'evidence' / 'transport-control-test.json').write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()

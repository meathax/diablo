"""Run the pinned shareware regression under ARM user-mode emulation, not MiSTer."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', default='/home/meath/.cache/diablo-arm-engine-portable')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    qemu = '/home/meath/.cache/diablo-qemu/root/usr/bin/qemu-arm'
    sysroot = ('/home/meath/.cache/diablo-toolchain-1.3.1/x-tools/'
               'armv7-neon-linux-gnueabihf/armv7-neon-linux-gnueabihf/sysroot')
    executable = args.build_dir.rstrip('/') + '/devilutionx'
    binary_hash = subprocess.check_output(
        ['wsl', '-d', 'Ubuntu', '--', 'sha256sum', executable], text=True).split()[0]
    runtime = ROOT / '.work/runtime/arm-replays' / uuid.uuid4().hex
    runtime.mkdir(parents=True)
    fixture = ROOT / '.work/sources/devilutionx/test/fixtures/timedemo/WarriorLevel1to2'
    inputs = {}
    for name in ('demo_0.dmo', 'spawn_0.sv', 'demo_0_reference_spawn_0.sv'):
        shutil.copyfile(fixture / name, runtime / name)
        inputs[name] = hashlib.sha256((runtime / name).read_bytes()).hexdigest()
    (runtime / 'diablo.ini').write_text(
        '[Graphics]\nFullscreen=0\nFit to Screen=0\nUpscale=0\n', encoding='utf-8')

    def linux_path(path):
        return subprocess.check_output(
            ['wsl', '-d', 'Ubuntu', '--', 'wslpath', '-a', path.as_posix()], text=True).strip()

    output_dir = linux_path(runtime)
    # Linux timeout owns the emulator process; no orphaned ARM process on expiry.
    command = ['wsl', '-d', 'Ubuntu', '--cd', args.build_dir, '--', 'env',
               '-u', 'DIABLO_NATIVE_SCENARIO', '-u', 'DIABLO_CAPTURE_DIR',
               'SDL_VIDEODRIVER=dummy', 'SDL_RENDER_DRIVER=software', 'SDL_AUDIODRIVER=dummy',
               'timeout', '--signal=TERM', '--kill-after=10s', str(args.timeout) + 's',
               qemu, '-cpu', 'cortex-a9', '-L', sysroot, executable,
               '--diablo', '--spawn', '--demo', '0', '--timedemo',
               '--data-dir', linux_path(ROOT / 'game'), '--save-dir', output_dir,
               '--config-dir', output_dir, '--lang', 'en', '-n', '--verbose',
               '--log-to-file', output_dir + '/engine.log']
    record = {'status': 'running', 'command': command, 'binary_sha256': binary_hash,
              'fixture_sha256': inputs, 'engine_headless_mode': False,
              'scope': 'Emulated ARM shareware replay; fixture resolution; no native640 capture or hardware/FPS claim',
              'started_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    receipt = runtime / 'run.json'
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    print(f'ARM replay output: {runtime}', flush=True)
    with (runtime / 'console.log').open('wb') as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
    log_path = runtime / 'engine.log'
    log = log_path.read_text(errors='replace') if log_path.exists() else ''
    passed = result.returncode == 0 and 'Timedemo: Same outcome as initial run.' in log
    record.update(status='passed' if passed else 'failed', exit_code=result.returncode,
                  replay_outcome_matches=passed,
                  finished_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'receipt': str(receipt), 'status': record['status']}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

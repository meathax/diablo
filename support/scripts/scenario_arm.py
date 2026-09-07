"""Capture native640 full-campaign reference scenes under ARM emulation."""
import argparse
import json
import subprocess
import uuid

import diablo
from compare_frames import read_frame
from scenario_host import scenario_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', choices=('diablo', 'hellfire'))
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    build = '/home/meath/.cache/diablo-arm-engine-portable'
    qemu = '/home/meath/.cache/diablo-qemu/root/usr/bin/qemu-arm'
    sysroot = ('/home/meath/.cache/diablo-toolchain-1.3.1/x-tools/'
               'armv7-neon-linux-gnueabihf/armv7-neon-linux-gnueabihf/sysroot')
    runtime = diablo.ROOT / '.work/runtime/arm-scenarios' / uuid.uuid4().hex
    runtime.mkdir(parents=True)

    def linux(path):
        return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--', 'wslpath', '-a',
                                        path.as_posix()], text=True).strip()

    output_dir = linux(runtime)
    if args.campaign == 'hellfire':
        (runtime / 'mods').mkdir()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--', 'cp', '-r', build + '/mods/hf',
                        output_dir + '/mods/hf'], check=True)
        if not (runtime / 'mods/hf/manifest.ini').is_file():
            parser.error('Missing bundled Hellfire mod')
    (runtime / 'demo_0.dmo').write_bytes(scenario_demo())
    (runtime / 'diablo.ini').write_text(
        '[Graphics]\nWidth=640\nHeight=480\nFullscreen=0\nFit to Screen=0\nUpscale=0\n')
    binary_hash = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--', 'sha256sum',
                                          build + '/devilutionx'], text=True).split()[0]
    command = ['wsl', '-d', 'Ubuntu', '--cd', build, '--', 'env',
               'DIABLO_NATIVE_SCENARIO=town-v1', 'DIABLO_CAPTURE_DIR=' + output_dir + '/frames',
               'SDL_VIDEODRIVER=dummy', 'SDL_RENDER_DRIVER=software', 'SDL_AUDIODRIVER=dummy',
               'timeout', '--signal=TERM', '--kill-after=10s', str(args.timeout) + 's',
               qemu, '-cpu', 'cortex-a9', '-L', sysroot, build + '/devilutionx',
               '--' + args.campaign, '--demo', '0', '--timedemo',
               '--data-dir', linux(diablo.ROOT / 'game'), '--save-dir', output_dir,
               '--config-dir', output_dir, '--lang', 'en', '-n', '--verbose',
               '--log-to-file', output_dir + '/engine.log']
    record = {'status': 'running', 'campaign': args.campaign, 'scenario': 'town-v1',
              'command': command, 'binary_sha256': binary_hash,
              'demo_sha256': diablo.sha256(runtime / 'demo_0.dmo'),
              'scope': 'ARM emulation, real drawing at native640; not hardware or FPS qualification'}
    diablo.write_json(runtime / 'run.json', record)
    print(f'ARM scenario output: {runtime}', flush=True)
    with (runtime / 'console.log').open('wb') as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
    log_path = runtime / 'engine.log'
    log = log_path.read_text(errors='replace') if log_path.exists() else ''
    errors = []
    marker = f'Native scenario town-v1 complete: campaign={args.campaign}, ticks=512,'
    if result.returncode or marker not in log or 'Demo queue empty' in log:
        errors.append('Scenario did not complete and quit normally')
    if not (runtime / 'single_0.sv').is_file():
        errors.append('Missing full-campaign save')
    captures = []
    for path in sorted((runtime / 'frames').glob('*.d8f')):
        try:
            frame = read_frame(path)
            captures.append({'file': path.name, 'sha256': frame['sha256'],
                             'frame': frame['frame'], 'logic_ms': frame['logic_ms']})
        except ValueError as error:
            errors.append(str(error))
    if len(captures) < 4 or list((runtime / 'frames').glob('*.partial')):
        errors.append('Missing or incomplete captures')
    record.update(status='passed' if not errors else 'failed', exit_code=result.returncode,
                  captures=captures, errors=errors)
    diablo.write_json(runtime / 'run.json', record)
    print(json.dumps({'status': record['status'], 'errors': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())

"""Run a fresh full-campaign native640 town smoke scenario via engine replay APIs."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import shutil
import uuid

import diablo
from compare_frames import read_frame


def scenario_demo():
    # Pinned replay v3: slot, native resolution, 23 gameplay option bytes.
    data = bytearray(struct.pack('<BIHH', 3, 0, 640, 480) + bytes(23))
    data.extend(struct.pack('<BBHH', 9, 0, 320, 180))
    for tick in range(512):
        # Exercise inventory and character rendering through normal game handlers.
        if tick in (128, 256, 320, 448):
            key = ord('i') if tick in (128, 256) else ord('c')
            for event in (13, 14):
                data.extend(struct.pack('<BBIH', event, 0, key, 0))
        data.extend(bytes((0, 0)))
    # The pinned SDL2 replay decoder does not map QuitEvent (8). Use the normal
    # game menu: Escape opens Options, Up wraps to Quit Game, Return activates it.
    for key in (27, 1073741906, 13):
        for event in (13, 14):
            data.extend(struct.pack('<BBIH', event, 0, key, 0))
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', choices=('diablo', 'hellfire'))
    parser.add_argument('--build-dir', default='.work/build/reference-host')
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    root = diablo.ROOT
    build = (root / args.build_dir).resolve()
    executable = build / 'devilutionx.exe'
    runtime = root / '.work/runtime/scenarios' / uuid.uuid4().hex
    runtime.mkdir(parents=True)
    mod_inputs = {}
    if args.campaign == 'hellfire':
        # With a separate --data-dir, loose bundled mods must be discoverable
        # beneath PrefPath; finding hellfire.mpq alone does not activate Hellfire.
        mod_source = build / 'mods/hf'
        if not (mod_source / 'manifest.ini').is_file():
            parser.error('Build lacks the bundled Hellfire mod')
        shutil.copytree(mod_source, runtime / 'mods/hf')
        mod_inputs = {p.relative_to(runtime).as_posix(): diablo.sha256(p)
                      for p in (runtime / 'mods/hf').rglob('*') if p.is_file()}
    (runtime / 'demo_0.dmo').write_bytes(scenario_demo())
    (runtime / 'diablo.ini').write_text(
        '[Graphics]\nWidth=640\nHeight=480\nFullscreen=0\nFit to Screen=0\nUpscale=0\n',
        encoding='utf-8')
    recipe = json.loads((root / 'support/host-reference.json').read_text())
    env = dict(os.environ)
    env.update(DIABLO_NATIVE_SCENARIO='town-v1', DIABLO_CAPTURE_DIR=str(runtime / 'frames'),
               SDL_VIDEODRIVER='dummy', SDL_RENDER_DRIVER='software', SDL_AUDIODRIVER='dummy')
    env['PATH'] = str(Path(recipe['toolchain_prefix']) / 'bin') + os.pathsep + env['PATH']
    command = [str(executable), '--' + args.campaign, '--demo', '0', '--timedemo',
               '--data-dir', str(root / 'game'), '--save-dir', str(runtime),
               '--config-dir', str(runtime), '--lang', 'en', '-n', '--verbose',
               '--log-to-file', str(runtime / 'engine.log')]
    record = {'scenario': 'town-v1', 'build_role': 'host-reference', 'campaign': args.campaign, 'command': command,
              'mod_sha256': mod_inputs,
              'executable_sha256': diablo.sha256(executable),
              'demo_sha256': diablo.sha256(runtime / 'demo_0.dmo'),
              'runner_sha256': diablo.sha256(Path(__file__)),
              'engine_headless_mode': False, 'timing': 'accelerated replay; not FPS evidence',
              'scope': 'Fresh hero, town simulation, inventory/character panels, indexed capture and save; not campaign completion or hardware qualification',
              'data_sha256': {p.name: diablo.sha256(p) for p in (root / 'game').iterdir()
                              if p.is_file() and p.suffix.lower() == '.mpq'}}
    print(f'Scenario output: {runtime}', flush=True)
    with (runtime / 'console.log').open('wb') as output:
        process = subprocess.Popen(command, cwd=build, env=env, stdout=output,
                                   stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        record.update(status='running', pid=process.pid)
        diablo.write_json(runtime / 'run.json', record)
        try:
            record.update(exit_code=process.wait(timeout=args.timeout), status='exited')
        except subprocess.TimeoutExpired:
            process.kill()
            record.update(exit_code=process.wait(), status='timed-out')
    errors = []
    log_path = runtime / 'engine.log'
    log = log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else ''
    marker = f'Native scenario town-v1 complete: campaign={args.campaign}, ticks=512,'
    if record['exit_code'] != 0 or marker not in log:
        errors.append('Scenario did not complete its engine state checks')
    if 'Demo queue empty' in log:
        errors.append('Replay exhausted without a clean quit')
    # This pinned revision registers a loose bundled hf as a builtin identity
    # without its manifest extension, so both isolated campaigns use .sv.
    save_name = 'single_0.sv'
    if not (runtime / save_name).is_file():
        errors.append('No full-campaign save was written')
    captures = []
    for path in sorted((runtime / 'frames').glob('*.d8f')):
        try:
            frame = read_frame(path)
            captures.append({'file': path.name, 'sha256': frame['sha256'],
                             'frame': frame['frame'], 'logic_ms': frame['logic_ms']})
        except ValueError as error:
            errors.append(str(error))
    if len(captures) < 4 or list((runtime / 'frames').glob('*.partial')):
        errors.append('Missing or incomplete native captures')
    record.update(captures=captures, errors=errors, passed=not errors,
                  output_sha256={p.name: diablo.sha256(p) for p in runtime.iterdir()
                                 if p.is_file() and p.name != 'run.json'})
    diablo.write_json(runtime / 'run.json', record)
    print(json.dumps({'passed': not errors, 'captures': len(captures), 'errors': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())

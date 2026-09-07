"""Run the pinned upstream shareware replay without desktop automation."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct
import uuid

import diablo
from compare_frames import read_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offscreen', action='store_true',
                        help='Use SDL dummy video/audio drivers; engine drawing stays enabled')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--timedemo', action='store_true',
                        help='Accelerate simulation regression; draws at game ticks, not normal presentation cadence')
    parser.add_argument('--capture-frames', action='store_true',
                        help='Require indexed captures from an engine built with the host capture hook')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    root = diablo.ROOT
    build = root / '.work/build/reference-host'
    executable = build / 'devilutionx.exe'
    fixture = root / '.work/sources/devilutionx/test/fixtures/timedemo/WarriorLevel1to2'
    demo_bytes = (fixture / 'demo_0.dmo').read_bytes()
    header = demo_bytes[:9]
    version, save_slot, width, height = struct.unpack('<BIHH', header)
    if version != 3 or save_slot != 0:
        parser.error('Unexpected upstream replay format or save slot')
    if args.capture_frames and (width, height) != (640, 480):
        parser.error(f'Fixture records {width}x{height}; native captures require a 640x480 replay. No resizing is performed.')
    runtime = root / '.work/runtime/replays' / uuid.uuid4().hex
    runtime.mkdir(parents=True)
    inputs = {}
    for name in ('demo_0.dmo', 'spawn_0.sv', 'demo_0_reference_spawn_0.sv'):
        shutil.copyfile(fixture / name, runtime / name)
        if name == 'demo_0.dmo':
            (runtime / name).write_bytes(demo_bytes)
        inputs[name] = diablo.sha256(runtime / name)
    (runtime / 'diablo.ini').write_text(
        '[Graphics]\nWidth=640\nHeight=480\nFullscreen=0\nFit to Screen=0\nUpscale=0\n',
        encoding='utf-8')
    command = [str(executable), '--diablo', '--spawn', '--demo', '0',
               '--data-dir', str(root / 'game'), '--save-dir', str(runtime),
               '--config-dir', str(runtime), '--lang', 'en', '-n', '--verbose',
               '--log-to-file', str(runtime / 'engine.log')]
    if args.timedemo:
        command.append('--timedemo')
    env = dict(os.environ)
    env.pop('DIABLO_CAPTURE_DIR', None)
    if args.capture_frames:
        env['DIABLO_CAPTURE_DIR'] = str(runtime / 'frames')
    recipe = json.loads((root / 'support/host-reference.json').read_text())
    env['PATH'] = str(Path(recipe['toolchain_prefix']) / 'bin') + os.pathsep + env['PATH']
    if args.offscreen:
        env.update(SDL_VIDEODRIVER='dummy', SDL_RENDER_DRIVER='software', SDL_AUDIODRIVER='dummy')
    record = {'fixture': 'WarriorLevel1to2', 'fixture_sha256': inputs,
              'executable_sha256': diablo.sha256(executable), 'command': command,
              'offscreen': args.offscreen, 'engine_headless_mode': False,
              'timing_mode': 'accelerated game-tick rendering' if args.timedemo else 'normal replay pacing',
              'capture_requested': args.capture_frames,
              'recorded_resolution': [width, height],
              'scope': 'Upstream shareware replay; not full-campaign, display/audio, or FPS qualification',
              'started_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    print(f'Replay output: {runtime}', flush=True)
    with (runtime / 'console.log').open('wb') as output:
        process = subprocess.Popen(command, cwd=build, env=env, stdout=output,
                                   stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        record.update(pid=process.pid, status='running')
        diablo.write_json(runtime / 'run.json', record)
        try:
            record['exit_code'] = process.wait(timeout=args.timeout)
            record['status'] = 'exited'
        except subprocess.TimeoutExpired:
            process.kill()
            record.update(status='timed-out', exit_code=process.wait())
    log = (runtime / 'engine.log').read_text(encoding='utf-8', errors='replace') if (runtime / 'engine.log').exists() else ''
    record['replay_outcome_matches'] = record['exit_code'] == 0 and 'Timedemo: Same outcome as initial run.' in log
    captures = sorted((runtime / 'frames').glob('*.d8f'))
    record['captures'] = []
    capture_errors = []
    for capture in captures:
        try:
            frame = read_frame(capture)
            record['captures'].append({'file': capture.name, 'sha256': frame['sha256'],
                                       'frame': frame['frame'], 'logic_ms': frame['logic_ms']})
        except ValueError as error:
            capture_errors.append(str(error))
    if list((runtime / 'frames').glob('*.partial')):
        capture_errors.append('Incomplete capture files remain')
    if args.capture_frames and not captures:
        capture_errors.append('No frames captured; verify the executable includes the host capture hook')
    record['capture_errors'] = capture_errors
    record['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    record['output_sha256'] = {p.name: diablo.sha256(p) for p in runtime.iterdir() if p.is_file() and p.name != 'run.json'}
    diablo.write_json(runtime / 'run.json', record)
    print(json.dumps({'status': record['status'], 'replay_outcome_matches': record['replay_outcome_matches'],
                      'captured_frames': len(record['captures']), 'capture_errors': capture_errors}))
    return 0 if record['replay_outcome_matches'] and not capture_errors else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Run one host campaign with private, isolated configuration and saves."""
import argparse
from pathlib import Path
import os
import subprocess
import datetime as dt
import shutil

import diablo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', choices=['diablo', 'hellfire'])
    args = parser.parse_args()
    root = diablo.ROOT
    executable = root / '.work/build/reference-host/devilutionx.exe'
    if not executable.is_file() or executable.stat().st_size == 0:
        raise RuntimeError('Host executable has not finished building')
    runtime = root / '.work/runtime' / args.campaign
    config, saves = runtime / 'config', runtime / 'saves'
    for directory in (config, saves):
        directory.mkdir(parents=True, exist_ok=True)
    mod_hashes = {}
    if args.campaign == 'hellfire':
        source = executable.parent / 'mods/hf'
        destination = saves / 'mods/hf'
        if not (source / 'manifest.ini').is_file():
            raise RuntimeError('Host build is missing its bundled Hellfire mod')
        files = [p for p in source.rglob('*') if p.is_file()]
        # Preserve any user changes in a reused runtime instead of overwriting.
        for path in files:
            target = destination / path.relative_to(source)
            if target.exists() and diablo.sha256(target) != diablo.sha256(path):
                raise RuntimeError(f'Existing runtime mod differs from build: {target}')
        for path in files:
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(path, target)
            mod_hashes[target.relative_to(saves).as_posix()] = diablo.sha256(target)
    ini = config / 'diablo.ini'
    if not ini.exists():
        ini.write_text('[Graphics]\nWidth=640\nHeight=480\nFullscreen=0\nFit to Screen=0\nUpscale=0\n', encoding='utf-8')
    command = [str(executable), '--' + args.campaign, '--data-dir', str(root / 'game'),
               '--config-dir', str(config), '--save-dir', str(saves), '--lang', 'en',
               '--verbose', '--log-to-file', str(runtime / 'engine.log'), '-n']
    env = dict(os.environ)
    env.pop('DIABLO_NATIVE_SCENARIO', None)
    env.pop('DIABLO_CAPTURE_DIR', None)
    env['PATH'] = 'D:/vibes/fpga/toolchains/msys64/ucrt64/bin' + os.pathsep + env['PATH']
    record = {'campaign': args.campaign, 'command': command,
              'mod_sha256': mod_hashes,
              'executable_sha256': diablo.sha256(executable),
              'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'gameplay_verified': False}
    with (runtime / 'console.log').open('wb') as output:
        process = subprocess.Popen(command, cwd=executable.parent, env=env,
                                   stdout=output, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        record.update(pid=process.pid, status='running')
        diablo.write_json(runtime / 'run.json', record)
        print(f'{args.campaign} PID {process.pid}; log {runtime / "engine.log"}', flush=True)
        record['exit_code'] = process.wait()
    record.update(status='exited', finished_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    diablo.write_json(runtime / 'run.json', record)
    return record['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())

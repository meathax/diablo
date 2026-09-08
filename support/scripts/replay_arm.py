"""Run the pinned shareware regression under ARM user-mode emulation, not MiSTer."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ASSET_PATHS = ('ASSETS_VERSION', 'ui_art/diablo.pal')


class AssetAdmissionError(ValueError):
    """The replay package cannot satisfy the engine's relative asset lookup."""


def host_path(path):
    """Map the WSL mount notation accepted by --build-dir to the host filesystem."""
    if os.name != 'nt':
        return Path(path)
    if path.startswith('/mnt/') and len(path) > 7 and path[6] == '/':
        return Path(path[5].upper() + ':/' + path[7:])
    if path.startswith('/'):
        return Path(subprocess.check_output(
            ['wsl', '-d', 'Ubuntu', '--', 'wslpath', '-w', path], text=True).strip())
    return Path(path)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight_assets(build_dir, package_manifest=None):
    """Require the assets directory resolved by the engine from its working directory."""
    asset_root = host_path(build_dir) / 'assets'
    missing = [str(asset_root / required) for required in REQUIRED_ASSET_PATHS
               if not (asset_root / required).is_file()]
    if missing:
        raise AssetAdmissionError('missing required replay asset(s): ' + ', '.join(missing))

    record = {
        'asset_root': str(asset_root),
        'required_assets': {
            required: sha256(asset_root / required) for required in REQUIRED_ASSET_PATHS
        },
    }
    if package_manifest is None:
        return record

    manifest_path = host_path(package_manifest)
    if not manifest_path.is_file():
        raise AssetAdmissionError(f'package manifest does not exist: {manifest_path}')
    try:
        files = json.loads(manifest_path.read_text(encoding='utf-8'))['files']
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise AssetAdmissionError(f'invalid package manifest: {manifest_path}') from error
    assets = [entry for entry in files
              if isinstance(entry, dict) and isinstance(entry.get('path'), str)
              and entry['path'].startswith('assets/')]
    if not assets:
        raise AssetAdmissionError(f'package manifest has no assets entries: {manifest_path}')
    resolved_asset_root = asset_root.resolve()
    mismatches = []
    for entry in assets:
        raw_path = entry['path']
        normalized_path = raw_path.replace('\\', '/')
        relative = PurePosixPath(normalized_path)
        parts = relative.parts
        if (relative.is_absolute() or PureWindowsPath(raw_path).is_absolute()
                or len(parts) < 2 or parts[0] != 'assets'
                or any(part in ('.', '..') or ':' in part for part in parts[1:])):
            raise AssetAdmissionError(f'invalid package asset path: {raw_path}')
        candidate = asset_root.joinpath(*parts[1:]).resolve()
        if not candidate.is_relative_to(resolved_asset_root):
            raise AssetAdmissionError(f'package asset escapes asset root: {raw_path}')
        expected = entry.get('sha256')
        if not candidate.is_file() or not isinstance(expected, str) or sha256(candidate) != expected:
            mismatches.append(entry['path'])
    if mismatches:
        raise AssetAdmissionError('package asset coverage failed: ' + ', '.join(mismatches[:5]))
    record.update(package_manifest=str(manifest_path),
                  package_manifest_sha256=sha256(manifest_path),
                  package_asset_count=len(assets))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', default='/home/meath/.cache/diablo-arm-engine-portable')
    parser.add_argument('--package-manifest',
                        help='verify build-dir/assets against this package manifest before QEMU')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    try:
        asset_preflight = preflight_assets(args.build_dir, args.package_manifest)
    except AssetAdmissionError as error:
        parser.error(str(error))
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
        inputs[name] = sha256(runtime / name)
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
              'asset_preflight': asset_preflight,
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

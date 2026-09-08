"""Capture native640 full-campaign reference scenes under ARM emulation."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

import diablo
from compare_frames import read_frame
from scenario_host import scenario_demo


BUILD_DIR_ENV = 'DIABLO_ARM_SCENARIO_BUILD_DIR'
REFERENCE_ROLE = 'arm-reference'
TRANSPORT_ROLE = 'arm-transport'
BINARY_NAME = 'devilutionx'


def validate_binary_hash(observed: str, expected: str | None = None) -> str:
    """Validate and normalize an ARM executable hash before a run is started."""
    observed = observed.strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', observed):
        raise ValueError(f'ARM executable hash is invalid: {observed!r}')
    if expected is not None:
        expected = expected.strip().lower()
        if not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError(f'expected ARM executable hash is invalid: {expected!r}')
        if observed != expected:
            raise ValueError(
                f'ARM executable hash mismatch: expected {expected}, observed {observed}')
    return observed


def selected_binary(build: str, expected_hash: str | None = None) -> dict[str, str]:
    """Return the exact WSL binary identity or reject a missing/wrong selection."""
    build = build.rstrip('/')
    executable = f'{build}/{BINARY_NAME}'
    try:
        output = subprocess.check_output(
            ['wsl', '-d', 'Ubuntu', '--', 'sha256sum', executable],
            text=True, stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f'ARM executable is missing or unreadable: {executable}') from error
    fields = output.split()
    if not fields:
        raise ValueError(f'ARM executable hash is missing: {executable}')
    return {'path': executable, 'sha256': validate_binary_hash(fields[0], expected_hash)}


def recipe_build_role(recipe: str) -> str:
    """Build role is determined by the CMake overlay that produced the artifact."""
    if recipe == 'support/cmake/arm-reference.cmake':
        return REFERENCE_ROLE
    if recipe == 'support/cmake/arm-transport.cmake':
        return TRANSPORT_ROLE
    raise ValueError(f'unsupported ARM build recipe: {recipe!r}')


def require_receipt_artifact_path(build: str, artifact_path: str) -> None:
    """Do not let an equally hashed binary from another directory replace the receipt artifact."""
    if artifact_path != build.rstrip('/') + '/' + BINARY_NAME:
        raise ValueError('ARM build directory does not select the receipt artifact path')


def load_build_receipt(path: Path, requested_role: str | None = None) -> dict[str, str]:
    """Load the independently derivable role/path/hash binding for the ARM build."""
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'ARM build receipt is missing or redirected: {path}')
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f'ARM build receipt is not valid JSON: {path}') from error
    if not isinstance(record, dict):
        raise ValueError(f'ARM build receipt must contain an object: {path}')
    if record.get('schema') != 'diablo-arm-build-receipt-v1' or record.get('status') != 'pass':
        raise ValueError(f'ARM build receipt is not a successful typed build record: {path}')
    provenance = record.get('provenance')
    if not isinstance(provenance, dict) or provenance.get('kind') != \
            'retained-arm-reference-build-adapter-v1':
        raise ValueError(f'ARM build receipt has no verified provenance adapter: {path}')
    try:
        from record_arm_reference_provenance import derive_receipt
        expected_record = derive_receipt()
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        raise ValueError('ARM build provenance inputs cannot be verified') from error
    if record != expected_record:
        raise ValueError(f'ARM build receipt does not match verified build provenance: {path}')
    artifact = record['artifact']
    role = recipe_build_role(record['configure']['include']['path'])
    if requested_role is not None and role != requested_role:
        raise ValueError(
            f'ARM build role mismatch: requested {requested_role}, receipt records {role}')
    return {'build_role': role, 'binary_sha256': validate_binary_hash(artifact['sha256']),
            'artifact_path': artifact['path'], 'path': str(path.resolve())}


def resolve_build_dir(value: str, root: Path) -> str:
    """Resolve a CLI build path to a canonical WSL path for the ARM command."""
    if not value or not value.strip():
        raise ValueError(f'--build-dir is required (or set {BUILD_DIR_ENV})')
    value = value.strip()
    if value.startswith('/'):
        return value.rstrip('/')
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    try:
        return subprocess.check_output(
            ['wsl', '-d', 'Ubuntu', '--', 'wslpath', '-a', str(path.resolve())],
            text=True).strip().rstrip('/')
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f'cannot resolve ARM build directory through WSL: {path}') from error


def validate_role(role: str) -> None:
    """Reference capture hooks are absent from the deployable transport binary."""
    if role == TRANSPORT_ROLE:
        raise ValueError(
            'arm-transport has no DIABLO_NATIVE_SCENARIO hooks; use replay_arm.py for its '
            'timedemo replay')
    if role != REFERENCE_ROLE:
        raise ValueError(f'unsupported ARM scenario build role: {role}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', choices=('diablo', 'hellfire'))
    parser.add_argument('--build-dir', default=os.environ.get(BUILD_DIR_ENV),
                        help=f'WSL or Windows ARM reference build directory '
                             f'(or {BUILD_DIR_ENV})')
    parser.add_argument('--build-role', choices=(REFERENCE_ROLE, TRANSPORT_ROLE),
                        help='Optional cross-check against the recipe-derived build role')
    parser.add_argument('--build-receipt', required=True,
                        help='verified typed JSON receipt binding the selected artifact to its build recipe')
    parser.add_argument('--expected-binary-sha256',
                        help='Additional hash assertion; the build receipt hash is always required')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    try:
        receipt_path = Path(args.build_receipt)
        if not receipt_path.is_absolute():
            receipt_path = diablo.ROOT / receipt_path
        receipt = load_build_receipt(receipt_path, args.build_role)
        validate_role(receipt['build_role'])
        build = resolve_build_dir(args.build_dir, diablo.ROOT)
        expected_hash = receipt['binary_sha256']
        if args.expected_binary_sha256 is not None:
            expected_hash = validate_binary_hash(args.expected_binary_sha256, expected_hash)
        require_receipt_artifact_path(build, receipt['artifact_path'])
        binary = selected_binary(build, expected_hash)
    except ValueError as error:
        parser.error(str(error))
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
    command = ['wsl', '-d', 'Ubuntu', '--cd', build, '--', 'env',
               'DIABLO_NATIVE_SCENARIO=town-v1', 'DIABLO_CAPTURE_DIR=' + output_dir + '/frames',
               'SDL_VIDEODRIVER=dummy', 'SDL_RENDER_DRIVER=software', 'SDL_AUDIODRIVER=dummy',
               'timeout', '--signal=TERM', '--kill-after=10s', str(args.timeout) + 's',
               qemu, '-cpu', 'cortex-a9', '-L', sysroot, build + '/devilutionx',
               '--' + args.campaign, '--demo', '0', '--timedemo',
               '--data-dir', linux(diablo.ROOT / 'game'), '--save-dir', output_dir,
               '--config-dir', output_dir, '--lang', 'en', '-n', '--verbose',
               '--log-to-file', output_dir + '/engine.log']
    record = {'status': 'running', 'build_role': receipt['build_role'], 'campaign': args.campaign,
              'scenario': 'town-v1', 'build_receipt': receipt['path'],
              'build_receipt_sha256': diablo.sha256(Path(receipt['path'])),
              'build_dir': build, 'binary_path': binary['path'],
              'binary_sha256': binary['sha256'], 'command': command,
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

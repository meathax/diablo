"""Derive one typed receipt for the retained successful ARM-reference build."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / '.mister/evidence/arm-native-capture-pass.json'
RUN_PATH = ROOT / '.work/runtime/arm-scenarios/51185829844d47bca166d4b03e162787/run.json'
CONFIGURE_COMMAND_PATH = ROOT / '.work/build/arm-engine-portable/reference-configure-command.json'
CONFIGURE_LOG_PATH = ROOT / '.work/build/arm-engine-portable/replay-loading-configure.log'
BUILD_LOG_PATH = ROOT / '.work/build/arm-engine-portable/replay-loading-build.log'
SOURCE_LOCK_PATH = ROOT / '.mister/source-lock.json'
RECIPE_PATH = ROOT / 'support/cmake/arm-reference.cmake'
RECIPE_RELATIVE_PATH = 'support/cmake/arm-reference.cmake'
TOOLCHAIN_RELATIVE_PATH = 'support/cmake/arm-portable.cmake'
OVERLAY_PATH = '/home/meath/.cache/diablo-arm-engine-portable/host-engine-fixes.txt'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f'cannot read JSON provenance input: {path}') from error
    if not isinstance(value, dict):
        raise ValueError(f'provenance input must be a JSON object: {path}')
    return value


def wsl_output(*command: str) -> str:
    try:
        return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--', *command], text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f'cannot read retained ARM build output: {command[-1]}') from error


def wsl_sha256(path: str) -> str:
    fields = wsl_output('sha256sum', path).split()
    if len(fields) < 1 or len(fields[0]) != 64:
        raise ValueError(f'cannot hash retained ARM build output: {path}')
    return fields[0].lower()


def command_value(command: list, prefix: str) -> str:
    matches = [value[len(prefix):] for value in command
               if isinstance(value, str) and value.startswith(prefix)]
    if len(matches) != 1 or not matches[0]:
        raise ValueError(f'reference configure command has no unique {prefix} value')
    return matches[0]


def command_option(command: list, option: str) -> str:
    indexes = [index for index, value in enumerate(command) if value == option]
    if len(indexes) != 1 or indexes[0] + 1 >= len(command):
        raise ValueError(f'reference configure command has no unique {option} value')
    value = command[indexes[0] + 1]
    if not value:
        raise ValueError(f'reference configure command has an empty {option} value')
    return value


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def derive_receipt() -> dict:
    evidence = read_json(EVIDENCE_PATH)
    run = read_json(RUN_PATH)
    source_lock = read_json(SOURCE_LOCK_PATH)
    try:
        configure_command = json.loads(CONFIGURE_COMMAND_PATH.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f'cannot read reference configure command: {CONFIGURE_COMMAND_PATH}') from error
    if not isinstance(configure_command, list) or not all(isinstance(value, str)
                                                          for value in configure_command):
        raise ValueError('reference configure command must be a string list')
    if evidence.get('status') != 'passed' or evidence.get('source_checkout_clean') is not True:
        raise ValueError('reference capture evidence is not a successful clean-source record')
    if source_lock.get('schema') != 'diablo-source-lock-v1':
        raise ValueError('source lock has an unsupported schema')
    engine_revision = source_lock.get('sources', {}).get('devilutionx', {}).get('commit')
    if not isinstance(engine_revision, str) or len(engine_revision) != 40:
        raise ValueError('source lock has no pinned DevilutionX revision')
    actual_revision = subprocess.check_output(
        ['git', '-C', str(ROOT / '.work/sources/devilutionx'), 'rev-parse', 'HEAD'], text=True).strip()
    if actual_revision != engine_revision:
        raise ValueError('retained engine checkout differs from the pinned source revision')
    recipe_hash = sha256(RECIPE_PATH)
    if evidence.get('patch_inputs', {}).get('support\\cmake\\arm-reference.cmake') != recipe_hash:
        raise ValueError('reference recipe hash does not match the capture evidence')
    if sha256(CONFIGURE_LOG_PATH) != evidence.get('configure_log_sha256'):
        raise ValueError('reference configure log does not match the capture evidence')
    if sha256(BUILD_LOG_PATH) != evidence.get('build_log_sha256'):
        raise ValueError('reference build log does not match the capture evidence')
    include = command_value(configure_command, '-DCMAKE_PROJECT_DevilutionX_INCLUDE=')
    if not include.replace('\\', '/').endswith('/' + RECIPE_RELATIVE_PATH):
        raise ValueError('reference configure command does not select arm-reference.cmake')
    if command_option(configure_command, '-G') != 'Ninja':
        raise ValueError('reference configure command does not select Ninja')
    if '-DCMAKE_BUILD_TYPE=Release' not in configure_command:
        raise ValueError('reference configure command does not select Release')
    toolchain = command_value(configure_command, '-DCMAKE_TOOLCHAIN_FILE=')
    if not toolchain.replace('\\', '/').endswith('/' + TOOLCHAIN_RELATIVE_PATH):
        raise ValueError('reference configure command has an unexpected ARM toolchain')
    build_directory = command_option(configure_command, '-B')
    artifact_path = build_directory.rstrip('/') + '/devilutionx'
    run_command = run.get('command')
    if not isinstance(run_command, list) or artifact_path not in run_command:
        raise ValueError('reference run does not select the configured ARM artifact')
    result = next((item for item in evidence.get('results', []) if isinstance(item, dict)
                   and str(item.get('arm_run', '')).replace('\\', '/').endswith(
                       relative(RUN_PATH))), None)
    if result is None or result.get('arm_run_sha256') != sha256(RUN_PATH):
        raise ValueError('reference run is not the recorded capture-evidence run')
    binary_hash = result.get('arm_binary_sha256')
    if not isinstance(binary_hash, str) or run.get('binary_sha256') != binary_hash:
        raise ValueError('reference run does not match the recorded binary identity')
    if wsl_sha256(artifact_path) != binary_hash:
        raise ValueError('retained ARM artifact no longer matches the recorded binary identity')
    overlay_text = wsl_output('cat', OVERLAY_PATH)
    expected_overlay = evidence.get('generated_engine_overlay_manifest')
    if not isinstance(expected_overlay, str) or overlay_text != expected_overlay:
        raise ValueError('retained overlay manifest does not match the capture evidence')
    overlay_hash = hashlib.sha256(overlay_text.encode('utf-8')).hexdigest()
    if wsl_sha256(OVERLAY_PATH) != overlay_hash:
        raise ValueError('retained overlay manifest hash is unstable')
    return {
        'schema': 'diablo-arm-build-receipt-v1',
        'status': 'pass',
        'artifact': {
            'path': artifact_path,
            'sha256': binary_hash,
            'bytes': int(wsl_output('stat', '-c', '%s', artifact_path).strip()),
        },
        'source': {
            'engine_revision': engine_revision,
            'source_lock': {'path': relative(SOURCE_LOCK_PATH), 'sha256': sha256(SOURCE_LOCK_PATH)},
            'overlay_manifest': {'path': OVERLAY_PATH, 'sha256': overlay_hash},
        },
        'configure': {
            'command': {'path': relative(CONFIGURE_COMMAND_PATH),
                        'sha256': sha256(CONFIGURE_COMMAND_PATH)},
            'generator': 'Ninja',
            'build_type': 'Release',
            'toolchain_file': TOOLCHAIN_RELATIVE_PATH,
            'include': {'path': RECIPE_RELATIVE_PATH, 'sha256': recipe_hash},
            'configure_log': {'path': relative(CONFIGURE_LOG_PATH),
                              'sha256': sha256(CONFIGURE_LOG_PATH)},
            'build_log': {'path': relative(BUILD_LOG_PATH), 'sha256': sha256(BUILD_LOG_PATH)},
        },
        'provenance': {
            'kind': 'retained-arm-reference-build-adapter-v1',
            'capture_evidence': {'path': relative(EVIDENCE_PATH), 'sha256': sha256(EVIDENCE_PATH)},
            'run': {'path': relative(RUN_PATH), 'sha256': sha256(RUN_PATH)},
            'scope': ('Historical successful ARM-reference build provenance only; no new build, '
                      'hardware acceptance, or performance qualification.'),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='receipt path relative to the repository root or absolute')
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        receipt = derive_receipt()
    except ValueError as error:
        parser.error(str(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Assemble a verified, game-data-free SD root and matching runtime database."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from support.scripts import candidate_manifest as candidate, package_release as package

def build(engine, base_package, output, base_url):
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"refusing to replace existing output: {output}")
    problems = package.verify_package(base_package)
    if problems:
        raise ValueError(str(problems))
    paths = {"engine": engine, "rbf": ROOT / "output_files/Diablo.rbf",
             "abi": base_package / "transport_abi.hex",
             "launcher": ROOT / "support/scripts/mister_launcher.py"}
    frontend = ROOT / "output_files/Diablo"
    for binary in (engine, frontend):
        header = binary.read_bytes()[:20]
        if header[:5] != b"\x7fELF\x01" or header[18:20] != b"\x28\x00":
            raise ValueError(f"not an ELF32 ARM binary: {binary}")
    assets = base_package / "assets"
    artifacts = list(paths.values()) + [frontend] + sorted(p for p in assets.rglob('*') if p.is_file())
    manifest = candidate.make_manifest(ROOT, artifacts)
    identity = ROOT / '.work/candidates' / (manifest['candidate_id'] + '.json')
    candidate.write_new_manifest(identity, manifest)
    runtime = output / '_Other/Diablo'
    package.create_package(ROOT, identity,
        [(role, str(path.relative_to(ROOT))) for role, path in paths.items()],
        'de10-nano-mister', runtime, str(assets.relative_to(ROOT)))
    shutil.copyfile(frontend, output / 'Diablo')
    for name in ('Diablo.rbf', 'Diablo Hellfire.rbf'):
        shutil.copyfile(paths['rbf'], output / '_Other' / name)
    # Main_MiSTer is a separate GPL program. Preserve its license alongside it.
    docs = output / 'docs/Diablo'
    docs.mkdir(parents=True)
    shutil.copyfile(ROOT.parent / 'VoidSW/platform/mister/wrapper/LICENSE', docs / 'LICENSE.frontend')
    (docs / 'INSTALL.txt').write_text(
        'Copy the contents of ready to the MiSTer SD root.\n'
        'Select _Other/Diablo.rbf or _Other/Diablo Hellfire.rbf.\n'
        'update_all integration must supply [Diablo] main=Diablo in MiSTer.ini.\n'
        'No MiSTer.ini is included: do not overwrite the user configuration.\n'
        'Game data belongs in games/Diablo; saves remain in games/Diablo/Saves.\n'
        'The inner package Scripts entries describe the optional transactional installer;\n'
        'they are not required for RBF launching. Python 3 is required on MiSTer.\n'
        'Frontend source: https://github.com/meathax/diablo (support/mister and build_diablo_main.sh).\n')
    for executable in (output / 'Diablo', runtime / 'devilutionx', runtime / 'diablo_launcher.py'):
        executable.chmod(0o755)
    files = {}
    folders = {}
    hashes = {}
    for path in sorted(output.rglob('*')):
        rel = path.relative_to(output).as_posix()
        if path.is_dir():
            folders[rel + '/'] = {'tags': ['diablo']}
            continue
        if path.suffix.lower() in ('.mpq', '.sv', '.sav', '.sve'):
            raise ValueError(f"private game content in output: {rel}")
        body = path.read_bytes()
        hashes[rel] = hashlib.sha256(body).hexdigest()
        files[rel] = {'hash': hashlib.md5(body).hexdigest(), 'size': len(body),
                      'url': base_url.rstrip('/') + '/' + quote(rel, safe='/'), 'tags': ['diablo']}
    database = {'v': 1, 'db_id': 'diablo_runtime', 'timestamp': int(time.time()),
                'files': files, 'folders': folders}
    (ROOT / 'distribution/diablo_runtime.json').write_text(json.dumps(database, indent=2) + '\n')
    (ROOT / 'reports/ready-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print(json.dumps({'ready': str(output), 'files': len(files), 'candidate': manifest['candidate_id'],
                      'package_errors': package.verify_package(runtime)}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--base-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'ready')
    parser.add_argument('--base-url', required=True, help='Published URL prefix for the ready directory')
    args = parser.parse_args()
    build(args.engine.resolve(), args.base_package.resolve(), args.output.resolve(), args.base_url)

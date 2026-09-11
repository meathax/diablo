"""Assemble a complete verified MiSTer SD-root staging tree and runtime database."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GAME_DATA_SOURCE = ROOT / 'game/Diablo'
sys.path.insert(0, str(ROOT))
from support.scripts import candidate_manifest as candidate, package_release as package
from scripts import generate_update_all as update_all


def md5_file(path):
    digest = hashlib.md5()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def stage_game_data(output):
    """Copy only the externally-audited local game archives into the SD root."""
    for entry in update_all.load_external_files():
        destination = output / entry['path']
        source = GAME_DATA_SOURCE / destination.name
        if not source.is_file():
            raise ValueError(f'missing required local game archive: {source}')
        if source.stat().st_size != entry['size']:
            raise ValueError(f'game archive size mismatch: {source}')
        if md5_file(source) != entry['md5']:
            raise ValueError(f'game archive MD5 mismatch: {source}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


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
    assets = Path(tempfile.mkdtemp(prefix="packed-assets-", dir=ROOT / ".work"))
    shutil.copytree(base_package / "assets", assets, dirs_exist_ok=True)
    packed_mod = assets / "mods" / "hf.mpq"
    if not packed_mod.exists():
        packer = ROOT / "support/scripts/pack_hellfire_mod.py"
        if sys.platform == "win32":
            def wsl_path(path):
                return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]
            subprocess.run(["wsl.exe", "-d", "Ubuntu", "--exec", "python3",
                            wsl_path(packer), wsl_path(assets / "mods/hf"),
                            wsl_path(packed_mod)], check=True)
        else:
            subprocess.run([sys.executable, str(packer), str(assets / "mods/hf"),
                            str(packed_mod)], check=True)
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
    for executable in (output / 'Diablo', runtime / 'devilutionx', runtime / 'diablo_launcher.py'):
        executable.chmod(0o755)
    # The runtime archive intentionally excludes licensed game data. Stage it only
    # after creating the archive so ready remains a complete local SD-root payload.
    update_all.write_game_artifacts()
    update_all.write_runtime_artifacts(output, base_files_url=base_url)
    stage_game_data(output)
    hashes = {}
    for path in sorted(output.rglob('*')):
        rel = path.relative_to(output).as_posix()
        if path.is_dir():
            continue
        body = path.read_bytes()
        hashes[rel] = hashlib.sha256(body).hexdigest()
    (ROOT / 'reports/ready-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print(json.dumps({'ready': str(output), 'files': len(hashes), 'candidate': manifest['candidate_id'],
                      'package_errors': package.verify_package(runtime)}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--base-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'ready')
    parser.add_argument('--base-url', required=True, help='Published URL prefix for the ready directory')
    args = parser.parse_args()
    build(args.engine.resolve(), args.base_package.resolve(), args.output.resolve(), args.base_url)

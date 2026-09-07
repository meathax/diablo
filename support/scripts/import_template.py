"""Import the pinned MiSTer template without replacing existing project files."""
import json
from pathlib import Path
import diablo


def main():
    root = diablo.ROOT
    locked = diablo.load_lock()['sources']['template']
    source = Path(locked['local'])
    identity = diablo.inspect_source(source, locked)
    files = diablo.git(source, 'ls-files').splitlines()
    excluded = {'.gitignore', 'Readme.md', 'Template_Q13.qpf', 'Template_Q13.qsf', 'Template_Q13.srf'}
    prepared = []
    for name in files:
        if name in excluded:
            continue
        destination = 'LICENSE.fpga' if name == 'LICENSE' else name.replace('Template.', 'Diablo.')
        raw = (source / name).read_bytes()
        if name in {'Template.qpf', 'files.qip', 'Template.sv'}:
            raw = raw.replace(b'Template', b'Diablo')
        target = root / destination
        if target.exists() and target.read_bytes() != raw:
            raise RuntimeError(f'Refusing to replace existing content: {target}')
        prepared.append((name, target, raw))
    records = []
    for name, target, raw in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(raw)
        records.append({'source_path': name, 'destination': target.relative_to(root).as_posix(),
                        'source_sha256': diablo.sha256(source / name),
                        'destination_sha256': diablo.sha256(target),
                        'modified': (source / name).read_bytes() != raw})
    manifest = {'schema': 'diablo-template-import-v1', 'source': identity, 'files': records,
                'excluded': sorted(excluded), 'scope': 'template demo bootstrap, not Diablo gameplay'}
    diablo.write_json(root / '.mister/template-import.json', manifest)
    framework = [r for r in records if r['destination'].startswith('sys/')]
    assert framework and all(not r['modified'] for r in framework)
    print(f'Imported {len(records)} files; {len(framework)} framework files unchanged')


if __name__ == '__main__':
    main()

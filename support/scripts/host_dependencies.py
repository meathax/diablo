"""Snapshot resolved host dependency sources and CMake inputs after configuration."""
import hashlib
import json
import os
from pathlib import Path

import diablo


def inventory(root, build):
    build_inputs = json.loads((build / 'build-inputs.json').read_text())
    git_executable = build_inputs['tools']['git']['path']
    def git(source, *args):
        # Use FetchContent's Git and its line-ending defaults consistently.
        return diablo.command([git_executable, '-c', f'safe.directory={source.resolve().as_posix()}',
                               '-C', str(source), *args])
    dependencies = []
    for source in sorted((build / '_deps').glob('*-src')):
        files = []
        for directory, subdirs, names in os.walk(source):
            subdirs[:] = sorted(name for name in subdirs if name != '.git')
            for name in sorted(names):
                path = Path(directory) / name
                if name == '.git':
                    continue
                files.append((path.relative_to(source).as_posix(), diablo.sha256(path)))
        tree = hashlib.sha256(json.dumps(sorted(files), separators=(',', ':')).encode()).hexdigest()
        item = {'name': source.name, 'file_count': len(files), 'file_tree_sha256': tree}
        if (source / '.git').exists():
            item.update(commit=git(source, 'rev-parse', 'HEAD'),
                        submodules=git(source, 'submodule', 'status', '--recursive'),
                        modifications=git(source, 'status', '--porcelain', '--untracked-files=all'))
        dependencies.append(item)
    inputs = {}
    for relative in ('CMakeCache.txt', 'compile_commands.json', 'build-inputs.json',
                     'dependency-fixes.json', 'CMakeFiles/devilutionx.dir/link.txt',
                     'CMakeFiles/devilutionx.dir/linkLibs.rsp'):
        path = build / relative
        if path.is_file():
            inputs[relative] = diablo.sha256(path)
    return {'schema': 'diablo-resolved-host-dependencies-v1',
            'scope': 'configured host source snapshot; not a target/runtime dependency lock',
            'dependency_closure_verified': False,
            'engine_commit': diablo.load_lock()['sources']['devilutionx']['commit'],
            'dependencies': dependencies, 'build_input_sha256': inputs,
            'pending': ['system header/library and runtime DLL identities',
                        'independent clean rebuild verification', 'ARM dependency closure']}


if __name__ == '__main__':
    result = inventory(diablo.ROOT, diablo.ROOT / '.work/build/reference-host')
    output = diablo.ROOT / '.mister/evidence/host-resolved-dependencies.json'
    diablo.write_json(output, result)
    print(f'Inventoried {len(result["dependencies"])} resolved dependency trees: {output}')

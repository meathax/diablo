"""Windows host-reference build with recorded patches and a clean pinned checkout."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import os
import uuid


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integration_files(root):
    """Record every project-owned source that affects the reference build."""
    names = ('support/scripts/host_build.py', 'support/cmake/host-reference.cmake',
             'support/cmake/host-capture.cmake', 'support/reference/host_capture.hpp',
             'support/cmake/host-scenario.cmake', 'support/reference/host_scenario.hpp',
             'support/reference/indexed_frame.hpp', 'support/tests/host_png_test.cpp',
             'support/patches/host-dependency-fixes.json')
    return {name: digest(root / name) for name in names}


def resolve_build_dir(root, requested):
    base = (root / '.work/build').resolve()
    chosen = (root / requested).resolve()
    if chosen == base or not chosen.is_relative_to(base):
        raise RuntimeError('Host build directory must be a directory beneath .work/build')
    return chosen


def apply_dependency_fixes(root, build_dir):
    manifest_path = root / 'support/patches/host-dependency-fixes.json'
    manifest = json.loads(manifest_path.read_text())
    applied = []
    for fix in manifest['fixes']:
        path = build_dir / fix['path']
        if not path.resolve().is_relative_to((build_dir / '_deps').resolve()):
            raise RuntimeError('Dependency patch must remain inside the build dependency tree')
        observed = digest(path)
        if observed == fix['original_sha256']:
            content = path.read_bytes().decode('utf-8')
            for edit in fix['edits']:
                if content.count(edit['old']) != edit['count']:
                    raise RuntimeError(f'Dependency patch context mismatch: {path}')
                content = content.replace(edit['old'], edit['new'])
            raw = content.encode('utf-8')
            if hashlib.sha256(raw).hexdigest() != fix['patched_sha256']:
                raise RuntimeError('Dependency patch output hash mismatch')
            path.write_bytes(raw)
        elif observed != fix['patched_sha256']:
            raise RuntimeError(f'Refusing to patch changed dependency: {path}')
        applied.append({'path': fix['path'], 'original_sha256': fix['original_sha256'],
                        'patched_sha256': digest(path)})
    record = {'manifest_sha256': digest(manifest_path), 'files': applied}
    (build_dir / 'dependency-fixes.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def build(root, args, inspect_source, lock):
    source = root / '.work/sources/devilutionx'
    identity = inspect_source(source, lock['sources']['devilutionx'])
    recipe_path = root / 'support/host-reference.json'
    recipe = json.loads(recipe_path.read_text())
    prefix = Path(recipe['toolchain_prefix'])
    tool_paths = {'cmake': Path(shutil.which('cmake') or ''),
                  'cc': prefix / 'bin/gcc.exe', 'cxx': prefix / 'bin/g++.exe',
                  'make': prefix / 'bin/mingw32-make.exe',
                  'git': Path('C:/Program Files/Git/cmd/git.exe')}
    for name, path in tool_paths.items():
        if not path.is_file():
            raise RuntimeError(f'Host build tool unavailable: {name}: {path}')
    build_dir = resolve_build_dir(root, args.build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    project_inputs = integration_files(root)
    inputs = {'engine': identity, 'recipe_sha256': digest(recipe_path),
              'integration_files': project_inputs,
              'integration_sha256': hashlib.sha256(json.dumps(project_inputs, sort_keys=True).encode()).hexdigest(),
              'tools': {name: {'path': str(path), 'sha256': digest(path)} for name, path in tool_paths.items()},
              'upstream_dependency_declarations': {
                  path.relative_to(source).as_posix(): digest(path)
                  for path in sorted((source / '3rdParty').rglob('CMakeLists.txt'))},
              'dependency_closure_verified': False}
    admission = build_dir / 'build-inputs.json'
    if admission.exists() and json.loads(admission.read_text()) != inputs:
        previous = json.loads(admission.read_text())
        comparable = lambda value: {key: item for key, item in value.items()
                                    if key not in {'recipe_sha256', 'integration_sha256', 'integration_files'}}
        if not args.reconfigure or comparable(previous) != comparable(inputs):
            raise RuntimeError('Build inputs changed; recipe-only updates require --reconfigure; engine/tool changes require a separate build directory')
        archive = build_dir / ('build-inputs-' + uuid.uuid4().hex + '.json')
        archive.write_bytes(admission.read_bytes())
    admission.write_text(json.dumps(inputs, indent=2) + '\n', encoding='utf-8')
    env = dict(os.environ)
    env['PATH'] = str(prefix / 'bin') + os.pathsep + env['PATH']
    configure = [str(tool_paths['cmake']), '-S', str(source), '-B', str(build_dir),
                 '-G', 'MinGW Makefiles', f'-DCMAKE_C_COMPILER={tool_paths["cc"].as_posix()}',
                 f'-DCMAKE_CXX_COMPILER={tool_paths["cxx"].as_posix()}',
                 f'-DCMAKE_MAKE_PROGRAM={tool_paths["make"].as_posix()}',
                 f'-DGIT_EXECUTABLE={tool_paths["git"].as_posix()}',
                 f'-DCMAKE_PROJECT_DevilutionX_INCLUDE={(root / "support/cmake/host-reference.cmake").as_posix()}',
                 f'-DCMAKE_PREFIX_PATH={prefix.as_posix()}']
    configure += [f'-D{key}={value}' for key, value in recipe['cmake_options'].items()]
    steps = [('configure', configure)]
    if not args.configure_only:
        steps.append(('build', [str(tool_paths['cmake']), '--build', str(build_dir),
                                '--parallel', str(args.jobs), '--target', 'devilutionx']))
    for stage, command in steps:
        if stage == 'build':
            apply_dependency_fixes(root, build_dir)
        log = build_dir / f'{stage}.log'
        print(f'{stage}: {log}', flush=True)
        with log.open('wb') as stream:
            process = subprocess.run(command, cwd=root, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=3600,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode:
            raise RuntimeError(f'Host {stage} failed ({process.returncode}); inspect {log}')
    inspect_source(source, lock['sources']['devilutionx'])
    executable = build_dir / 'devilutionx.exe'
    if not args.configure_only and not executable.is_file():
        raise RuntimeError(f'Build returned success without the expected executable: {executable}')
    return {'variant': 'reference-host', 'stage': 'configured' if args.configure_only else 'built',
            'inputs': str(admission.relative_to(root)), 'inputs_sha256': digest(admission),
            'logs': {stage: {'path': str((build_dir / f'{stage}.log').relative_to(root)),
                             'sha256': digest(build_dir / f'{stage}.log')} for stage, _ in steps},
            'executable_sha256': digest(executable) if executable.exists() and not args.configure_only else None,
            'dependency_fixes_sha256': digest(build_dir / 'dependency-fixes.json') if not args.configure_only else None,
            'engine_fixes_sha256': digest(build_dir / 'host-engine-fixes.txt'),
            'gameplay_verified': False, 'dependency_closure_verified': False}

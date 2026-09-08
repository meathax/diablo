"""Ensure dependency fixes cannot overwrite unrecognized build inputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('host_build', Path(__file__).parents[1] / 'scripts/host_build.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class BuildDirectoryTests(unittest.TestCase):
    def test_reference_recipe_disables_lto_for_fast_host_validation(self):
        recipe = json.loads((Path(__file__).parents[1] / 'host-reference.json').read_text())
        self.assertEqual(recipe['cmake_options'].get('DISABLE_LTO'), 'ON')
        self.assertEqual(recipe['cmake_options'].get('DISABLE_ZERO_TIER'), 'ON')

    def test_default_and_clean_directories_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = host.resolve_build_dir(root, '.work/build/reference-host')
            b = host.resolve_build_dir(root, '.work/build/reference-host-clean')
            self.assertNotEqual(a, b)
            self.assertFalse(a.exists())
            self.assertFalse(b.exists())

    def test_build_root_and_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for requested in ('.work/build', '.work/build/../../game', '../outside'):
                with self.subTest(requested=requested), self.assertRaises(RuntimeError):
                    host.resolve_build_dir(root, requested)


class DependencyFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.target = self.build / '_deps/source.c'
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'original')
        self.manifest = self.root / 'support/patches/host-dependency-fixes.json'
        self.manifest.parent.mkdir(parents=True)
        self.data = {'fixes': [{'path': '_deps/source.c',
            'original_sha256': hashlib.sha256(b'original').hexdigest(),
            'patched_sha256': hashlib.sha256(b'patched').hexdigest(),
            'edits': [{'old': 'original', 'new': 'patched', 'count': 1}]}]}
        self.manifest.write_text(json.dumps(self.data))

    def test_verified_patch_is_repeatable(self):
        first = host.apply_dependency_fixes(self.root, self.build)
        self.assertEqual(self.target.read_bytes(), b'patched')
        self.assertEqual(host.apply_dependency_fixes(self.root, self.build), first)

    def test_changed_dependency_is_preserved(self):
        self.target.write_bytes(b'user change')
        with self.assertRaises(RuntimeError): host.apply_dependency_fixes(self.root, self.build)
        self.assertEqual(self.target.read_bytes(), b'user change')

    def test_bad_patch_output_does_not_modify_source(self):
        self.data['fixes'][0]['patched_sha256'] = '0' * 64
        self.manifest.write_text(json.dumps(self.data))
        with self.assertRaises(RuntimeError): host.apply_dependency_fixes(self.root, self.build)
        self.assertEqual(self.target.read_bytes(), b'original')

    def test_path_outside_dependencies_is_rejected(self):
        self.data['fixes'][0]['path'] = '../outside.c'
        self.manifest.write_text(json.dumps(self.data))
        with self.assertRaises(RuntimeError): host.apply_dependency_fixes(self.root, self.build)

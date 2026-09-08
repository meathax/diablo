import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'support/scripts/replay_arm.py'
SPEC = importlib.util.spec_from_file_location('replay_arm', SCRIPT)
REPLAY_ARM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPLAY_ARM)


class ReplayArmPreflightTest(unittest.TestCase):
    def make_package(self, directory, extra_entries=()):
        stage = Path(directory)
        assets = stage / 'assets'
        required = {
            'ASSETS_VERSION': b'1\n',
            'ui_art/diablo.pal': b'palette',
        }
        entries = []
        for relative, content in required.items():
            path = assets / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            entries.append({
                'path': f'assets/{relative}',
                'sha256': hashlib.sha256(content).hexdigest(),
            })
        entries.extend(extra_entries)
        manifest = stage / 'package-manifest.json'
        manifest.write_text(json.dumps({'files': entries}), encoding='utf-8')
        return stage, manifest

    def test_accepts_normal_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            stage, manifest = self.make_package(directory)
            admission = REPLAY_ARM.preflight_assets(str(stage), str(manifest))

        self.assertEqual(admission['package_asset_count'], 2)

    def test_rejects_missing_package_assets_before_qemu(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), '--build-dir', directory, '--timeout', '1'],
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn('missing required replay asset(s)', result.stderr)
        self.assertIn('ui_art', result.stderr)

    def test_rejects_manifest_parent_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / 'outside.bin'
            outside.write_bytes(b'outside')
            entry = {
                'path': 'assets/../outside.bin',
                'sha256': hashlib.sha256(outside.read_bytes()).hexdigest(),
            }
            stage, manifest = self.make_package(directory, [entry])
            with self.assertRaisesRegex(REPLAY_ARM.AssetAdmissionError, 'invalid package asset path'):
                REPLAY_ARM.preflight_assets(str(stage), str(manifest))

    def test_rejects_absolute_manifest_path(self):
        with tempfile.TemporaryDirectory() as directory:
            entry = {
                'path': 'assets/C:/outside.bin',
                'sha256': hashlib.sha256(b'outside').hexdigest(),
            }
            stage, manifest = self.make_package(directory, [entry])
            with self.assertRaisesRegex(REPLAY_ARM.AssetAdmissionError, 'invalid package asset path'):
                REPLAY_ARM.preflight_assets(str(stage), str(manifest))

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / 'outside.bin'
            outside.write_bytes(b'outside')
            stage, manifest = self.make_package(directory)
            link = stage / 'assets/ui_art/linked.bin'
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f'symlink fixture unavailable: {error}')
            package = json.loads(manifest.read_text(encoding='utf-8'))
            package['files'].append({
                'path': 'assets/ui_art/linked.bin',
                'sha256': hashlib.sha256(outside.read_bytes()).hexdigest(),
            })
            manifest.write_text(json.dumps(package), encoding='utf-8')
            with self.assertRaisesRegex(REPLAY_ARM.AssetAdmissionError, 'escapes asset root'):
                REPLAY_ARM.preflight_assets(str(stage), str(manifest))

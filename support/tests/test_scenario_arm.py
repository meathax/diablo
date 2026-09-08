import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / 'scripts' / 'scenario_arm.py'
REAL_REFERENCE_RECEIPT = ROOT.parent / '.mister/evidence/receipts/arm-reference-portable-build-20260908.json'
sys.path.insert(0, str(ROOT / 'scripts'))
import record_arm_reference_provenance

RETAINED_REFERENCE_INPUTS = (
    record_arm_reference_provenance.EVIDENCE_PATH,
    record_arm_reference_provenance.RUN_PATH,
    record_arm_reference_provenance.CONFIGURE_COMMAND_PATH,
    record_arm_reference_provenance.CONFIGURE_LOG_PATH,
    record_arm_reference_provenance.BUILD_LOG_PATH,
    record_arm_reference_provenance.SOURCE_LOCK_PATH,
    record_arm_reference_provenance.RECIPE_PATH,
    record_arm_reference_provenance.ROOT / '.work/sources/devilutionx',
)


def retained_reference_available() -> bool:
    if not REAL_REFERENCE_RECEIPT.is_file():
        return False
    if not all(path.is_file() if path.suffix else path.is_dir()
               for path in RETAINED_REFERENCE_INPUTS):
        return False
    configure_command = json.loads(
        record_arm_reference_provenance.CONFIGURE_COMMAND_PATH.read_text(encoding='utf-8'))
    if (not isinstance(configure_command, list)
            or not all(isinstance(value, str) for value in configure_command)
            or configure_command.count('-B') != 1):
        raise ValueError('retained ARM configure command metadata is malformed')
    build_index = configure_command.index('-B')
    if build_index + 1 >= len(configure_command) or not configure_command[build_index + 1]:
        raise ValueError('retained ARM configure command has no build directory')
    artifact = configure_command[build_index + 1].rstrip('/') + '/devilutionx'
    for path in (artifact, record_arm_reference_provenance.OVERLAY_PATH):
        try:
            if subprocess.run(['wsl', '-d', 'Ubuntu', '--', 'test', '-f', path],
                              check=False, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode != 0:
                return False
        except OSError:
            return False
    return True


RETAINED_REFERENCE_AVAILABLE = retained_reference_available()

spec = importlib.util.spec_from_file_location('scenario_arm', SCRIPT)
scenario = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(scenario)


class ScenarioArmSelectionTests(unittest.TestCase):
    @staticmethod
    def synthetic_reference_receipt() -> dict:
        return {
            'schema': 'diablo-arm-build-receipt-v1',
            'status': 'pass',
            'artifact': {'path': '/selected/devilutionx', 'sha256': '1' * 64, 'bytes': 1},
            'configure': {'include': {'path': 'support/cmake/arm-reference.cmake'}},
            'provenance': {'kind': 'retained-arm-reference-build-adapter-v1'},
        }

    def test_selected_binary_records_exact_hash(self):
        expected = '67e82c01d45050f4ea7892f75d33cd9f2075be7ce02425aa9529fa11de7909ed'
        with mock.patch.object(
                scenario.subprocess, 'check_output',
                return_value=f'{expected}  /selected/devilutionx\n') as check_output:
            identity = scenario.selected_binary('/selected', expected)

        self.assertEqual(identity, {'path': '/selected/devilutionx', 'sha256': expected})
        self.assertEqual(check_output.call_args.args[0][-1], '/selected/devilutionx')

    def test_selected_binary_rejects_wrong_hash(self):
        with mock.patch.object(
                scenario.subprocess, 'check_output',
                return_value='0' * 64 + '  /selected/devilutionx\n'):
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                scenario.selected_binary('/selected', '1' * 64)

    def test_selected_binary_rejects_missing_executable(self):
        error = subprocess.CalledProcessError(1, ['sha256sum'])
        with mock.patch.object(scenario.subprocess, 'check_output', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'missing or unreadable'):
                scenario.selected_binary('/missing')

    def test_transport_role_reports_replay_gap(self):
        with self.assertRaisesRegex(ValueError, 'use replay_arm.py'):
            scenario.validate_role(scenario.TRANSPORT_ROLE)

    def test_build_receipt_rejects_user_claimed_role_and_hash(self):
        with self.assertRaisesRegex(ValueError, 'not a successful typed build record'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'build.json'
                path.write_text(json.dumps({
                    'build_role': scenario.REFERENCE_ROLE,
                    'binary_sha256': '1' * 64,
                }), encoding='utf-8')
                scenario.load_build_receipt(path)

    def test_build_receipt_rejects_failed_or_modified_typed_record(self):
        receipt = self.synthetic_reference_receipt()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'build.json'
            path.write_text(json.dumps(receipt), encoding='utf-8')
            receipt['status'] = 'fail'
            path.write_text(json.dumps(receipt), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'not a successful typed build record'):
                scenario.load_build_receipt(path)
            receipt['status'] = 'pass'
            receipt['artifact']['sha256'] = '0' * 64
            path.write_text(json.dumps(receipt), encoding='utf-8')
            with mock.patch.object(record_arm_reference_provenance, 'derive_receipt',
                                   return_value=self.synthetic_reference_receipt()):
                with self.assertRaisesRegex(ValueError, 'does not match verified build provenance'):
                    scenario.load_build_receipt(path)

    def test_build_role_is_derived_from_recipe_and_transport_stops_before_run(self):
        role = scenario.recipe_build_role('support/cmake/arm-transport.cmake')
        self.assertEqual(role, scenario.TRANSPORT_ROLE)
        with self.assertRaisesRegex(ValueError, 'use replay_arm.py'):
            scenario.validate_role(role)

    @unittest.skipUnless(RETAINED_REFERENCE_AVAILABLE,
                         'retained ARM reference evidence is not materialized in this checkout')
    def test_real_reference_provenance_adapter_is_accepted(self):
        loaded = scenario.load_build_receipt(REAL_REFERENCE_RECEIPT, scenario.REFERENCE_ROLE)
        self.assertEqual(loaded['build_role'], scenario.REFERENCE_ROLE)
        self.assertEqual(
            loaded['artifact_path'],
            '/home/meath/.cache/diablo-arm-engine-portable/devilutionx')
        self.assertEqual(
            loaded['binary_sha256'],
            '4ef9b4b1557174908809da0fee8c424a1a12e83b10caa45b11db0969925189e2')

    def test_build_directory_must_select_receipt_artifact_path(self):
        with self.assertRaisesRegex(ValueError, 'does not select the receipt artifact path'):
            scenario.require_receipt_artifact_path(
                '/other-build', '/home/meath/.cache/diablo-arm-engine-portable/devilutionx')

    def test_cli_transport_crosscheck_stops_before_binary_or_qemu(self):
        receipt = self.synthetic_reference_receipt()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'build.json'
            path.write_text(json.dumps(receipt), encoding='utf-8')
            argv = [str(SCRIPT), 'diablo', '--build-dir',
                    '/home/meath/.cache/diablo-arm-engine-portable', '--build-receipt',
                    str(path), '--build-role', scenario.TRANSPORT_ROLE]
            with mock.patch.object(sys, 'argv', argv), \
                    mock.patch.object(sys, 'stderr', new=io.StringIO()), \
                    mock.patch.object(record_arm_reference_provenance, 'derive_receipt',
                                       return_value=receipt), \
                    mock.patch.object(scenario, 'selected_binary') as selected:
                with self.assertRaises(SystemExit) as error:
                    scenario.main()
        self.assertEqual(error.exception.code, 2)
        selected.assert_not_called()

    def test_cli_rejects_other_build_directory_before_binary_or_qemu(self):
        receipt = self.synthetic_reference_receipt()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'build.json'
            path.write_text(json.dumps(receipt), encoding='utf-8')
            argv = [str(SCRIPT), 'diablo', '--build-dir', '/other-build', '--build-receipt',
                    str(path), '--build-role', scenario.REFERENCE_ROLE]
            with mock.patch.object(sys, 'argv', argv), \
                    mock.patch.object(sys, 'stderr', new=io.StringIO()), \
                    mock.patch.object(record_arm_reference_provenance, 'derive_receipt',
                                       return_value=receipt), \
                    mock.patch.object(scenario, 'selected_binary') as selected:
                with self.assertRaises(SystemExit) as error:
                    scenario.main()
        self.assertEqual(error.exception.code, 2)
        selected.assert_not_called()

    def test_build_dir_requires_explicit_selection(self):
        with self.assertRaisesRegex(ValueError, '--build-dir is required'):
            scenario.resolve_build_dir('', ROOT)

if __name__ == '__main__':
    unittest.main()

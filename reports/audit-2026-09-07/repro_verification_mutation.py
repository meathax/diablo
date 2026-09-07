"""Exercise receipt publication when an input changes during a passing step."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'support/scripts'))
import verification

with tempfile.TemporaryDirectory(prefix='diablo-mutation-audit-') as temporary:
    root = Path(temporary)
    source = root / 'input.txt'
    source.write_text('before', encoding='utf-8')
    step = verification.Step('mutate-input', ((sys.executable, '-c',
        "from pathlib import Path; Path('input.txt').write_text('after', encoding='utf-8')"),))
    with patch.object(verification, 'DEPENDENCY_INPUTS', ('input.txt',)), \
         patch.object(verification, 'selected_steps', return_value=([step], [])):
        code, receipt, receipt_path = verification.run(root, 'foundation', None, None)
        observed = verification.source_snapshot(root)
    report = {'experiment': 'Real local runner; only dependency selection and the step list are narrowed to a temporary input.',
              'exit_code': code, 'receipt_status': receipt['status'],
              'recorded_source_id': receipt['candidate']['source_id'],
              'after_source_id': observed['source_id'],
              'source_changed': receipt['candidate']['source_id'] != observed['source_id'],
              'expected': 'Receipt must fail or invalidate its source binding when an input changes during execution.'}
    output = ROOT / 'reports/audit-2026-09-07/refresh-evidence/verification-mutation.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))

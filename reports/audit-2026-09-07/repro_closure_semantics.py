"""Demonstrate structural evidence admission without modifying project gates."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'support/scripts'))
import closure_gates

matrix = json.loads((ROOT / 'support/qualification/closure-gates.json').read_text())
with tempfile.TemporaryDirectory(prefix='diablo-gate-audit-') as temp:
    root = Path(temp)
    plan = root / matrix['plan']['path']
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text((ROOT / matrix['plan']['path']).read_text(encoding='utf-8'), encoding='utf-8')
    source_id = 'a' * 64
    candidate_id = 'b' * 64
    record = {'schema': closure_gates.RECORD_SCHEMA, 'matrix_sha256': closure_gates.matrix_digest(matrix),
              'source_id': source_id, 'candidate_id': candidate_id, 'items': {}}
    for identifier, specification in matrix['items'].items():
        evidence = []
        for requirement in specification['evidence']:
            file = root / (identifier + '-' + requirement['id'] + '.json')
            if requirement['kind'] == 'receipt':
                content = {'schema': closure_gates.RECEIPT_SCHEMA, 'status': 'pass',
                           'suite': requirement['suite'], 'candidate': {'source_id': source_id, 'candidate_id': candidate_id},
                           'results': [{'id': 'required-check', 'status': 'fail'}]}
            else:
                content = {'schema': closure_gates.ARTIFACT_SCHEMAS[requirement['id']], 'status': 'fail',
                           'source_id': source_id, 'candidate_id': candidate_id,
                           'metrics': {'fps': 1, 'p99_presentation_ms': 9999, 'late_prepared_percent': 100},
                           'note': 'Not a candidate manifest, timing report, or accepted qualification.'}
            file.write_text(json.dumps(content), encoding='utf-8')
            evidence.append({'id': requirement['id'], 'kind': requirement['kind'],
                             'path': file.name, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
        record['items'][identifier] = {'status': 'closed', 'evidence': evidence}
    result = closure_gates.evaluate(root, matrix, record, None, None)
    report = {'experiment': 'All gates supplied hash-valid but semantically failing synthetic evidence; no real acceptance changed.',
              'observed': result, 'expected_eligible': False}
    output = ROOT / 'reports/audit-2026-09-07/refresh-evidence/closure-semantics.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))

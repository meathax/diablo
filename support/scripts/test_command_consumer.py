"""Compile and run the randomized-backpressure FPGA command consumer fixture."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import diablo


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    iverilog = shutil.which('iverilog') or shutil.which('iverilog.exe')
    vvp = shutil.which('vvp') or shutil.which('vvp.exe')
    if not iverilog or not vvp:
        raise SystemExit('iverilog and vvp are required')
    build = ROOT / '.work' / 'build' / 'command-consumer'
    build.mkdir(parents=True, exist_ok=True)
    executable = build / 'diablo_command_consumer.vvp'
    sources = [
        ROOT / 'rtl' / 'diablo_command_consumer.sv',
        ROOT / 'support' / 'tests' / 'diablo_command_consumer_tb.sv',
    ]
    compile_command = [
        iverilog, '-g2012', '-I', str(ROOT / 'rtl'), '-s', 'diablo_command_consumer_tb',
        '-o', str(executable), *(str(path) for path in sources),
    ]
    subprocess.run(compile_command, cwd=ROOT, check=True)
    subprocess.run([vvp, str(executable)], cwd=ROOT, check=True)
    evidence = {
        'schema': 'diablo-command-consumer-test-v1',
        'status': 'passed',
        'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'commands': [compile_command, [vvp, str(executable)]],
        'inputs': {str(path.relative_to(ROOT)): sha256(path) for path in sources},
        'checks': [
            'command ring identity, layout, epoch and ownership validation',
            'FillRect clipping and indexed pixel writes',
            'overlap-safe CopyRect source/destination ordering',
            'End fence publication and record/payload consumer advancement',
            'randomized DDR busy and delayed-read backpressure',
        ],
        'scope': 'RTL command consumer correctness fixture; top-level MiSTer command-ring integration and full DevilutionX scene submission remain open.',
    }
    receipt = ROOT / '.mister' / 'evidence' / 'fpga-command-consumer-test-20260907.json'
    diablo.write_json(receipt, evidence)
    print(json.dumps({'status': 'passed', 'receipt': str(receipt.relative_to(ROOT))}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

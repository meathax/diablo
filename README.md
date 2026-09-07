# Diablo for MiSTer — implementation workspace

This workspace is preparing a native DevilutionX ARM port with FPGA presentation,
input transport and indexed rendering acceleration for DE10-Nano. **There is no
accepted runnable Diablo core or release package yet.**

The detailed execution and closure authority is
[reports/audit-2026-09-07/PROPOSED_PLAN.md](reports/audit-2026-09-07/PROPOSED_PLAN.md).
[CORE_COMPLETION_AUDIT.md](CORE_COMPLETION_AUDIT.md) is the compact execution entry point;
[.mister/state.json](.mister/state.json) identifies the current candidate work and
marks earlier receipts as historical when the source has changed.

## What exists

- Pinned engine, Blood donor and MiSTer template identities.
- A clean ignored DevilutionX checkout under `.work/sources/devilutionx`.
- Private MPQ identity and structural-bounds verification.
- Python preflight, source checks, tests and diagnostic Quartus report parsers.
- A Windows host build and reproducible 640×480 town scenarios for full Diablo
  and Hellfire, with exact indexed-frame and RGB888 palette comparisons.

The pinned template is imported and the tree contains a prototype ARM transport
adapter, generated shared ABI, indexed frame/command paths, PCM and input paths.
Those local components do not establish a target candidate, physical I/O,
deterministic full-scene correctness, campaign workflows, multiplayer, or a
daemon-free menu launch. These remain release requirements.

## Current commands

Use Python 3.10 or newer and Git:

```text
python support/scripts/diablo.py doctor --quartus-root D:/Q17
python support/scripts/diablo.py fetch --locked
python support/scripts/diablo.py verify-data
python support/scripts/diablo.py test --suite foundation
python support/scripts/diablo.py verify --suite local
python support/scripts/diablo.py build-host --jobs 8
```

Quartus is installed at `D:/Q17`; its version file reports `17.0.2.602`.
Doctor inventories it without launching tools. A successful inventory is not a
build or hardware verdict. It returns exit code 2 if the compiler is missing;
operation failures return 1 and successful operations return 0.
The removed plan's particular workflow runner is no longer a project prerequisite.

The host reference builds and the upstream gameplay replay passes. Both campaign
town scenarios pass and their repeated captures agree. These are PC correctness
checks, not MiSTer or FPS results. An independent clean rebuild passes the same
campaign scenarios and produces matching captures; step 1 is accepted in
[the host-reference evidence](.mister/evidence/step-1-host-reference-acceptance.json).
See [HOST_REFERENCE.md](support/HOST_REFERENCE.md) for command-line validation
without desktop automation and the limits of this evidence.
The local verification command records immutable source-bound receipts. Configure
host build/SDL paths and ARM/QEMU paths explicitly before requesting those optional
tiers; a passing local or QEMU receipt does not load an RBF or establish board
acceptance. FPGA build, target launcher, benchmark and package qualification remain
open in the detailed plan.

## Data, sources and distribution

`game/` contains user-supplied commercial archives. Keep it read-only to build
operations; never include it in Git or packages. Structural MPQ checks do not
prove member integrity or successful engine startup. No saves or private captures
belong in public artifacts.

Exact source identities are in [.mister/source-lock.json](.mister/source-lock.json).
Blood is a read-only integration donor; Template_MiSTer supplies the FPGA skeleton.
Preserve component notices and track imported files. Component licensing and
composition review remain required before distribution; no aggregate release
license or hardware-accuracy claim is declared.

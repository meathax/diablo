# Diablo for MiSTer — implementation workspace

This project is implementing a native DevilutionX ARM port with an FPGA indexed
2D accelerator for the DE10-Nano. **There is no runnable Diablo core or release
package yet.** Native 640×480 output, daemon-free launch, full input support,
Hellfire, and multiplayer are requirements, not implemented feature claims.

The approved specification is [.mister/DIABLO_IMPLEMENTATION_PLAN.md](.mister/DIABLO_IMPLEMENTATION_PLAN.md).
The authoritative progress record is [.mister/state.json](.mister/state.json).

## Implemented foundation

- Immutable source commit lock and clean-checkout admission checks.
- Read-only inspection of the primary Blood donor and pinned MiSTer template.
- Separate ignored DevilutionX source checkout under `.work/sources/devilutionx`.
- SHA-256 identity and MPQ header/table-bounds verification of five private archives.
- Atomic operation receipts, a Quartus capability preflight, and negative-admission tests.
- Strict Quartus inference, timing and fitter report parsers under development,
  exercised against synthetic faults and real Blood reports. These do not issue
  release acceptance.

Run from this directory with Python 3.10 or newer and Git available:

```text
python support/scripts/diablo.py doctor
python support/scripts/diablo.py fetch --locked
python support/scripts/diablo.py verify-data
python support/scripts/diablo.py test --suite foundation
```

`doctor` returns exit code 2 while mandatory tooling gates are blocked. Other
commands return 0 on success and 1 on failure. The CLI prints the receipt path.
It does not implement later build, comparison, benchmark, or packaging commands;
unimplemented commands are rejected rather than reporting success.

`fetch --locked` validates the local Blood/template repositories without modifying
them and fetches the exact engine commit into the ignored development directory.
It refuses changed checkouts and does not fetch the complete engine dependency
closure. The latter belongs to P02. Optional `--source <lock-name>` selects a
specific source. No branch tracking, reset, clean, or global Git configuration is used.

`verify-data` never writes `game/`. Its private manifest is under
`.mister/evidence/private/`, also ignored. Hashing establishes identity; MPQ
structural checks do **not** establish member integrity, language compatibility,
or successful game startup. The pinned engine still needs to open the archives.

## Current gate

The shared Quartus runner now advertises workflow ownership; audit and acceptance
integration remains under development. No RTL, framework, PLL, constraints, or Quartus project has been
imported or changed, and no FPGA build has run. See
[the gate record](.mister/contracts/QUARTUS_RUNNER_GATE.md) for the observed
capabilities and the exact conditions for continuing P01.

## Target and accuracy

The intended target is DE10-Nano with HPS DDR3, HDMI, and applicable 31 kHz analog
output. The proposed DDR aperture is not yet approved for hardware access.
This is a native software-engine port with a newly designed accelerator; it
does not reproduce a Diablo arcade PCB. There is no hardware-accuracy claim.

## Sources and licenses

Blood is the primary integration donor; the official MiSTer template provides
the future public FPGA skeleton. DevilutionX supplies game behavior. Exact
identities and source roles are in [.mister/source-lock.json](.mister/source-lock.json).
Additional Frontier/Duke3D/DeViL references are recorded there.

DevilutionX's selected source has a Sustainable Use License. Donor components
have separate notices and conditions. No aggregate release license is declared
at this stage, and GPL Blood userspace code has not been copied into the engine.
See [.mister/contracts/PROVENANCE.md](.mister/contracts/PROVENANCE.md).

Commercial MPQs, saves, and private captures must never enter release packages.
There are no installable artifacts, OSD options, or downloader instructions yet.

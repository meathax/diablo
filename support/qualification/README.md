# Closure gate matrix

`closure-gates.json` is the machine-readable acceptance contract for the C01â€“C34 work packages in the detailed audit plan. It records required scope, numeric thresholds, closure dependencies, evidence tiers, and the source changes that reopen a gate.

Validate the contract before changing a status:

```powershell
python support/scripts/closure_gates.py --check
```

A future closure record must contain every C-item, the matrix digest, its source identity, and the SHA-256 of each immutable receipt or artifact it cites. A `closed` item must satisfy all of its listed evidence requirements; `waived` requires an explicit scope-decision identifier, approver, and rationale. Evaluate a record with:

```powershell
python support/scripts/closure_gates.py --evaluate reports/audit-2026-09-07/closure-record.json --expected-candidate-id <candidate-id>
```

The evaluator deliberately blocks a release when any item is open, blocked, or in progress. It is not a substitute for the physical, campaign, timing, and packaging evidence specified in the plan.

The local evaluator now requires a non-null 64-hex candidate/source identity,
typed JSON artifacts, pass-only result records, unique evidence IDs, and
hash/byte-verified logs. Performance artifacts are checked against the numeric
targets in `closure-gates.json`; physical artifacts must enumerate every scoped
campaign, output mode, control device, multiplayer pairing and workflow. A hash
alone is not acceptance.

Local verification runs against an isolated source snapshot and rejects source,
artifact or candidate-manifest drift before publishing a pass receipt. Use
`support/scripts/deployment_manifest.py` to create/verify a runtime-only package
manifest after development checkout validation. The launcher accepts
`--deployment-manifest` for that package and does not require Git or the source
tree at runtime.

For C32 packaging, stage only the verified runtime roles into a new output
directory. The builder refuses replacement, symlinks, private-data-looking
files and hash drift, then emits both `deployment.json` and the typed package
manifest:

```powershell
python support/scripts/package_release.py create `
  --root . `
  --candidate-manifest .mister/evidence/candidates/<candidate>.json `
  --artifact engine=.work/build/<id>/arm/devilutionx `
  --artifact rbf=.work/build/<id>/output_files/Diablo.rbf `
  --artifact abi=.work/build/transport-abi/header.hex `
  --artifact launcher=support/scripts/mister_launcher.py `
  --assets .work/build/arm-engine-transport-assets `
  --board-profile <miSTer-profile> `
  --output .work/release/<candidate>
python support/scripts/package_release.py verify --package .work/release/<candidate> `
  --board-profile <miSTer-profile>
```

The v2 package contains 192 files: four fixed runtime roles, deployment/package
manifests, `NOTICE.txt`, `SETUP.md` and the complete redistributable assets tree.
The target launcher is standard-library Python and verifies the package before
writing `load_core` to `/dev/MiSTer_cmd`; it creates the current-boot admission
and passes the transport lease FD to the engine. `deploy_package.py` provides the
same verified staging/atomic activation contract for clean install, update,
interrupted-update recovery and rollback qualification. A normal launcher smoke
is not video/audio/gameplay acceptance.

Copy the resulting runtime directory to a clean supported MiSTer image and run
the launcher preflight before recording install, update, rollback and second-
launch evidence. Do not add game data, saves or the development checkout to the
package.

The board tier is configuration-driven through
`support/scripts/board_runner.py`. A board configuration must bind the selected
candidate and source, name the target, provide explicit argv arrays (no shell),
and include passing candidate-bound video, audio, input, campaign and performance
observations. `verify --suite board` remains incomplete until a real target
configuration and physical evidence are supplied; the adapter no longer silently
pretends that a configured board run passed.

For a local lifecycle qualification fixture, run:

```powershell
python support/scripts/deployment_lifecycle.py `
  --package .work/release/<candidate> `
  --board-profile <miSTer-profile> `
  --output .mister/evidence/receipts/<unique-lifecycle-receipt>.json
```

The receipt is local transaction evidence only; it does not substitute for a
clean MiSTer install, menu activation, physical observation or campaign run.

## Current package/lifecycle qualification

The package and candidate identity are recorded in the main plan and .mister/state.json after each immutable candidate is minted. The package contains the fixed runtime roles, matching FPGA artifact and ABI, launcher, engine assets, NOTICE.txt, and SETUP.md; package_release.py verify checks its manifest before staging. deployment_lifecycle.py exercises clean install, interrupted update preservation, successful update, rollback, save/config preservation, final manifest verification, and staging cleanup. These local receipts remain evidence for the candidate they name and do not imply physical MiSTer acceptance.

## Candidate38 historical package checkpoint â€” 8 September 2026

An earlier package under qualification was `.work/package-board-candidate-38`,
staged at `\\192.168.0.69\sdcard\_CodexDiabloCandidate38`. It contains 190
files: `devilutionx`, `Diablo.rbf`, `transport_abi.hex`, `diablo_launcher.py`,
the two manifests and 184 redistributable assets. Package manifest SHA-256 is
`115998423d0409a2f10c192cf5c8487d340bc4bfd3cae2e2d88d37c1d3182896`.
Candidate38 and source identities are
`8e7a07cb78693ccbb60e813e56c0af018e2b947e0326a0ada5d3dd839cb6e2fb` and
`ff4184d9d0f5532cfacfe1990416f5d2dcd5a33da7683d2943e1b519609869f3`.

Target preflight passes at
`.mister/evidence/receipts/20260908T-candidate38-preflight.json`; the physical
normal60 launch receipt is
`.mister/evidence/receipts/20260908T-physical-launch-candidate38-normal60.json`.
These receipts prove package/admission/loader/frame lifecycle only. They do not
close the board profile, physical video/core identity, active audio, controls,
campaign/save/multiplayer, performance or clean-install/update/rollback gates.
Licensed MPQs, saves and private captures remain outside the package.

## Candidate40 historical superseding checkpoint â€” 8 September 2026

Candidate40 supersedes the candidate38 package entry above after the integrated
DDR testbench width/race fix. Its candidate manifest was
`.mister/evidence/candidates/fpga-candidate-20260908-40-integrated-tb.json`,
candidate ID
`56860713d38990ae28f1846e5f22850ed68b9ee228f6178c11e53fcb0f2d8a9b`, and source
ID `13b93de9eb32d9fc72701886c164853622bc744c18cddec1b660f127ffc70c7d`.
Package40 was staged at `\\192.168.0.69\sdcard\_CodexDiabloCandidate40` and its
read-only preflight passes. Candidate-bound local verification also passes all 20
registered checks.

The clean five-second launcher smoke passed. The longer board attempt is blocked
by a concurrent NFS_SE install/rollback process and observed active PCM underrun
growth/dropped chunks; it is recorded as a blocker, not a board pass. Physical
video/core identity, active audio, controls, campaign/save/multiplayer,
performance and clean install/update/rollback remain open. Keep MPQs, saves and
private captures outside the package.

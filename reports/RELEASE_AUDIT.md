# Diablo release audit — 2026-09-10

## Deliverable

`ready/` is an SD-root overlay containing 258 files. Copy its contents to the MiSTer root, preserving directories. Launch `_Other/Diablo.rbf` or `_Other/Diablo Hellfire.rbf`. The supported folder is `_Other` (singular).

No commercial game data, saves, or MiSTer.ini is included. Game data belongs in `games/Diablo`; existing saves remain in `games/Diablo/Saves`. Update All integration must supply the shared `[Diablo]` section with `main=Diablo`. Python 3 is required.

Candidate: `855baf91909f3d8dfa1ae0ab6d97670ec66967b67049f80306b6e16c3ed1bfb2`.

## Safe fixes

- Added the required downloader `folders` entries for game data staging.
- Registered the frontend transition cleanup hook; core changes now stop the launcher and engine instead of leaving processes behind.
- Routed frontend restarts through stock MiSTer so menu/other-core selection resolves the next core's configuration correctly.
- Closed the supervisor process-group setup race and bounded graceful shutdown before forced cleanup.
- Added launcher SIGTERM/finally cleanup and removal of stale readiness/admission markers while holding the transport lease.
- Added reproducible SD-overlay/runtime-database generation and full game-download verification tooling.

No gameplay rules, save formats, or FPGA logic were changed during this audit. The ARM engine and frontend were rebuilt; the existing RBF was retained.

## Evidence

- All five configured game URLs returned HTTP 200 and passed full streamed size and MD5 checks. See `downloader-audit.json`. Downloaded game bytes were not retained in ready.
- Runtime database: all 258 local destination files match their declared size and MD5. URL filenames are encoded, including the Hellfire RBF space.
- Package verification: no errors. SHA-256 inventory: `ready-sha256.json`.
- Hardware: all 258 deployed files matched ready byte-for-byte. Diablo started with `--diablo`; switching to Hellfire started `--hellfire`; switching back started a fresh Diablo engine. Returning to menu left stock MiSTer running, no launcher/engine processes, and no stale admission/readiness files.
- Hardware copy emitted FAT ownership-preservation warnings; subsequent complete byte comparison found zero mismatches.
- Previous deployed frontend/runtime retained under `/media/fat/.codex-backup/diablo-audit`. Board left at the MiSTer menu.
- Focused launcher/downloader suite on WSL: 16 tests passed, no skips.
- Full Windows suite: 204 tests run, 8 skipped, 1 error. The error is `test_real_reference_provenance_adapter_is_accepted`: retained historical reference-build evidence no longer matches its recipe hash. Evidence was not rewritten and the test was not weakened.
- Current ARM deterministic WarriorLevel1to2 gameplay replay passed. Receipt: `.work/runtime/arm-replays/e779a3898f7145298fdb458ae78e1043/run.json`.
- `git diff --check` passed.

## Update All publication gate

This audit validates source databases, full game downloads, the local runtime payload, and actual RBF launches. It does **not** establish that public Update All currently distributes this unpublished build.

Publish `ready/` and both databases at their configured URLs, and enable these database IDs in the Update All/downloader integration:

```ini
[diablo_mister]
db_url = https://raw.githubusercontent.com/meathax/diablo/main/distribution/diablo_mister.json

[diablo_runtime]
db_url = https://raw.githubusercontent.com/meathax/diablo/main/distribution/diablo_runtime.json
```

`diablo_mister` supplies game data; `diablo_runtime` supplies the SD-root overlay. A configured database is required; merely publishing JSON does not subscribe users to it. The external integration must also add the agreed MiSTer.ini entry without overwriting user configuration. Do not distribute a replacement MiSTer.ini or downloader.ini.

Before public release, rerun Update All against those published URLs on a clean staging card. Publishing/pushing and the external Update All integration were not performed here.

## Scope limits

This is targeted lifecycle, packaging, download-integrity, automated-test and deterministic-gameplay coverage, not an exhaustive playthrough or proof that the game is bug-free. Physical display/audio quality and perfect frame pacing were not instrumented in this audit. The stale historical provenance check remains an explicit outstanding test issue.

# Historical candidate checkpoints

Archived from the root execution guide on 8 September 2026. All present-tense
status statements below describe their original checkpoint, not current acceptance.
Use the root execution guide and detailed plan for current work.

The current development candidate is
`d95d4cfd03154bd659343c5a77a1230bcd4efc7c45d81d4f2299a0d754128611`, bound by
`.mister/evidence/candidates/fpga-candidate-20260908-49-final-local.json`
(manifest SHA-256
`f420873962a21317c8a9bdc9ff1ad07db02d9ad4299c2b9b5ff2e1abae802c4b`). Its
source identity is
`59d9a616708db186946cab362d6c66627a99d9a21a18b4bf6f97cb70a3e9eda0`.
The matching ARM transport executable SHA-256 is
`ead7cc2ac6417ce88833a66e7fcf400d85058061964a96f43a44658fb3bee87c`; fresh
candidate43 SOF SHA-256 is
`ae7f6bbc69f6d52f00f9e3bb7637de35b8495dac7f72aadc8a2794889dce98e7`, and raw
and compressed RBF SHA-256 is
`7b5eb62411233b96adc244d87fe3ee96b16da13b271fa608d9a70cafd4917b10`.
The 192-file/184-asset package was superseded by candidate49's 192-file package
with explicit `NOTICE.txt` and `SETUP.md`; it verifies locally, is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate49FinalLocal`, and its
read-only target preflight passes. Candidate-bound local and ARM/QEMU suites,
Diablo/Hellfire role-aware scene-oracle receipts and the local install/update/
rollback lifecycle receipt pass. The full checkout passes 141 Python tests with
one declared Windows privilege skip. These are development evidence only; no
accepted release candidate exists.

Candidate41 is a documentation-only source refresh of candidate40's integrated-test
fix. Candidate40's clean five-second launcher smoke passes package verification,
current-boot admission, exact requested-RBF process matching and FPGA operating
state for the unchanged runtime artifacts. Candidate41 then completed a clean
60-second Diablo normal-session launcher run with exact RBF matching, FPGA
`operating`, exit code 0, no PCM drops/resyncs and no observed steady underrun delta
after startup. Its blocked receipt is
`.mister/evidence/receipts/20260908T-physical-launch-candidate41-normal60.json`
(SHA-256 `3a1f7e97d3be5429000b27e9d3c1319dd42cf1291f02cba52e505651b5f845fb`): the
observer remained black/stale and startup PCM underruns were 6,732. Candidate40's
ownership-contended attempt remains recorded at
`.mister/evidence/receipts/20260908T-physical-launch-candidate40-attempt.json`
(SHA-256 `9ce81ad97fddeaf01ce178d3453d1096a7c5e623dfde04318508869195f8bdae`). The
physical observer has also reported AO486 in prior clean attempts, so video/core
identity is unresolved. Licensed campaign data is supplied from the target's
private data root and excluded from the package. Physical audio, controls,
campaign/save workflows, multiplayer, 60-FPS performance, clean install/update/
rollback and release promotion remain open.

The candidate41 Diablo timedemo attempt was blocked by a concurrent MAME core
owning MiSTer while the launcher waited for exact candidate-RBF admission. It was
aborted without accepting timedemo evidence; the diagnostic receipt is
`.mister/evidence/receipts/20260908T-physical-timedemo-candidate41-blocked.json`
(SHA-256 `028404ad383e53cfc8ff545f0ca5682afc11046d4799fba67debabae40731758`).
The next target window must exclude all MiSTer, MAME and installer processes.

The implementation fixes behind the remaining gates are recorded in the detailed
plan's bug register. They cover the v1 package's omitted assets, transport lease
descriptor inheritance, exact running-RBF admission, timedemo frame-rate pacing,
and the stale R12 board diagnostic. These fixes are locally regression-tested and
are evidence for implementation status only; they do not close the corresponding
physical acceptance gates.

## Candidate41 historical doc-sync checkpoint

Candidate41 was the final documentation-synchronized identity before the
candidate42/43 video-policy rebuild. Its manifest is
`.mister/evidence/candidates/fpga-candidate-20260908-41-doc-sync.json` (candidate `a5f2b83c0191d56e44a7b1babd5988e3fc0530a9f973f6e6bb739b13479ab989`,
source `7901cdc0d54c3d8d3a527a85445c78d4d1ad5330e1b223f426a3ed15dc914d0d`, SHA `c87c3b7dc214f23c4dc299c9010cbf2e8e031c2962a1a05604d59fa7452b0579`). Package41 and target preflight pass;
candidate-bound local verification passes all 20 checks. The board remains blocked
by shared MiSTer ownership and active PCM faults recorded in `.mister/evidence/receipts/20260908T-physical-launch-candidate40-attempt.json`.
Physical video/audio/input/campaign/performance/install and release-promotion gates
remain open until a quiescent target run supplies the required receipts.

## Candidate43 source-policy and clean-build checkpoint

Candidate43 supersedes the provisional candidate42 source-policy record. The
fresh build receipt `.mister/evidence/fpga-build-candidate43.json` (SHA-256
`f825d7ab8eaaccfd2f03699bb775c329b759d1bee5eebba648354334317fe2e2`) records
direct Quartus compile, compression and four setup corners with zero violations
and 0.188 ns minimum positive slack. Candidate43 local and ARM/QEMU receipts,
both role-aware scene-oracle passes, package verification and target preflight
all pass. The package is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate43`.

The candidate remains development-only. The target is currently owned by an
external MAME core, so activation was not attempted; connector-specific video,
active stereo audio, controls, campaign/save/multiplayer, performance and clean
install/update/rollback evidence remain open. The exact HDMI framebuffer/scaler,
direct RGB and analog/scandoubler rows are now explicit in the matrix; each still
needs candidate43 physical evidence before C13/C25/C31 can close.
Candidate49 carries the release tooling and package evidence, but the same three
rows still require candidate-bound physical captures.

## Candidate49 release-lifecycle checkpoint

Candidate49 is the current development identity after the release-tooling pass:
candidate `d95d4cfd03154bd659343c5a77a1230bcd4efc7c45d81d4f2299a0d754128611`,
source `59d9a616708db186946cab362d6c66627a99d9a21a18b4bf6f97cb70a3e9eda0`,
manifest `.mister/evidence/candidates/fpga-candidate-20260908-49-final-local.json`
(SHA `f420873962a21317c8a9bdc9ff1ad07db02d9ad4299c2b9b5ff2e1abae802c4b`). It
retains candidate43's fresh FPGA/ARM artifact lineage while binding the new
package and board-runner source snapshot.

Candidate49 package49 contains 192 files/184 assets plus explicit setup/notices,
verifies with package-manifest SHA
`f09bd76e1b4c80d7eb6391409dc1724f573a5931d4cf644ed7092573e49e63f3`, and is
staged at `\\192.168.0.69\sdcard\_CodexDiabloCandidate49FinalLocal`.
The target preflight passes in
`.mister/evidence/receipts/20260908T-candidate49-preflight.json` (SHA
`64d827d9d29953396c55be9314ae19fde04aa63820370573fab9de3d594a1b78`). The
transaction receipt
`.mister/evidence/receipts/20260908T-candidate49-deployment-lifecycle.json`
(SHA `324d8ad330f940de78d52d77f372b8c04cbf7dce10eeb3278e899410dee14c01`)
passes clean install, interrupted-update preservation, update, rollback, save
preservation, manifest verification and staging cleanup. `board_runner.py` now
has a no-replace CLI result path, but no physical observations are claimed.

Candidate49 remains development-only: the target is owned by an external MAME
core, so no activation was attempted. HDMI framebuffer/scaler, direct RGB,
analog/scandoubler, active stereo audio, controls, campaign/save/multiplayer,
performance, menu activation and clean-target acceptance remain open.


## Candidate27 physical handoff packet

Use this packet to resume the only blocked execution segment without rereading
the historical audit. The runtime package is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate27`; its read-only preflight receipt
is `.mister/evidence/receipts/20260908T-preflight-candidate27.json`. Bind every
observation to candidate
`95eaf3535aaf52d55b63f85b9bc566178c8e24b0d6f00d1e29d28a54021bcaf8`, source
`29e74b2685e333470ee383d40a977aa8b5a6da87a1a3d5106025890f1e9a42f4`, and
manifest SHA-256
`e83b4d6a3142ab930419bf04caf9f273df4d628619010906e51e7f0fd16a0f13`.

1. From a known-safe MiSTer menu state, use the supported menu/loader path to
   load the staged `Diablo.rbf`; record current boot identity, reserved DDR,
   loaded RBF identity, target version, output mode and the exact loader/runtime
   argv. The reachable target's `Scripts/wifi.sh` and `Scripts/MiSTer_SAM_on.sh`
   show the local loader interface as `load_core /media/fat/<path>` written to
   `/dev/MiSTer_cmd`; the read-only observation is recorded in
   `.mister/evidence/receipts/20260908T-loader-interface-candidate27.json`
   (SHA-256 `8a1ffe1a1b56e9f1da5e224c50d11afe8e0065bd9a40f3e37e044a522f94665a`).
   Use that interface only through an authorized target command/profile, then
   verify the resulting core identity. Do not overwrite existing core or
   user-data paths.
2. Supply a candidate-bound `diablo-board-configuration-v1` profile to
   `support/scripts/board_runner.py`. It must use shell-free argv arrays,
   positive timeouts, a target name, and passing `video`, `audio`, `input`,
   `campaign` and `performance` observations with immutable evidence references.
3. Run the physical matrix on the same loaded candidate: HDMI and every claimed
   analog/direct mode, stereo audio, keyboard/mouse/controller-only input, OSD
   focus, save/load, Diablo and Hellfire progression, multiplayer, reset/core
   switch, idle/gameplay endurance and the stated cadence/latency/underrun
   thresholds. Return to the menu and preserve the before/after state.
4. On a clean supported image, first prove the MiSTer-native engine launch path
   and its interpreter/dependency contract. If that path is unavailable, add a
   target-compatible launcher and rebuild/requalify the candidate before testing
   install, update, interrupted update, rollback, second launch and save
   preservation. A package hash match alone cannot close this gate.

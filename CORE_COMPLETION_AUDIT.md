# Diablo MiSTer — completion execution plan

**Active execution status, 8 September 2026:** follow the concise [progress handoff](PROGRESS.md) and the authoritative [PLAN.md](PLAN.md). The user confirms the repaired full cinematic cycle and good audio, and authorizes HDMI-only physical testing with CRT/direct-video retained as best-effort untested settings. The committed local verification packet and endpoint-aligned ARM replay are complete. PCM underflow-event diagnostic commit `9bf880a` is accepted as diagnostic-only; reproducible FPGA compile/timing/compress is delegated to `.work/goal-pcm-fpga-9bf880a`, and candidate-bound integrated tracing remains active. No hardware or release acceptance is implied, and no release is accepted.

## Historical next-chat handoff — 8 September 2026

This is a retained historical checkpoint, superseded by the active status above. No release is accepted; retain the full C01–C34/R01–R13 closure scope in the detailed plan.

- **Completed:** cinematic source mismatch fixed in `d2ccbc3`; movies now use their own indexed pixels/palette and a pitch-aware 640×480 conversion, including backpressure handling. Focused regression, independent review, incremental ARM compile/link, candidate/package verification and 191/191 target hashes pass. Engine SHA-256: `67e82c01d45050f4ea7892f75d33cd9f2075be7ce02425aa9529fa11de7909ed`. The qualified FPGA was reused; no new Quartus build was needed.
- **Current development candidate:** `b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b`, package `.work/package-board-c26-cinematic-d2ccbc3-assets`, target `/media/fat/_CodexDiabloCinematic_d2ccbc3`. The user confirms the full visual cycle and good audio; historical launcher/engine PIDs 2515/2524 are not current ownership proof. Revalidate live ownership before interacting. Private game data is verified at `/media/fat/_CodexDiabloGameData`; preserve user data and existing test artifacts.
- **Visual observation:** the user's repaired title → cinematic → title confirmation is recorded as candidate-bound development evidence. Changing full-frame CRCs, advancing frames and zero conversion diagnostics remain telemetry; they do not close HDMI physical acceptance or permit candidate promotion by themselves.
- **Audio investigation:** the identity-matched steady trace records 120/120 samples on one stable epoch: producer/consumer `+6196941`, display/last-frame `+5652`, underruns `+33685`, resync `0`, and no input drops. The user reports good audio; telemetry does not establish an audible defect, and zero-underrun physical acceptance remains open. Evidence: `.work/goal-audio/steady-gameplay-20260908/{receipt.json,summary.json,packet-index.json}`. Underflow-event attribution is the active next work, delegated to `pcm_event_capture` with `pcm_diagnosis` review.
- **Independent checks:** commit `0782c88` has a passing 23-step committed local receipt; `.work/goal-replay-endpoint/completed-comparison.json` records the exact reference/repaired ARM replay at 4,853 logical ticks, both original comparator passes and byte-identical final archives. Candidate-bound integrated target tracing and the remaining campaign/save/input, HDMI, audio, performance, lifecycle and C25 checks remain open. Host/local evidence does not close ARM physical or release gates.
- **Remaining release requirements:** controls/OSD, save/relaunch, Diablo/Hellfire progression and content, multiplayer, all declared display modes, stereo endurance, performance/latency, reset/core switching, clean installation/update/rollback/menu launch, and C25 external timing/board configuration proof. Use the existing detailed plan and closure matrix; do not narrow completion to this repair.
- **Push blocker:** local commits exist on `main`, but no Git remote is configured. `git push` failed with “No configured push destination.” The remote URL was requested and is still missing. Obtain the intended URL, verify it, and push the committed work; do not invent a repository or claim a successful push. Two unrelated tracked modifications (`.mister/evidence/transport-control-test.json` and `reports/audit-2026-09-07/refresh-evidence/inventory.json`) and historical untracked artifacts were preserved rather than staged wholesale.

Resume efficiently: one bounded implementation owner (Luna MAX), Terra XHIGH for difficult cross-component review, exact evidence and focused tests first. Reuse the qualified FPGA unless FPGA inputs actually change. Avoid repeated audits, tool rediscovery, speculative fixes and extra Quartus builds.

**Active worktree update:** C34 ownership extraction and command-wait accounting
changes supersede Candidate49 source qualification. The cinematic ARM overlay and focused source/test packet are committed in d2ccbc3
and locally regression-tested. Repaired candidate b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b is packaged and
running; the physical visual cycle remains pending.  C33 is reopened because its last
receipt records file absence, not execution of current build/test producers. No
release is accepted.

**Status: not release-ready; no current accepted candidate. Updated 8 September
2026.** Start here. Follow the seven batches below in order. The detailed
[C01–C34 work packages](PLAN.md) remain the
implementation/closure authority; the
[audit refresh](reports/audit-2026-09-07/REFRESH_AUDIT.md) adds mandatory R01–R12
fixes. [Machine state](.mister/state.json) records the active action and evidence;
the [gate matrix](support/qualification/closure-gates.json) defines measurable
acceptance. Earlier bring-up claims are preserved in the
[progress handoff](PROGRESS.md) and the [archived historical guide](reports/audit-2026-09-07/archive/HISTORICAL_COMPLETION_GUIDE.md).

C34 now separates input, PCM resampling, command/frame state and profiling.
The pre-review baseline passed the full local suite (21 checks), ARM ABI/QEMU
suite, production ARM incremental rebuild and executable startup check. Subsequent
profiler reset, invalid timing and 60 Hz pacing fixes pass their focused regression;
full qualification is being refreshed. The current ARM executable is
`.work/build/arm-engine-c34-clean/devilutionx` (clean engine-input build and QEMU startup pass); it is not yet an accepted
candidate. Exact receipts and remaining C34 checks are in the detailed plan's
current execution table.

Candidate49 is historical because the source changed. Its staged package is
preserved for rollback/reference; do not activate it as the current build.
[Historical candidate checkpoints](reports/audit-2026-09-07/CANDIDATE_CHECKPOINT_HISTORY.md)
preserve prior artifact identities, results and limitations without duplicating
them in this execution guide.

Quartus is available under `D:/q17/quartus`. SSH to `192.168.0.69` works, but the
latest check found an NFS_SE deployment modifying MiSTer files. Recheck target
ownership before activation; leave that operation undisturbed.

## Bugs found and fixes

| Bug | Fix | Closure evidence still required |
| --- | --- | --- |
| Runtime package omitted assets. | v2 package/deployment manifests require and hash the complete 184-file asset tree. | Clean target installation and both campaign launches. |
| Engine did not inherit the launcher's transport lock descriptor. | Launcher passes the POSIX lease FD to the child process. | Candidate32 normal-session receipt and controlled exit. |
| Core admission could accept a different running RBF. | Launcher matches the exact requested RBF in `/proc` and records boot/FPGA state. | Independent target video/core identity proof. |
| Timedemo could saturate the transport ring and reboot the board. | Candidate32 adds opt-in 60 Hz frame pacing when timedemo is requested. | Completed Diablo/Hellfire timedemo runs with stable boot and zero transport faults. |
| R12 fallback message was stale. | Verification now names the missing board configuration and the board runner path. | Candidate-bound board verification receipt. |
| The ARM CMake overlay lost the `string(REPLACE ...)` match string while the audio callback was being tuned. | The overlay failed at configure time and could not produce a target binary. | Restored the exact upstream `Aulib::init` match and added the 1024-frame target callback path; the clean overlay now configures and builds all 742 targets. Rebuild any future candidate from a clean snapshot and retain the configure/build receipt. |
| `Diablo.sv` passed PCM parameters as ports, so Quartus rejected the intended large FIFO instantiation. | FPGA compilation stopped before timing analysis. | Corrected the instantiation to `#(.PRIME_SAMPLES(8192), .FIFO_SAMPLES(16384))`; candidate38 compile, timing and compression pass with zero timing violations. Candidate-bound board run must confirm the larger FIFO under active gameplay. |
| The 512-frame ARM callback and small FPGA FIFO starved the target during active load. | PCM underruns rose continuously in candidate35/36/37 observations. | Use a 1024-frame callback, 8,192-sample prime and 16,384-sample FPGA FIFO, publish local queue occupancy through the ABI flags word, and log startup versus steady deltas. 30-minute Diablo/Hellfire active traces, physical stereo inspection and zero steady underrun/resync delta remain required. |
| Candidate manifests and packages could diverge on the required assets/launcher roles. | A package could verify its four runtime files while a clean launch failed on missing campaign/UI assets. | Candidate38 uses the complete v2 manifest and 190-file package; package and target preflight verify exact file coverage and private-data exclusion. Clean-image install/update/rollback and both campaigns from the staged package remain required. |
| Video source selection could let the diagnostic generator masquerade as gameplay, and the three connector paths were described too generically. | A black/stale or diagnostic pattern could be mistaken for a valid game frame, while HDMI evidence could be incorrectly inherited by direct RGB or analog output. | `rtl/diablo_video_source_policy.sv` gates gameplay on a complete indexed frame, keeps diagnostics explicit, and drives `FB_EN`/`VGA_SCALER` from one policy. The matrix now has exact HDMI framebuffer/scaler, direct RGB and analog/scandoubler rows; candidate43 rebuild and policy RTL regression pass. | Candidate43 physical gameplay capture, sync/geometry and per-connector acceptance. |
| The imported scandoubler carried an unresolved one-line VSync TODO. | Progressive 31 kHz output could have been misaligned even if HDMI looked correct. | `sys/scandoubler.v` now documents the supported progressive pipeline, samples VSync/VBlank consistently and connects Hq2x `.mono(1'b0)` deterministically; candidate43 all-corner timing passes. | Analog/scandoubler connector capture and sync/geometry proof. |
| The integrated DDR testbench kept an 11-bit PCM queue wire after the production client widened to 13 bits, and its final read/response assertion sampled a live in-flight request. | Candidate-bound local verification failed with a width warning and one apparent missing response even though the client was still servicing the request. | Widened the harness to `[12:0]` and made the assertion sample at a safe edge while allowing exactly one tracked in-flight read; the local suite now passes. | Keep the integrated harness in every candidate-bound local suite and reopen the gate on any client port-width change. |
| Physical board observations can be contaminated by another MiSTer installation/update process. | Candidate40's longer target attempt saw an unrelated NFS_SE rollback process and cannot prove single-core video/audio behavior. | The board receipt records the contention as `blocked`; target work must acquire an exclusive board window and verify one exact MiSTer process before physical acceptance. | Re-run candidate40 (or the next candidate) on a quiescent board, then complete video/audio/input/campaign/performance gates. |
| The distributed package had no explicit setup/notices or transactional update proof. | A clean target could not tell users where licensed data belongs or recover safely from an interrupted update. | `package_release.py` emits `NOTICE.txt`/`SETUP.md`; `deploy_package.py` performs verified staging and atomic activation; candidate49 lifecycle evidence passes install, interruption, update, rollback and save preservation. | Run the final package on a clean supported MiSTer, prove menu integration and second launch, and retain physical receipts. |
| The board runner had no executable receipt-publishing entry point. | Physical qualification depended on ad-hoc invocation and could not enforce no-replace evidence. | `board_runner.py` now provides a shell-free bounded CLI and immutable result publication with regression coverage. | Supply candidate-bound physical video/audio/input/campaign/performance observations on a quiescent target. |
## Completion contract

Deliver Diablo and Hellfire at native 640×480 with correct gameplay, stable game
timing, correct indexed/RGB output, audible stereo, keyboard/mouse and
controller-only operation, save/load, multiplayer and robust menu launch/exit.
Qualify every declared display mode explicitly. Cover ordinary progression,
late-game/boss/end sequences, representative class/skill/spell/inventory/UI,
cinematics, transitions and campaign-specific content, not only a town timedemo.
Maintain a coverage matrix so shared checks are reused and campaign-specific
checks cannot disappear.

The existing matrix targets 60 FPS, p99 presentation ≤16.67 ms, late-prepared
frames ≤0.1%, and physical input-to-visible p95 ≤50 ms / p99 ≤100 ms. Record
p50/p95/p99/p99.9/max, actual display cadence and every missed/dropped/faulted
presentation. Require exact deterministic scene equality, zero corruption,
no stuck ownership/input, and zero steady-play PCM underruns after explicit
priming. Loading/transition stalls are reported separately, never discarded.

Acceptance includes ≥30 minutes combined gameplay per campaign, ≥120 minutes
idle, ≥100 lifecycle cycles, and ≥30 minutes per required multiplayer campaign
pairing. These are minimum stress samples, not proof that campaign progression
is complete. Require clean install/update/rollback and a second launch on a
supported MiSTer image, with private data/saves excluded from the package.
An unmet feature or target remains open; do not silently weaken it to obtain a
green result. Completion means satisfying this explicit contract with evidence;
testing cannot prove the absence of every possible bug.

## Batch 1 — make the plan and evidence trustworthy

**C18/C26–C31; R01–R03/R06–R12.** Preserve existing work and immutable historical
receipts. Freeze a reviewable implementation snapshot; inventory staged and
unstaged implementation, generated files, dependencies and licensing. Keep
pinned source identities, `game/` and donor trees read-only. Do not commit
unrelated work or copy private MPQs into the snapshot.

The two reproduced evidence bugs are now fixed locally and regression-tested:

1. Closure evaluation now inspects typed artifact contents, required test IDs,
   complete coverage/measurements and transitive log hashes; bind a mandatory
    validated candidate and reject failed/skipped/incomplete evidence. The
    historical failing-evidence reproduction is now rejected.
2. Verification now runs from an isolated immutable snapshot and rejects changed
   sources/artifacts before receipt publication. The mutation regression now
   records a failed `source-integrity` result instead of publishing a pass.

Exit: both refresh reproductions are negative regression tests; all gate targets
and release candidate requirements are machine-enforced. Record current work
separately from accepted work. Preserve C01–C34 identifiers and keep these items
IMPLEMENTED/VERIFYING until their required evidence actually closes them.

## Batch 2 — close integrated correctness and service recovery

**C01–C12/C14/C15/C17/C19/C22.** Reuse implemented rectangle, cache, clipping,
scanout and input fixes; run targeted regressions before editing them again.
Finish asynchronous fence/fault ownership, callback-safe epoch recovery, and
the combined DDR arbitration/service path as one coherent transport change.

Required cases: producer faster/slower than display; all slots occupied; late
fence and malformed commands; wrapped cursors/IDs; epoch/reset during command,
audio or input; delayed DDR; focus loss with held controls; disconnect/reconnect;
queue overflow and resynchronization; command/full-copy/dirty-copy alternation;
different animated palettes and scaler-visible output through delayed commits.
Never recycle a slot while a late FPGA writer can still target it.

Build one deterministic capture/oracle corpus covering complete indexed frames,
palettes and metadata for Diablo/Hellfire scenes, then check decoded displayed
RGB. Sampled CRCs and acknowledgements are diagnostics only. Start with a correct
full-copy baseline and compare acceleration to it on identical scenes. Add
failure-specific regressions instead of implementation-mirroring tests.

Exit: targeted host/RTL/integrated regressions pass, required host PNG/SDL/ARM
tiers run with explicit dependencies, and every physical check has a named
scenario and expected result. No board performance conclusion yet.

## Batch 3 — complete the actual target launch and output path

**C13/C16/C17/C24/C28/C32; R04/R05.** The runtime deployment manifest,
`--deployment-manifest` launcher path and configuration-driven board adapter are
implemented. Complete the concrete MiSTer menu profile and supply a real board
configuration; `verify --suite board` stays incomplete until its commands and
candidate-bound physical observations pass.

Separate development source manifests from deployment manifests. A clean target
must validate installed ARM/RBF/ABI files and build provenance without needing
the developer Git checkout, `.work` directory or toolchain. Confirm target
launcher/interpreter/runtime dependencies. Prove current-boot DDR reservation,
candidate/core readiness and exclusive process ownership before mapping the
aperture. Reject stale boot/admission files and mismatched artifacts.

Implement and qualify each promised HDMI/analog/native/direct-video mode; a
diagnostic test pattern or forced-scaler route cannot close another output mode.
Finish controller naming/text entry, OSD focus, safe shutdown, reset/core switch,
relaunch, missing-data errors and storage/save failure handling.

Exit: fake-target lifecycle/error tests pass and there is one explicit real-target
command/profile with artifact identity, bounded logs, timeouts and cleanup.

## Batch 4 — build and admit one matching candidate

**C18/C25–C29.** Build ARM and FPGA from frozen source. Use pinned sources,
isolated toolchains and Quartus `D:/Q17`; no retired workflow runner dependency.
Close all timing corners, active endpoints, justified exceptions, clock/CDC/reset
assumptions and inferred resources. A positive summary alone is insufficient.
Archive build commands, tool/config identities, logs, warnings and exact hashes.

Create a new immutable candidate binding source, ARM, compressed RBF and ABI.
Recheck source/artifacts before load. Record target board/image/boot/output
configuration and verify installed hashes/readiness using Batch 3 admission.
Do not rebuild after a docs-only edit when the artifact dependency manifest
proves no build input changed; implementation or RTL/SDC changes invalidate the
affected build and downstream checks.

Exit: candidate-bound local/ARM results and final FPGA sign-off are consistent,
and the board safely admits exactly that candidate. Gameplay acceptance is next.

## Batch 5 — qualify the complete physical core

**C09/C13/C15/C19/C23/C24.** Use one session matrix to capture matching pixels,
speaker output, real controls, game workflow and transport telemetry together.
Exercise both campaigns through the coverage contract, required multiplayer
host/join pairings, idle/gameplay stress, storage failures and lifecycle cycles.
Dummy SDL does not substitute for seeing/hearing/controlling the game.

For each row record candidate, scene/save/replay identity, board configuration,
duration, expected/observed result and immutable capture/log references. Keep
private game data and recordings private. A physical observer can provide visual/
audio judgments when instrumentation cannot establish them; unobserved rows
remain pending. Investigate every mismatch, underrun, stuck control or unsafe
recovery, fix once, then rerun its dependency-affected rows.

Exit: the full physical correctness/workflow matrix passes on the same candidate.

## Batch 6 — reach the measured performance target

**C20/C21, with C03/C09/C15/C19.** Run ≥3 paired software/accelerated measurements
on identical deterministic representative and worst-case scenes. Keep simulation
timing fixed and use one pacing authority. Measure draw/build/copy/submission,
fences, DDR, actual presentation, PCM and input service, including failed paths.

Find the dominant p99/p99.9 cost before optimizing. Prioritize command batching,
overflow/fallback reduction, safe overlap or transfer reduction only when the
profile supports it. Use both ARM cores only when measured critical-path time
improves without races or bandwidth starvation. Gate each optimization with
full-frame equality/service bounds, then repeat the same paired corpus. Timebox
one hypothesis/experiment; retain only demonstrated improvements.

If the target remains infeasible, record the limiting bandwidth/cycle/CPU budget
and a concrete architectural remedy with its cost and requalification scope.
Keep the target open; do not declare completion from a faster town demo.

Exit: matrix performance/cadence/input limits pass while correctness and
zero-underrun service remain intact on the final candidate.

## Batch 7 — package, clean-install and close

**C23–C34.** Produce the allowlisted runtime package, deployment manifest,
installation/data-placement instructions, notices and component/source provenance.
Exclude MPQs, personal saves, captures, caches and donor files. Test a clean target
without developer tools; prove installation, update, interrupted update, rollback,
wrong/missing data errors, save preservation and second launch for both campaigns.
Use `support/scripts/package_release.py` to create and verify the immutable
runtime-only package before copying it to a MiSTer image; its local self-check is
necessary but does not replace the physical install/update/rollback observations.

Evaluate an actual closure record against the hardened matrix. Every required
C-item and R01–R12 amendment must have matching evidence. Reopen affected gates
after implementation/configuration changes. Remove generated root artifacts only
after retaining their evidence and setting ignore rules. Publish a concise release
record identifying exactly what was tested and delivered.

Exit: every required feature/measurable gate passes; package hashes match the
qualified candidate and clean-install observations. Only then call it fully working.

## Physical qualification handoff

1. Use the newly verified package and candidate identity from machine state.
   Recheck target ownership, preserve a rollback package and bind every run to
   the current boot, reserved DDR, exact loaded RBF and ARM executable.
2. Activate through the supported launcher/menu path and verify core identity.
   Record actual output mode, target version, commands and cleanup result.
3. Run the gate matrix on the same candidate: HDMI, direct RGB and
   analog/scandoubler; stereo endurance; keyboard/mouse/controller, OSD focus;
   both campaigns, saves, multiplayer and reset/core switch; cadence and latency.
4. Use `support/scripts/board_runner.py` with candidate-bound, immutable physical
   observations. Missing observations remain open; a configuration file alone
   does not constitute evidence.
5. On a clean supported target image, verify install, update, interrupted update,
   rollback, menu return, second launch and save preservation. Preserve user data.

## Token-efficient execution and next action

Read only the current status and next action in the [progress handoff](PROGRESS.md), then the active defect and acceptance procedure in [PLAN.md](PLAN.md). The archived plan history retains older critical-path decisions and runtime observations; it does not override the live status or gates.

- Resolve known FPGA defects, pass focused production-RTL tests, independently
  review and commit the final source/file-list packet before any new Quartus run.
- Build once per stabilized FPGA input identity. Reuse unchanged qualified ARM,
  ABI and assets. Prose, receipt and test-only changes do not trigger synthesis.
- Use one defect owner and one necessary reviewer; stop speculative preparation
  and repeated historical audits. Reuse verified tool commands; escalate repeated
  failures rather than repairing unrelated environments.
- Bind one development package, run MiSTer launch/video/audio/input/save smoke
  tests, fix observed failures, then complete the remaining physical matrix.
  Keep every release criterion intact and distinguish missing observations from
  local software work.

**Next action:** finish the full candidate-bound title → cinematic → title MiSTer cycle
on repaired candidate `b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b` and record the user-observed visual result;
then complete controls/OSD, save/relaunch, campaign, endurance/performance,
installation/rollback and remaining physical gates. The ARM artifact and 191-file
package are verified, the qualified FPGA was reused, and no Quartus run is needed.
C26 remains the activated development-only, pre-fix baseline; repaired candidate
`b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b` is running from `/media/fat/_CodexDiabloCinematic_d2ccbc3` and is not
accepted until the physical visual cycle is observed. Its package receipt is
`.mister/evidence/receipts/20260908T-c26-cinematic-candidate-package-b537.json` (manifest SHA-256 `c344c81a45503ceb2b25fe939f8f135a1f63028f14f96e6c37cd0cdaa0e64f94`). Live receipt `.work/c26/cinematic-live-receipt-b537b12c.json` (SHA-256 `180e06138e6c7ce5261303a6373b45fded1414c588e3f36651be30d829d0d262`) records arm/fpga ready and fault=0; PCM underruns rose 0, 0, 6745 and 13465, so physical audio acceptance remains open. The 375 kHz IO fix, actual-source regression,
`files.qip` registration, clean C26 FPGA qualification and focused cinematic
helper/adapter regression are complete; C25 external IO/physical evidence and
full cinematic hardware evidence remain open. Do not run Quartus unless an FPGA
input changes or compile/timing failure requires it.

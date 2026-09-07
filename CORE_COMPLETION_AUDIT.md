# Diablo MiSTer — completion execution plan

**Status: not release-ready; no current accepted candidate. Updated 7 September
2026.** Start here. Follow the seven batches below in order. The detailed
[C01–C34 work packages](reports/audit-2026-09-07/PROPOSED_PLAN.md) remain the
implementation/closure authority; the
[audit refresh](reports/audit-2026-09-07/REFRESH_AUDIT.md) adds mandatory R01–R05
fixes. [Machine state](.mister/state.json) records the active action and evidence;
the [gate matrix](support/qualification/closure-gates.json) defines measurable
acceptance. Earlier bring-up claims are preserved in the
[historical guide](reports/audit-2026-09-07/HISTORICAL_COMPLETION_GUIDE.md).

The current development candidate is `08b43647e181c2c099ddc77049e44d7e40f3ab26fd94d07334bb9157d07284e4`, bound by
`.mister/evidence/candidates/fpga-candidate-20260907-6-arm.json`. Its configured
local host/RTL and ARM/QEMU receipts pass for the exact manifest; those receipts
are local and ABI-emulation evidence only. The candidate is not board-accepted:
current-boot loader admission, target mapping, physical I/O, campaign equality,
performance and release promotion remain open. The earlier unconfigured local
run is retained as an incomplete receipt rather than a pass. Local tests do not
establish a complete MiSTer core.

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

**C18/C26–C31; R01–R03.** Preserve existing work and immutable historical
receipts. Freeze a reviewable implementation snapshot; inventory staged and
unstaged implementation, generated files, dependencies and licensing. Keep
pinned source identities, `game/` and donor trees read-only. Do not commit
unrelated work or copy private MPQs into the snapshot.

Fix the two reproduced evidence bugs first:

1. Closure evaluation must inspect typed artifact contents, required test IDs,
   complete coverage/measurements and transitive log hashes; bind a mandatory
   validated candidate and reject failed/skipped/incomplete evidence. The
   current checker incorrectly accepts failing synthetic evidence as eligible.
2. Verification must run from an isolated immutable snapshot and reject changed
   sources/artifacts before receipt publication. The current runner can publish
   pass for an input changed during its own run.

Exit: both refresh reproductions become negative regression tests; all gate
targets and release candidate requirements are machine-enforced. Record current
work separately from accepted work. Preserve C01–C34 identifiers and mark fixes
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

**C13/C16/C17/C24/C28/C32; R04/R05.** Implement the concrete MiSTer menu loader
and target profile; the generic supervisor is groundwork. Supply the board
adapter missing from `verify --suite board`.

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

Evaluate an actual closure record against the hardened matrix. Every required
C-item and R01–R05 amendment must have matching evidence. Reopen affected gates
after implementation/configuration changes. Remove generated root artifacts only
after retaining their evidence and setting ignore rules. Publish a concise release
record identifying exactly what was tested and delivered.

Exit: every required feature/measurable gate passes; package hashes match the
qualified candidate and clean-install observations. Only then call it fully working.

## Token-efficient execution and next action

- Read this guide/state first; open only the active C-package and exact evidence
  needed. Keep logs/captures in files via Context Mode or bounded Capsule output.
  Never reread the entire detailed plan each turn.
- Use one work ledger with status, dependency, next action, source/candidate ID
  and receipt pointer. Do not duplicate long histories in state or chat.
- Batch related checks once per snapshot. Finish cheap regressions before ARM/
  Quartus/board runs. Reuse receipts only when complete dependency identity still
  matches; `not_run` is never a pass.
- Stabilize ABI/ownership changes before expensive builds. Keep a known-good
  rollback package and change one measured bottleneck at a time. Avoid concurrent
  writers to shared mutable build paths.

**Next action:** execute Batch 1 R02/R03 negative regressions and fixes, then freeze
the implementation. Finish the deployment/target adapter contract and integrated
blockers before rebuilding a new candidate. Do not resume physical acceptance
using the stale candidate named in earlier receipts.

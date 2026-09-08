# Archived PLAN scheduling and progress history

> Moved out of the authoritative root [PLAN.md](../../../PLAN.md) on 8 September 2026. Current status and next actions are in [PROGRESS.md](../../../PROGRESS.md). The detailed C01–C34/R01–R13 acceptance procedures remain in PLAN.md.

## EXECUTION STATE

### Active entry point — implementation resumed, 8 September 2026

This block is the scheduling authority. The C01–C34 procedures and R01–R13 amendments below remain the detailed acceptance specification; `support/qualification/closure-gates.json` remains the machine-enforced scope and numeric-target contract. The root guide's **Next-chat handoff** supplies the last recorded runtime observations. Older sections saying “current”, “next” or “underway” are dated history, not instructions to repeat completed work. Resolve any newer evidence by updating this block once, without rewriting historical receipts.

- **Done, recorded:** 375 kHz IO correction and production-source regression; clean C26 FPGA compile/compress/full timing; cinematic ARM repair `d2ccbc3`, focused regression/independent review, ARM link, package verification and 191/191 target hashes. These are scoped implementation/build results, not release closure.
- **In progress:** candidate-bound integrated target trace and the remaining physical/release matrix. The clean-checkout repair at commit `0782c88` has a passing committed local receipt, and the endpoint-aligned ARM replay is complete; development candidate `b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b` remains development-only. No accepted release exists.
- **Physical observation received:** the user confirms the repaired title → cinematic → title cycle displayed correctly. Record this as visual-cycle evidence only; correlate the live target/package identity in the active diagnostic receipt. It does not close audio, other connectors, full scene equality or campaign coverage.
- **Authorized output scope, 8 September 2026:** the user specifies a standard MiSTer, says only HDMI can be tested, and requests best-effort CRT/direct-video settings. HDMI is the required physically qualified output for this delivery. Retain CRT/direct-video implementation with documented standard-framework assumptions, explicitly untested/unqualified; do not claim connector measurements or guaranteed CRT compatibility. This narrowly supersedes mandatory physical testing of the two non-HDMI rows in C13/C23/C25/C31/C32. Keep their source/mux safety checks and all HDMI, campaign, audio, controls, lifecycle and performance requirements. Commit `ebc724d` implements and independently verifies per-mode enforcement (22 focused tests and matrix check pass; matrix SHA-256 `ba1759b50674f62b0366c52b84bfae4dadba4cebfa193af7b2d8ced3779125c4`). Old matrix-bound closures require revalidation. No whole-item waiver or physical pass is granted.
- **Open:** candidate-bound FPGA qualification for the accepted PCM diagnostic, active-load attribution/endurance qualification and the remaining C01–C34/R01–R13 integrated/release evidence, including C25 external board/timing contracts. The user reports good audio; counters alone do not establish an audible defect. The diagnostic implementation is accepted only; no hardware or release acceptance is implied. Missing Git remote blocks the historical push only.
- **C25 evidence:** `.work/goal-c25/c25-residual-contract-gap-report.md` and `.work/goal-c25/c25-contract-evidence.json` retain 3 residual inputs/10 outputs. Board measurements remain unknown; CRT/direct video remain best-effort untested under the user's HDMI scope.
- **Diagnostic packet accepted, commit `e7b7b18`:** coherent ring/local-FIFO queues, short/malformed fixture rejection, maintained host registration and independent review pass; host receipt `.mister/evidence/receipts/20260908T091523Z-d9262832-6116-4d22-a50f-a57cf3a24561.json`. Reviewed ARM diagnostic SHA-256 `f0a2087ff2ac438b4db2a1bd2f71f6da05d82de513f9efd272d5651f807861a1` is built/staged and target-hash verified. Earlier `30a2a526` helper and idle observations are superseded by the active receipt.
- **Provenance/preflight accepted:** commit `82ceac1` validates the retained ARM-reference build through typed, re-derived recipe/source/build-log/artifact evidence (16 focused tests and independent review pass); it proves historical local provenance only, not a new clean build. Commit `3c7888a` admits replay assets before QEMU, verifies optional manifest paths/hashes, rejects traversal/symlink escapes, and passes five WSL tests plus independent review. Its timeout/different-state runs remain historical incomplete evidence. The completed comparison below is the current endpoint result; preserve the older receipts without relabeling them.
- **Target handoff:** after explicit authorization to switch from Crack Down, Diablo launched successfully on boot `0cd4f2ef-9ab9-4653-bc72-cba05f3490e2`; recorded launcher/MiSTer/engine PIDs 6519/6532/6534. `.work/goal-audio/runtime-pcm-receipt-f0a2087f.json` binds runtime identity. Revalidate before any later target mutation; preserve ongoing gameplay.
- **Gameplay/audio observations:** the user confirms gameplay looks good and explicitly says "audio is good!". These pass the observed-session physical video/listening checks, without asserting full campaign or endurance coverage. Three genuine 640x480 FPGA indexed-framebuffer readbacks were captured and visually inspected at `.work/goal-audio/screenshots/mister-indexed-readback-01.png` through `-03.png`, with `capture-metadata.json`; these are not physical HDMI captures.
- **Replay endpoint accepted:** `.work/goal-replay-endpoint/completed-comparison.json` binds the exact reference `4ef9b4…5189e2` and repaired `67e82c…7909ed` binaries to completed CLI runs, both exit 0 and original comparator pass. Both final archives are 484600 bytes with SHA-256 `f376e442a818f16f2e2504df756ff16ac8e5d8bb11e6191c35c0cba6227adf6c`. Independent parser/source review corrects the earlier count: 4,853 GameTick records, matching both terminal logs. The prior 120-second A/B stopped at 2309/1500 ticks and remains historical incomplete evidence, not a regression. This closes this save-oracle replay only; no hardware, image, performance or full campaign acceptance is implied.
- **PCM causal diagnostic accepted, commit `9bf880a`:** `.work/goal-audio/steady-gameplay-20260908/{receipt.json,summary.json,packet-index.json}` records 120/120 samples on one stable epoch, producer/consumer both advancing `+6196941`, display/last-frame `+5652`, underruns `+33685`, resync `0`, and no input drops. The new 48-byte ABI tail at offset 424 captures the first active underflow's event cycle, epoch, producer/fetch/published-consumer cursors, underrun count, local queue, player state, DDR-arbiter state, resync count and commit marker; commit/epoch checks, reset invalidation and old-image unavailable handling preserve coherent reads. Independent player/long/arbiter/integrated RTL, host ABI and WSL state-dump checks pass. This is diagnostic-only and does not establish physical sound quality or hardware acceptance. Reproducible FPGA compile/timing/compress for `9bf880a` is delegated to `.work/goal-pcm-fpga-9bf880a`; C15 remains open for candidate-bound build/trace, endurance and physical stereo/zero-steady-delta evidence.
- **Clean-checkout repair accepted, commit `0782c88`:** source-only verification materializes only an absent deterministic `build_id.v` with recorded provenance and cleanup; candidate/board validation stays strict. Synthetic provenance tests are hermetic, absent retained evidence is explicitly skipped, and malformed present metadata fails. The committed local receipt `.work/goal-integrated/committed-0782c88/.mister/evidence/receipts/20260908T101424Z-ed322804-db33-493c-adfb-48d53ed5bc46.json` passes all 23 recorded steps; the isolated foundation run passed 168 tests with three explicit skips (two Windows symlink cases and absent retained-reference evidence). The committed plan is pinned LF and fresh-checkout guide digest validation passes. This closes the local verification packet only; ARM/target, physical HDMI, campaign, performance and release gates remain open.
- **Next dependency-ready work:** complete the delegated reproducible FPGA compile/timing/compress for `9bf880a`, then use the sequence below after implementation resumes. Do not rerun the completed IO repair, C34 extraction or unchanged replay artifacts because an older paragraph calls them pending.
- **Key decisions:** reuse artifacts only when complete relevant inputs match; retain immutable candidate/evidence identities; one critical-path defect owner and a separate verifier; physical observations and full numeric/coverage requirements remain mandatory.
- **Completion condition:** implement and independently verify every mandatory C01–C34/R01–R13 gate, update this state as packets land, and accept only the fully qualified integrated result. The earlier plan-only stop instruction is superseded by the user's implementation goal. Hardware observations and missing external inputs remain explicit blockers, not waived gates.

### Resume sequence and packet boundaries

| Order / ownership | Bounded outcome | Admission and completion evidence |
| --- | --- | --- |
| 1 — one target owner | Revalidate the existing development runtime and obtain the repaired title → cinematic → title observation. | Read-only boot/core/package/lease check first; preserve the running session and pending observation. Bind the observation to the exact candidate and connector. CRC/counter changes alone cannot pass visual acceptance. |
| 2 — diagnostic owner, then independent verifier | Qualify the accepted PCM underflow-event snapshot and resolve pauses versus starvation before selecting a fix. | Use the ABI queue fields and event snapshot together; record `queued_frames`, `local_queue_frames`, producer/consumer, callback/drop/underrun/resync counters, epoch and lifecycle phase. Split traces at resets and startup/steady boundaries. Do not infer occupancy or increase buffers from cursor deltas alone. Preserve raw trace and identify a reproducible failing interval or an explicitly unresolved result. |
| Parallel local packet, separate files | Make repaired-binary replay select the exact build; run the candidate-bound local deployment lifecycle. | The root handoff records that `scenario_arm.py` hardcodes an older build. Parameterize only the build selection, verify binary role/hash, then replay the repaired transport binary where supported. ARM-reference scenes remain software-oracle evidence. Neither replay nor a local deployment fixture substitutes for physical acceptance. |
| Parallel read-only packet | Collect the missing C25 board/receiver/configuration contracts. | Record actual board/revision, USER_IO use, receiver limits and RC/skew evidence for unresolved endpoints. Keep unavailable inputs blocked. Do not change SDC/RTL from nominal assumptions. |
| 3 — source boundary | If diagnosis exposes a defect, implement and independently verify only that defect; qualify affected artifacts once. | Focused regression → independent diff acceptance → reviewed source snapshot → affected build/suite → immutable candidate/package binding. Reuse the qualified FPGA for ARM-only changes. Reopen affected evidence under C31; never relabel old receipts. |
| 4 — coordinated target session | Pass launch/video/audio/input/OSD/save/relaunch smoke, then complete remaining coverage. | Reuse one compatible candidate and session for C13/C15/C19–C24/C32 when fixtures and observations match. Retain every required campaign, connector, input, multiplayer and lifecycle cell, all duration/latency targets and separate diagnostic/performance configurations. A shared run may support several gates only when it actually satisfies each gate. |
| 5 — independent integrated acceptance | Validate final candidate-bound evidence, reconcile C30 state, and evaluate every required closure. | Existing validators must pass with no missing mandatory result. Mark implementation complete separately from release acceptance; promote only after the full matrix and R01–R13 amendments close. |

**Dependency decision:** distinguish readiness to collect evidence from permission to close a gate. C18 development identity and C32 development packaging must exist before physical qualification; their final acceptance follows it. C26/C27 build proof, C28/C29 runners and C31 scope can be used while final closure is open. Do not create a deadlock by requiring an accepted release before running its acceptance tests. This does not remove any closure dependency.

**Invalidation decision:** documentation-only edits require guide/link/digest validation, not ARM/FPGA rebuilds or a new candidate. Test/runner changes require their focused checks and affected qualification receipts; ARM inputs require ARM rebuild and affected integration/board checks; RTL/QIP/SDC/ABI changes require the corresponding production regressions and FPGA/timing or peer rebuilds. Inspect transitive inputs, tool/options and configuration before reuse; if the existing manifest validator rejects a changed dependency, retain that rejection and resolve it through the existing workflow rather than bypassing validation.

**Token decision:** on resume read this block, the active C-item and exact referenced evidence only. Keep one compact result/receipt pointer per packet, replacing the active state rather than appending another “current” narrative. Use Context Mode for bounded command/log analysis and Capsule for large/repeated evidence when available. Dispatch Luna MAX with objective, exclusive write scope, constraints, relevant excerpt, acceptance and compact return; use Terra XHIGH after two failed bounded attempts or for a concrete cross-component escalation. Do not redelegate successful exploration or repeat broad qualification without an invalidating change.

**Existing commands:** run from the repository root with the configured Python/tool environment. For this documentation edit, run `python support/scripts/guide_status.py --root .` after synchronizing only `.mister/state.json`'s `completion_document_sha256`; expect `ok=true`. For future implementation, `python support/scripts/diablo.py verify --suite foundation` runs foundation checks and `python support/scripts/diablo.py verify --suite local` runs the configured local tier. These unbound commands do not establish candidate acceptance. Recover candidate/ARM/board-specific arguments, build paths and tool configuration from the exact successful receipt and existing CLI help; do not copy historical candidate paths or omit required identity/profile arguments. Use the existing Quartus snapshot helper in C27 only when FPGA inputs change. Missing prerequisites are `not_run`/blocked, never pass.

### Historical stop and next-chat handoff

Implementation and testing stopped after the passive audio trace recorded below. The **Next-chat handoff** at the top of `CORE_COMPLETION_AUDIT.md` records that checkpoint: repaired candidate b537b12c was deployed development-only; cinematic visual acceptance and audio diagnosis remained open; the full release matrix remains mandatory. That earlier session ended with the handoff and requested push attempt. Push failed because no Git remote is configured; the destination URL remains pending. This is historical session scope, not a new instruction to push during a plan edit.

Final passive trace: `.work/c26/cinematic-pcm-passive-trace-b537b12c.summary.json` (SHA-256 `26961f57e588067e0ecd600389eabacdc202ce0bf3a818587de15964ac5a37f3`). Ninety samples remained ready/fault 0; producer/consumer each advanced 3,802,872 and display frames 1,307, with 13 fully unchanged intervals and three absolute producer/consumer mismatches (maximum 2,229). The underrun counter reset from 121,171 to 0; do not calculate one cumulative delta across reset. Installed diagnostics omit both queue-occupancy fields, so pauses versus starvation remain unresolved. Exact boot is `0cd4f2ef-9ab9-4653-bc72-cba05f3490e2`; earlier `cbaa05` text is a transcription error. WSL QEMU 10.2.1 is currently available, but repaired-binary replay has not run. The runtime was left running; revalidate it on resume.

### Recorded live-test checkpoint — cinematic video remains unaccepted

This update supersedes the earlier window/not-activated status below. The user authorized MiSTer testing; C26 remains the pre-fix development baseline, and repaired candidate b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b is now running from `/media/fat/_CodexDiabloCinematic_d2ccbc3`. The user confirms animated title and good audio, followed after approximately 30 seconds by a frozen title while cinematic audio plays. Source tracing proves the generic ARM presentation hook republishes `PalSurface` while movies update a separate indexed `SVidSurface`. The persistent engine and FPGA acknowledgements continue: this is not an ended test or proof of queue deadlock.

- Next: finish the full candidate-bound title → cinematic → title physical cycle on repaired candidate b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b; its visual result is pending user observation. Then complete controls/OSD, save/relaunch, campaign, endurance/performance, installation/rollback and remaining C25 gates. The ARM build and package are verified by `.mister/evidence/receipts/20260908T-c26-cinematic-candidate-package-b537.json` (engine SHA-256 `67e82c01d45050f4ea7892f75d33cd9f2075be7ce02425aa9529fa11de7909ed`, package manifest SHA-256 `c344c81a45503ceb2b25fe939f8f135a1f63028f14f96e6c37cd0cdaa0e64f94`); the qualified FPGA was reused and no Quartus run is justified.
- Repair contract: handle movie presentation without falling through to stale title publication on transient backpressure; preserve transport-disabled SDL fallback, movie timing, dynamic palettes, aspect/letterboxing and return to title. Unsupported input and persistent runtime failures must remain diagnosable. Do not disable movies or alter the pinned donor directly.
- Geometry finding: the ten SMK2 streams found by a read-only DIABDAT header scan are 320×156, while transport consumes a fixed 640×480 indexed frame. Match the donor aspect-fit behavior: these movies occupy 640×312 centered at y=84. Use an indexed scratch frame with the current movie palette and SDL's palette mapping for black borders; if no exact black exists, preserve movie colors and use the nearest border color rather than suppressing playback. Test geometry and nonzero black palette indices explicitly.
- Acceptance: changing indexed movie pixels and palettes against a static title buffer, forced backpressure, disabled transport, and return to title through actual integration; then observe the full title → cinematic → title cycle on the current repaired candidate. A short startup smoke cannot close this blocker. Equal sampled descriptor CRCs alone do not prove final output is frozen.
- Resolved inputs: test authorization and game-data availability. Full Diablo plus all four Hellfire MPQs are privately staged and hash verified at `/media/fat/_CodexDiabloGameData`. Preserve user saves/configuration and keep private assets out of packages and Git.
- Still open: remaining physical matrix, controls/OSD, save/relaunch, campaigns/multiplayer, endurance/performance, installation/rollback and C25 external timing/configuration proof. Title animation and audio observations are scoped development evidence, not release acceptance.
- Evidence: `.work/c26/frame-backpressure-diagnosis.md`; repaired candidate `b537b12c1dc8afbd36cb2c5e82d0a58cff4be2f50ca60d0cf38badb540b49c7b` is running from `/media/fat/_CodexDiabloCinematic_d2ccbc3`, while its physical visual result remains pending.
- Local repair evidence: `.mister/evidence/receipts/20260908T070956Z-transport-cinematic-d2918ef76bc7433597d994ee330f8efa.json` passes real helper/adapter tests and static generated-hook checks. Actual SDL execution rejected the initial indexed `SDL_BlitScaled` approach (`Blit combination not supported`); the repair uses pitch-aware, locked, center-sampled indexed copying. A missing transport include in the generated source was also corrected. Keep those failures as regression evidence; do not retry the unsupported SDL scaling approach.
- Candidate provenance: `.mister/evidence/receipts/20260908T-c26-cinematic-candidate-package-b537.json` verifies 191 target/package files and excludes private data; the target hash check is 191/191 with healthy startup/launcher at boot `0cd4f2ef-9ab9-4653-bc72-cbaa05f3490e2`. Live receipt `.work/c26/cinematic-live-receipt-b537b12c.json` (SHA-256 `180e06138e6c7ce5261303a6373b45fded1414c588e3f36651be30d829d0d262`) records 191/191 target hashes, boot `0cd4f2ef-9ab9-4653-bc72-cbaa05f3490e2`, launcher 2515 and engine 2524; full-CRC samples advanced with arm/fpga ready, fault=0 and zero conversion diagnostics. PCM underruns were 0, 0, 6745 and 13465 (+13465); no physical audio acceptance is claimed. The user visual title/movie/title result remains pending, so this is not a visual pass.

### Earlier qualification checkpoint (historical)

- Done: the MCP23009 375 kHz correction, actual-source 375/400/500 kHz regression and `files.qip` registration are committed in `ca6f541`; synchronized source/docs are committed in `0232f7`. Clean C26 FPGA qualification passed with compile/compress/full STA exit 0 and positive four-corner metrics. Development candidate `8530508c0923c8d14766f584019bb4bd5b78ed614c95facb474d5b6788ed1376` is locally verified and staged.
- In progress: no local FPGA defect remains. The staged 192-file development package `.work/package-board-c26-0232f7` is not activated and awaits an exclusive MiSTer test window.
- Open external requirements: C25 as a whole remains open for residual HDMI/IO timing contracts, IO-board/revision and USER_IO configuration, and physical output/observer evidence. The target window is also open; recheck the foreign target read-only rather than interrupt it.
- Next: at the next available exclusive window, run read-only boot/data/DDR preflight, then smoke-first launch/video/audio/input/save checks before the remaining physical matrix. Do not run Quartus for prose or state synchronization.
- Decisions: the IO-rate defect is locally fixed and separately verified; retain every physical/release gate. Reuse the exact C26 package, candidate and staging receipts; do not mint another candidate for bookkeeping.
- Current development package: candidate manifest `.mister/evidence/candidates/fpga-candidate-20260908-c26-0232f7.json` (SHA-256 `b51d4a9821686cf7032e6c9bb48768df71453b4f30376de196902571a017abf0`), package manifest SHA-256 `8d4b9deebaf6849fe9487bac93ab8a6d4d00079b7026bcbf5eae434fed92ed9b`, staged at `\\192.168.0.69\sdcard\_CodexDiabloC26_0232f7`; it is development-only and not activated.

### C25 proven blocker: MCP23009 Fast-mode timing

The architecture review traced the actual 50 MHz clock through the shared divider: 500 kHz produces 1.000 us SCL low/high periods, while Fast mode requires SCL low >=1.3 us and frequency <=400 kHz. The MCP23009-only parameter is now `375_000`, giving 66/67 fabric cycles per half-period and a minimum 1.320 us low/high period. Actual-source regression accepts 375 kHz and rejects 400/500 kHz low timing; the local defect is closed.

The corrected source packet, clean C26 FPGA build and staged package now bind the implementation evidence. C25 remains open only for the separate external board RC/skew, IO-board/USER_IO and physical matrix requirements; none is evidence for changing the proven local divider correction.

## Critical path and efficiency decisions

### Findings from the current execution

The objective remains a fully functional, accepted MiSTer core. The highest-value efficiency changes address observed waste: a Quartus build completed before the remaining IO-rate decision; repeated simulator setup/quoting failures delayed a one-parameter fix; preparation and handoffs continued without advancing the next functional test. Stop those loops. Preserve successful historical evidence without repeating or upgrading its scope.

| Current blocker | Shortest next action and required proof |
| --- | --- |
| IO-rate regression and video-policy registration are recorded complete | Preserve commits `ca6f541` and `0232f7` and the clean C26 qualification. Reopen only on changed relevant inputs or an observed regression. |
| Repaired cinematic video remains physically unaccepted | Revalidate candidate b537b12c and observe the full title → cinematic → title cycle; do not rebuild its unchanged FPGA. |
| PCM trace cannot distinguish pauses from starvation | Collect queue occupancy and lifecycle/reset boundaries before selecting a repair; follow the bounded diagnostic packet above. |
| Remaining clean-checkout/integrated qualification | Reuse existing producer/build receipts where dependencies still match; execute only missing or invalidated proof through the existing workflow. Do not design another qualification framework. |
| Remaining external timing contracts | Use known device limits plus actual board/configuration evidence. IO-board/revision, USER_IO use, RC/skew and relevant receiver settings remain inputs to acceptance. Do not invent delays or start speculative RTL work. |
| Candidate-bound physical acceptance | Obtain an available MiSTer window and physical display/audio observation or capture. Recheck boot/core identity once at admission; do not poll or interrupt a changing foreign workload. |

### Firm Quartus pre-build gate

No additional Quartus run until: (1) all currently known FPGA-affecting defect decisions are resolved; (2) focused regressions pass using production RTL; (3) independent review accepts the final diff; (4) the exact source/file-list packet is committed; and (5) snapshot dependencies match that commit. Record those five checks in the existing work receipt, without creating a new gate framework. Then run one fresh compile/compress/full timing flow for that input identity. Do not launch an overlapping build while a known source decision can invalidate it.

Rebuild again only for an FPGA input change or an actual compile/timing failure requiring a fix. Documentation, Git bookkeeping, test-only files and receipt updates do not justify another Quartus run. Reuse the clean ARM executable, assets and ABI artifacts when their complete dependency identities still match. Check hashes once at package binding; do not mint successive candidates for prose changes. Static timing acceptance and physical acceptance remain mandatory.

### Fastest route to working hardware

Start from the recorded repaired cinematic development package, revalidate its identity, finish the physical cycle observation and diagnose audio. If a defect requires a source change, qualify only the affected artifacts under the pre-build gate and bind one immutable **development** package with rollback. Use it first for supported launch, visible image, active stereo, controls/OSD focus, and save/relaunch. Fix observed failures before long endurance/campaign/performance runs. When the smoke test passes, collect the remaining required output modes, stereo endurance, campaigns, multiplayer, reset/core switch, latency and installation/update/rollback matrix in one coordinated session on that candidate where dependencies permit. A development candidate may collect missing evidence; it is never labeled an accepted release prematurely.

### Execution rules that reduce time and tokens

- Keep one implementation owner for the active defect. Give a second worker only a concrete independent review or a necessary task that advances the critical path; idle slots are acceptable. Stop speculative preparation, repeated historical audits, cosmetic refactors and unrelated warning cleanup.
- Use the known native WSL Verilator 5.050 route (`/home/meath/.local/bin/verilator`, resolved installation under `/home/meath/.cache/veriemu-next/src/verilator-5.050`), native compiler and established WSL path helpers. Persist the successful exact command in the existing runner/receipt once. Do not rediscover tools or fall back to known-incompatible Icarus/older Verilator for the aggregate RTL syntax.
- Report the first unexpected failure with exact command/result. After two failed recovery attempts, escalate once to Terra with files/logs rather than repeating the same loop. Recovery packets report after at most eight tool calls. Use structured arguments or script files rather than nested PowerShell/Bash quoting.
- Run a focused test before broad regression or synthesis. Repeat checks only for changed dependencies, actual failures or unresolved results. Batch routine documentation/link/hash checks at a source boundary; independently review critical code and acceptance changes, not every bookkeeping edit.
- Maintain this execution block plus compact receipt pointers. Keep raw logs and captures in files, retrieve only exact relevant evidence, and avoid repeated status narratives or large file reads. Preserve histories as histories; do not recatalog them unless reproducibility is actually blocked.
- When only external configuration/observation is missing, state the precise required input and keep that gate open. Do not spend further local tokens trying to manufacture physical evidence or weaken completion requirements.

Completion still requires every mandatory gate and candidate-bound evidence. This sequence reduces wasted work; it does not waive timing, physical, campaign, multiplayer, performance or installation acceptance.

## Historical execution state — C34 requalification

There is no accepted release candidate. Candidate49 and its package are historical:
C34 source changes supersede their source qualification. Freeze the implementation,
rebuild affected artifacts and qualify a new immutable candidate before promotion.
Historical checkpoints below retain their original scope; the top execution
state governs current work and records later qualification.

C34 implementation now separates input reconciliation, callback-local PCM
resampling, command/frame ownership and profiling into four components documented
in `support/TRANSPORT_OWNERSHIP.md`. Adapter retains runtime lifetime, callback
admission and transport orchestration. Command publication/reconciliation borrows
runtime per synchronous call. The adapter is approximately 490 lines. Duplicate
initialization and the obsolete slot-zero RTL comment were corrected. Command
wait accounting now records one sample per submission, including timeout followed
by late completion, and rejects invalid/backward timestamps.

Pre-review baseline evidence (source snapshot
`affa173cd5e6639ed5e43a9a4baa972e51e54aaaf6862723d31268ffa4a96465`):

| Check | Result and receipt |
| --- | --- |
| Full local suite | All 21 registered checks pass; `.mister/evidence/receipts/20260908T015436Z-febcee74-f4f6-4c7c-b610-3d6bb84a559f.json`. Includes independent owners, 64 reset cycles, PCM chunk equivalence, malformed callbacks, command wait and bounded trace regressions. |
| Configured ARM ABI/QEMU suite | Pass; `.mister/evidence/receipts/20260908T015737Z-1654e8e0-ebc5-4e8a-889d-ef85c8b95009.json`. The earlier missing-toolchain attempt remains incomplete. |
| Production ARM incremental rebuild | Pass with unchanged before/after source identity; `.mister/evidence/receipts/20260908T-c34-arm-engine-rebuild.json`. Executable `.work/build/arm-engine-c34-ownership/devilutionx`, SHA-256 `d790990953427fa3df2146529b9a17f91f4549b9cd749e7c504793651a39e214`. This is not clean-build proof. |
| ARM executable startup | QEMU `--version` exits 0; `.mister/evidence/receipts/20260908T-c34-arm-version-smoke.json`. Startup only; no gameplay or hardware acceptance. |

Independent review found no extraction ownership/lifetime regression, but identified
three corrections now implemented and passing the focused host regression.
Full qualification must be refreshed for these changed headers:

| Bug | Fix and acceptance |
| --- | --- |
| Profiler reset leaves command metrics behind; Adapter compensates with direct field writes. | Move all metric clearing into `ResetProfile`, remove compensating writes, and verify dirty counters all reset through the owner API. |
| Command-build duration subtracts a zero/backward clock reading. | Guard the timing sample before subtraction, apply the existing invalid-sample policy, and test zero/backward/valid samples. |
| The stated 60 Hz limiter uses fixed 16 ms intervals (62.5 Hz) and static shared deadline state. | Use per-adapter resettable fractional 60 Hz deadlines, retain wrap/lag recovery, and test deterministic cadence/reset/wrap behavior. |

C33 producer execution now passes in
`.mister/evidence/receipts/20260908T021850Z-c33-producer-proof-4fea2af2-836b-49d1-9936-919113740560.json`
(SHA-256 `5d201bf40dbb634b5be47d8f2762e192167c4dd31edc41ec7eb8ba870d703b4b`).
The isolated snapshot ran foundation (141 tests, one declared privilege skip),
all 14 RTL steps and the FPGA snapshot-sync producer. Inputs stayed byte-identical;
no direct root files appeared. Logs, generated simulations and nested receipts
identify actual output destinations. Quartus compile-output proof and C18/C26
closure dependencies remain separate; this is not full C33 closure.

The fresh ARM build passes with all 1,537 engine inputs unchanged in
`.mister/evidence/receipts/20260908T-c34-clean-arm-engine-build.json`. The exact
executable `.work/build/arm-engine-c34-clean/devilutionx` has SHA-256
`6cfc2c80ff0c2fedf4dd5ea4a91cfad7339fac7f67828421465c4f1d7b324989` and passes
QEMU startup in `.mister/evidence/receipts/20260908T-c34-clean-arm-version-smoke.json`.
Concurrent changes were confined to test infrastructure; engine-input provenance
is valid. Whole-source/candidate and physical acceptance remain separate gates.
Use the fresh FPGA paths under `.work/c34/output_files`, not an older build's
path merely because its RBF hash is identical.

The real file-backed adapter lifecycle regression is implemented in commit
`bb2bf6f`: 64 production initialize/shutdown/rebind cycles, idempotence, frame
ownership reset and concurrent PCM callback admission pass. Focused receipt:
`.mister/evidence/receipts/20260908T023835Z-transport-lifecycle-232e187fbf42483db41fe6dc472bd781.json`
(SHA-256 `4ef96eca52af2e020063a34af25c3d39ba3fcaa7ad86cffe600f30beb6647fea`).
The registered host suite passes all seven checks in
`.mister/evidence/receipts/20260908T023847Z-934b4267-5c05-45fd-beac-064a0ac8614a.json`.
Independent verification accepted the C34 packet in commit `643f806`, including
the prerequisite decode of existing PCM health flags without packed ABI changes.
The full local suite passes 22/22 with no deferrals/failures/timeouts in
`.mister/evidence/receipts/20260908T025424Z-9aba44bd-ac7c-4391-9675-2f1f15f75e05.json`
(SHA-256 `6578d3846a06bbfb4761add8f7b5a4f8b6f390257d6491a7956f01e250f015f3`).
Review receipt `.mister/evidence/receipts/20260908T030000Z-c34-independent-acceptance.json`
records hash checks and guide/matrix validation. No candidate or board promotion follows;
these are Linux/WSL file-backed results, not FPGA or physical evidence.

C34 remains open for independent acceptance, scene/profiling qualification
and current artifact/candidate acceptance. C33 is reopened: the previous receipt
proved absence of two root outputs only. Run representative current build/test
producers in a fresh source snapshot and retain before/after inventories, output
destinations and closure dependencies. Ignore rules and directory listings alone
cannot close it.

User-provided Quartus is available at `D:/q17/quartus/bin64`. SSH access to
`192.168.0.69` succeeds; the last read-only snapshot showed only MiSTer, no matching
MAME/Diablo/installer process, on boot
`618a6107-3cbc-42ca-970e-b44c7c057a4d`. Recheck immediately before activation.
A subsequent SSH observation found an active NFS_SE deployment shell (PID 1504)
modifying runtime assets and MiSTer.ini. Activation is deferred until it finishes;
receipt `.mister/evidence/receipts/20260908T-c34-target-contention-observation.json`.
Earlier MAME-contention statements are historical observations. Physical HDMI,
direct RGB, analog/scandoubler, stereo endurance, controls/OSD, campaign/save/reset,
multiplayer, performance and install/update/rollback/menu/second-launch gates
remain open.

## Historical implementation checkpoint — candidate49

R02/R03/R04/R05/R06/R07/R08/R09 are implemented locally and regression-tested.
R12 is implemented: the board fallback explains that --board-configuration is
required and points to board_runner.py. C33 is reopened pending producer
execution evidence; C34 remains open because the
ownership refactor and regression/profiling proof are not complete. These
code fixes move implementation status forward without closing physical or
release evidence gates.

Candidate49 is a historical artifact-bound development candidate whose source inputs are superseded by C34/P01-P06; the following receipts are historical:
`d95d4cfd03154bd659343c5a77a1230bcd4efc7c45d81d4f2299a0d754128611`, manifest
`.mister/evidence/candidates/fpga-candidate-20260908-49-final-local.json`
(SHA-256 `f420873962a21317c8a9bdc9ff1ad07db02d9ad4299c2b9b5ff2e1abae802c4b`),
source `59d9a616708db186946cab362d6c66627a99d9a21a18b4bf6f97cb70a3e9eda0`.
Its FPGA/ARM artifact lineage remains candidate43. It binds the ARM transport executable SHA-256
`ead7cc2ac6417ce88833a66e7fcf400d85058061964a96f43a44658fb3bee87c`, fresh
SOF SHA-256 `ae7f6bbc69f6d52f00f9e3bb7637de35b8495dac7f72aadc8a2794889dce98e7`
and raw/compressed RBF SHA-256
`7b5eb62411233b96adc244d87fe3ee96b16da13b271fa608d9a70cafd4917b10`.
The build receipt `.mister/evidence/fpga-build-candidate43.json` (SHA-256
`f825d7ab8eaaccfd2f03699bb775c329b759d1bee5eebba648354334317fe2e2`) records
direct compile, compression and four setup corners with three paths per corner,
zero violations and 0.188 ns minimum positive slack.

Candidate49 local verification passes all 21 registered checks in
`.mister/evidence/receipts/20260908T005425Z-a0fbb81c-2ec1-4c90-813d-68bcf2de6e30.json`
(SHA-256 `8e63f45062e56abcba6c5806e4910198eda2f2a32cc8e0b4c479e8bccd0d68b3`),
and its configured ARM/QEMU suite passes in
`.mister/evidence/receipts/20260908T005732Z-35359e71-54c4-434f-9d29-91c9ec427c70.json`
(SHA-256 `286b11f449a9fb52eb3f22858782aa5ae8c683fa4b9d5913bdaf4f0118c6f585`).
Diablo and Hellfire role-aware scene-oracle receipts pass with five frames each
(`734578c7b6c8f5d2b9f8753087a6c5b6783fc528c1f94a4d5d2d74d5fe7ea278` and
`3e1075671cc486b5cf8cf5c253e52c080513acba8037aae3b722fe3844ec4331`).
Package49 contains 192 files/184 assets, verifies with package manifest SHA-256
`f09bd76e1b4c80d7eb6391409dc1724f573a5931d4cf644ed7092573e49e63f3`, and is
staged at `\\192.168.0.69\sdcard\_CodexDiabloCandidate49FinalLocal`. Its
passing target preflight is `.mister/evidence/receipts/20260908T-candidate49-preflight.json`
(SHA-256 `64d827d9d29953396c55be9314ae19fde04aa63820370573fab9de3d594a1b78`).
The candidate49 lifecycle receipt
`.mister/evidence/receipts/20260908T-candidate49-deployment-lifecycle.json`
(SHA-256 `324d8ad330f940de78d52d77f372b8c04cbf7dce10eeb3278e899410dee14c01`)
passes clean install, interrupted update preservation, update, rollback, save
preservation, manifest verification and staging cleanup. The full Python suite
now passes 141 tests with one declared Windows privilege skip.

Candidate42's old-RBF source-policy record remains historical and cannot be
promoted. Candidate49 is still development-only because the target is owned by
an external MAME core and no candidate49 physical HDMI/direct-RGB/analog capture,
active stereo-audio trace, controls, campaign/save/multiplayer, performance, menu
activation or clean-target acceptance evidence exists. Any source/RTL/ABI change
creates a new immutable candidate and invalidates affected receipts; a
package/tooling change regenerates candidate-bound release receipts.

## Bugs found and fixes recorded in this plan

| Finding | Impact | Fix now in the checkout | Remaining proof |
| --- | --- | --- | --- |
| The v1 package copied only runtime roles and omitted the redistributable asset tree. | A target launch could pass manifest checks and then fail on missing assets such as `ui_art/diablo.pal`. | Deployment and package manifests are v2; package creation requires `--assets`, verifies the complete tree and rejects private-looking paths. Package33 contains 184 assets and the package regression covers omission and hash drift. | Clean install/update/rollback and a real Diablo/Hellfire launch from the package. |
| The launcher opened the transport lease but did not inherit its POSIX file descriptor into the engine. | The engine could report transport ownership error 7 even though the launcher held the lock. | `mister_launcher.py` now passes the lock descriptor through `subprocess.Popen(..., pass_fds=...)`; the candidate31 normal target smoke proved the ownership path. | Repeat on candidate32 and complete the controlled exit receipt. |
| Loader admission did not prove that the exact requested RBF was the running MiSTer process. | A stale or different core could make FPGA state look healthy while the wrong core was being tested. | The launcher now matches `/proc/*/cmdline` against the exact requested RBF, records the current boot ID and requires FPGA `operating` state. | Resolve the observed AO486-versus-Diablo identity conflict with an independent target capture. |
| Timedemo disables the normal frame limiter and can flood the finite transport ring. | Candidate29/31 timedemo attempts rebooted the target during startup. | The ARM transport overlay adds an opt-in 60 Hz `PaceFrame()` deadline for `DIABLO_MISTER_FORCE_FRAME_PACING`; the launcher enables it only for `--timedemo`. Candidate32 survived its first six seconds. | Finish a candidate32 Diablo and Hellfire demo run with no reboot, no fault counter increase and a launcher pass receipt. |
| The board verification fallback returned a stale “board runner missing” explanation. | A CLI run without a board profile reported the wrong blocker and obscured the actionable configuration requirement. | The fallback now says `--board-configuration` is required and points to `support/scripts/board_runner.py`; a regression test locks the diagnostic. | Regenerate candidate-bound verification receipts after the hardware run. |
| The release package had no user-facing setup/notices and no executable update transaction. | A clean target could not verify data ownership, interrupted-update recovery or rollback from the distributed package. | `package_release.py` emits `NOTICE.txt` and `SETUP.md`; `deploy_package.py` uses verified staging, candidate-named releases and atomic activation; `deployment_lifecycle.py` records the full local transaction matrix. | Run the same package through a clean MiSTer install, menu entry, both campaigns and a second launch; retain physical acceptance receipts. |
| The board runner was import-only and could not publish a qualification receipt from its documented path. | Operators could not execute the candidate-bound configuration as a stable CLI result, encouraging ad-hoc evidence. | `board_runner.py` now exposes a shell-free CLI, bounded command capture and immutable JSON result publication; the regression covers repeat-run refusal. | Supply a real board configuration with candidate-bound video/audio/input/campaign/performance observations and run it on a quiescent target. |

## 2026-09-08 continuation: candidate38 fixes and release blockers

This section records the historical work order after the candidate38 implementation pass.
It records the bugs found while closing the plan, the fix now in the checkout,
the evidence already captured and the exact gate that remains. Historical
candidate33/35/36/37 paragraphs below remain evidence of earlier experiments.

| Finding | Implemented fix and evidence | Remaining blocker / next action |
| --- | --- | --- |
| ARM overlay configure failure | Restored the lost `string(REPLACE ...)` match string in `support/cmake/arm-transport.cmake`; the portable ARM overlay now configures and builds all 742 targets. | Keep a clean-snapshot configure/build receipt bound to the next promoted candidate. |
| Quartus PCM instantiation failure | Corrected `Diablo.sv` to pass `.PRIME_SAMPLES(8192)` and `.FIFO_SAMPLES(16384)` through the module parameter list. Candidate38 compiles, compresses and closes timing with zero violations. | Run the larger FIFO through the active campaign and long-duration board gates. |
| PCM starvation under active load | Changed the target callback to 1024 frames, enlarged the FPGA local FIFO, added local queue telemetry in `RingControl::flags`, and separated startup from steady counter deltas. Candidate38 normal60 shows queue 7257, startup underrun 6766 and steady delta 0. | C15 still requires 30 minutes per campaign, physical stereo inspection, no active drops and zero steady underrun/resync delta. |
| Candidate/package role drift | Candidate38 binds ARM transport, FPGA RBF, ABI, launcher and the complete 184-file asset tree. Package verification and target preflight pass; the package manifest SHA is `115998423d0409a2f10c192cf5c8487d340bc4bfd3cae2e2d88d37c1d3182896`. | C32 still requires clean-image install, update interruption, rollback, second launch, notices and both campaign workflows. |
| Target physical identity remains contradictory | The launcher observes the exact candidate38 RBF process and FPGA `operating` state, while the observer is black/stale and reports AO486. A target memory probe saw nonzero framebuffer/palette data. | C13/C25/C31 need an independent HDMI/analog capture and mode-matrix proof that identifies the displayed Diablo frame. |
| Licensed data is not distributable | The target launch uses `/media/fat/tmp_esc/diablo-transport-assets` for user-owned MPQs; the package excludes MPQs, saves and private captures. An assets-only root correctly fails with `missing campaign data: diabdat.mpq`. | C16/C32 need documented user-data setup plus Diablo/Hellfire launch, save/load, reset, switch-away/back and second-launch receipts. |
| Scandoubler timing is still unqualified | The imported `sys/scandoubler.v` TODO is replaced by the documented progressive 31 kHz VSync/VBlank pipeline and deterministic `.mono(1'b0)` connection; candidate43 timing passes all four setup corners. | Capture gameplay, sync and geometry on the analog/scandoubler row and retain the HDMI/direct-RGB rows as separate physical gates. |

**Historical gate order from candidate41 (superseded):** (1) use the candidate41 package and licensed target data to
complete Diablo and Hellfire normal/timedemo campaign runs; (2) capture physical
video identity and audio/control behavior; (3) measure 60-FPS/p99/latency and
30-minute endurance; (4) exercise install/update/rollback and second launch; and
(5) regenerate candidate-bound receipts, update `.mister/state.json`, evaluate
the C01–C34 matrix, and promote only if every required item is closed. A package
or launcher pass cannot bypass an open physical or performance gate.

## Candidate40 historical update — integrated-test fix and board-contingency record

Candidate40 was a historical source-bound development checkpoint after the
integrated DDR harness fix. The production PCM client now has a 13-bit queue
telemetry port for the 4096-sample default FIFO, while the integrated testbench
had retained an 11-bit wire and a race-prone final `reads == responses` assertion.
The harness now uses `[12:0]` and samples at a safe edge while accounting for at
most one in-flight read. This fixed the candidate-bound local failure; the full
local suite passes all 20 registered checks and 132 Python tests with one declared
Windows privilege skip.

| Current evidence | Result | Limit |
| --- | --- | --- |
| Candidate manifest `.mister/evidence/candidates/fpga-candidate-20260908-40-integrated-tb.json` | Candidate `56860713d38990ae28f1846e5f22850ed68b9ee228f6178c11e53fcb0f2d8a9b`; source `13b93de9eb32d9fc72701886c164853622bc744c18cddec1b660f127ffc70c7d`; manifest SHA `41bd0513171bda2f72751eecc6f8a1573086efab05f789ae24838f3990bce900` | Development-only; no promotion until physical gates pass. |
| Package/preflight | Package40 verifies; target preflight `.mister/evidence/receipts/20260908T-candidate40-preflight.json` SHA `db016d77aaf5c97f5d3f2703314019d9952cb65554c9fe91220064f4a34315a3` passes on `\\192.168.0.69\sdcard\_CodexDiabloCandidate40` | Does not prove activation or user workflows. |
| Candidate-bound local suite | `.mister/evidence/receipts/20260907T220754Z-d52bc971-6283-4dce-b2c5-67f13d4828f8.json` SHA `c879632aee708ee0d6c831459cb296918aabf0c9eeca1a80fc6908644e4f30df` passes all 20 registered checks; the full Python suite is 132 tests / one skip | Host and QEMU replay remain software/emulation evidence. |
| Target launcher smoke | Clean five-second candidate40 smoke returned launcher `status=pass`, `exit_code=0`, exact candidate/source IDs and exact requested RBF process | The longer attempt was blocked by a concurrent NFS_SE installation/rollback process and is not physical acceptance. |
| Target PCM observation | The blocked attempt observed local queue 8,700 then 6,329, underrun 6,777 then 13,502, four dropped callback chunks and a later reset/change of target state | C15 requires a quiescent board, 30-minute Diablo/Hellfire traces, physical stereo inspection and zero steady underrun/resync/drop deltas. |

The blocked board receipt is
`.mister/evidence/receipts/20260908T-physical-launch-candidate40-attempt.json`
(SHA `9ce81ad97fddeaf01ce178d3453d1096a7c5e623dfde04318508869195f8bdae`). It is
retained as a first-class blocker, not counted as a pass. Before another board
run, acquire an exclusive maintenance window, confirm no other MiSTer/NFS
installer process, seed the menu RBF, verify the exact requested RBF and boot ID,
then run candidate41 with the licensed data root. A clean board run must capture
video identity, stereo audio, controls, campaign/save behavior, performance and
safe teardown in one candidate-bound receipt.

## Candidate41 superseding doc-sync checkpoint — 8 September 2026

Candidate41 historically superseded candidate40 as a documentation checkpoint; it is not current after C34/P01-P06 source commits.
identity after the qualification README was synchronized with the integrated DDR
harness fix. The source change is documentation-only; the ARM executable and FPGA
RBF remain byte-identical to candidate40. The candidate manifest is
`.mister/evidence/candidates/fpga-candidate-20260908-41-doc-sync.json` (candidate `a5f2b83c0191d56e44a7b1babd5988e3fc0530a9f973f6e6bb739b13479ab989`, source `7901cdc0d54c3d8d3a527a85445c78d4d1ad5330e1b223f426a3ed15dc914d0d`, manifest SHA
`c87c3b7dc214f23c4dc299c9010cbf2e8e031c2962a1a05604d59fa7452b0579`). The 190-file package is `.work/package-board-candidate-41` (package manifest
SHA `3c2b274f139b8b50a4a7107b395c1685f321985c9daacd8ddfb4290556d711c9`) and is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate41`; target preflight passes
with receipt `.mister/evidence/receipts/20260908T-candidate41-preflight.json` (SHA `d917dafcefb058d51f4de183543ca6e36d7cbc3c98645eb5a5b15e835befcacf`). Candidate-bound local
verification passes all 20 registered checks in `.mister/evidence/receipts/20260907T221825Z-1b8d996d-61dc-41d2-b5bd-e72fc2e178a4.json` (SHA
`e28aaedf6096ed519ecf792a8736284cb3b288300a73f9bd3c669b95e5eec74e`), while the full Python suite remains 132 tests with one declared
Windows privilege skip.

Candidate41's clean normal-session board run completed with launcher pass, exact RBF
process matching, FPGA operating state and controlled exit. Its observer remained
black/stale, startup PCM underruns were 6,732, and no steady underrun/resync/drop
delta was observed after the startup sample; receipt
`.mister/evidence/receipts/20260908T-physical-launch-candidate41-normal60.json`
(SHA `3a1f7e97d3be5429000b27e9d3c1319dd42cf1291f02cba52e505651b5f845fb`) records
the result as blocked. Candidate40's ownership-contended attempt remains a separate
historical blocker at `.mister/evidence/receipts/20260908T-physical-launch-candidate40-attempt.json`
(SHA `9ce81ad97fddeaf01ce178d3453d1096a7c5e623dfde04318508869195f8bdae`). Acquire
an exclusive, quiescent board window before repeating candidate41. Then
capture exact RBF/boot/FPGA identity, HDMI/analog video, stereo audio with zero
steady underrun/resync/drop deltas, physical controls, Diablo/Hellfire campaign
and save workflows, performance, and clean install/update/rollback. Do not promote
or call the core complete until those candidate-bound receipts and the C01–C34/R01–R13
matrix all pass.

A separate candidate41 Diablo timedemo attempt was blocked because a concurrent
MAME core owned MiSTer while the launcher waited for exact candidate-RBF admission;
it was aborted without accepting timedemo evidence. The diagnostic receipt is
`.mister/evidence/receipts/20260908T-physical-timedemo-candidate41-blocked.json`
(SHA `028404ad383e53cfc8ff545f0ca5682afc11046d4799fba67debabae40731758`). The
next target window must exclude all MiSTer, MAME and installer processes, not only
the NFS updater.

## Candidate42 source-policy checkpoint — 8 September 2026

The source-policy pass added an explicit `diablo_video_source_policy` RTL module,
its Verilog regression, an exact HDMI/direct-RGB/analog-scandoubler mode matrix,
and a deterministic progressive scandoubler disposition. The provisional source
manifest `.mister/evidence/candidates/fpga-candidate-20260908-42-video-policy.json`
has candidate `de8698de6291397fdd019bbd63ea5929151966b07fffebefc63cef1079b9e959`,
source `178e240bb3801db824cdeaaf18208884d59ea981c65f369c27128fd771763e29`,
and manifest SHA `fec717647f63c873317168d96b2d9aef71e588ef9ee2ff44c133f285cb0ffeae`.
It is retained as a source-policy development record only: the RTL and
`files.qip` changed, so the unchanged candidate38 FPGA RBF cannot be promoted
under this source identity. Candidate-bound local verification passed all
registered checks in `.mister/evidence/receipts/20260907T230230Z-0afb5fdf-2d2f-474a-91d0-f685b14c45bb.json`,
but its old artifact set is intentionally not a release candidate.

Candidate43 supersedes the provisional source-policy checkpoint. Its immutable
manifest is `.mister/evidence/candidates/fpga-candidate-20260908-43-video-policy.json`
(candidate `82ebd70596f62e5c3e60c00d6609a728359da1186b8ad140c1cd2e90ef6f534f`,
source `10486a2923b134085cbdb7d71e65b419545a4bce979e2fd5d6e9f73907a9c87f`,
manifest SHA `680c79298f3db7747e40dc20087861c193416aa6a0590e1820e561a17fcc2ddd`).
The direct Quartus build/compression/timing receipt is
`.mister/evidence/fpga-build-candidate43.json` (SHA
`f825d7ab8eaaccfd2f03699bb775c329b759d1bee5eebba648354334317fe2e2`) with all
four setup corners passing. Candidate-bound local, ARM/QEMU, Diablo/Hellfire
scene-oracle, package and read-only target-preflight evidence all pass; the
package is `.work/package-board-candidate-43` and is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate43`.

This closes the source-policy implementation and clean-build portion of C13/R10,
but does not close physical output qualification. C13/R10 remain open until the
three exact mode rows have connector-specific gameplay captures and sync/geometry
evidence. C31 remains open against matrix digest
`09bb6127f33e110b5a676358d892fe588f216d41027726948dac749311dccbe7` until those
rows and final approval are recorded. The target is currently owned by an
external MAME core, so no candidate43 RBF activation was attempted.

## Historical Candidate49 release-lifecycle checkpoint — 8 September 2026

Candidate49 carries the final local release-tooling changes after the candidate43
video-policy build: package documents now state the user-data and update contract,
`deploy_package.py` installs verified packages into candidate-named immutable
release directories and atomically switches a small activation record, and
`deployment_lifecycle.py` exercises clean install, interrupted update, successful
update, rollback, save preservation, manifest verification and staging cleanup.
`board_runner.py` now has a shell-free CLI that publishes a no-replace
candidate-bound board result; its required physical observations still prevent a
synthetic board pass.

Candidate49's package has 192 files/184 assets and passes local package verify and
read-only target preflight. The lifecycle receipt is deliberately scoped to a
mounted/local transaction fixture and does not claim menu activation or physical
qualification. The target remains owned by an external MAME core, so the next
action is still a quiescent maintenance window followed by exact RBF/boot
admission and the three output-mode captures, audio, controls, campaign/save,
performance and clean-target workflows. Candidate49 is not an accepted release.

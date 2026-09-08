# Plan to complete and close every September 7 audit item

## EXECUTION STATE

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
| MCP23009 500 kHz setting violates Fast-mode low time | Keep the 375 kHz correction; finish actual-source ACK/timing regression with installed native WSL Verilator 5.050. Prove 375 kHz passes and 400/500 kHz fail the low-time requirement. Resolve fixture startup/stimulus without changing production behavior for the test. |
| Clean HEAD omits required video-policy file registration | Preserve and commit the existing `files.qip` entry with the reviewed source-stabilization packet. Do not revert a registration required by the instantiated module. |
| Replacement FPGA and candidate do not yet exist | Pass the pre-build gate below, then compile once and bind the exact artifact. The successful `.work/c25-fpga-final` snapshot is pre-IO-fix evidence only. |
| Final clean-checkout qualification | Use the existing verification/materialization workflow on the accepted commit; run affected checks and required integrated qualification once. Do not design another qualification framework. |
| Remaining external timing contracts | Use known device limits plus actual board/configuration evidence. IO-board/revision, USER_IO use, RC/skew and relevant receiver settings remain inputs to acceptance. Do not invent delays or start speculative RTL work. |
| Candidate-bound physical acceptance | Obtain an available MiSTer window and physical display/audio observation or capture. Recheck boot/core identity once at admission; do not poll or interrupt a changing foreign workload. |

### Firm Quartus pre-build gate

No additional Quartus run until: (1) all currently known FPGA-affecting defect decisions are resolved; (2) focused regressions pass using production RTL; (3) independent review accepts the final diff; (4) the exact source/file-list packet is committed; and (5) snapshot dependencies match that commit. Record those five checks in the existing work receipt, without creating a new gate framework. Then run one fresh compile/compress/full timing flow for that input identity. Do not launch an overlapping build while a known source decision can invalidate it.

Rebuild again only for an FPGA input change or an actual compile/timing failure requiring a fix. Documentation, Git bookkeeping, test-only files and receipt updates do not justify another Quartus run. Reuse the clean ARM executable, assets and ABI artifacts when their complete dependency identities still match. Check hashes once at package binding; do not mint successive candidates for prose changes. Static timing acceptance and physical acceptance remain mandatory.

### Fastest route to working hardware

Finish the IO regression and source packet, qualify the clean checkout, build the affected FPGA once, and create one immutable **development** package with rollback. Use it first for supported launch, visible image, active stereo, controls/OSD focus, and save/relaunch. Fix observed failures before long endurance/campaign/performance runs. When the smoke test passes, collect the remaining required output modes, stereo endurance, campaigns, multiplayer, reset/core switch, latency and installation/update/rollback matrix in one coordinated session on that candidate where dependencies permit. A development candidate may collect missing evidence; it is never labeled an accepted release prematurely.

### Execution rules that reduce time and tokens

- Keep one implementation owner for the active defect. Give a second worker only a concrete independent review or a necessary task that advances the critical path; idle slots are acceptable. Stop speculative preparation, repeated historical audits, cosmetic refactors and unrelated warning cleanup.
- Use the known native WSL Verilator 5.050 route (`/home/meath/.local/bin/verilator`, resolved installation under `/home/meath/.cache/veriemu-next/src/verilator-5.050`), native compiler and established WSL path helpers. Persist the successful exact command in the existing runner/receipt once. Do not rediscover tools or fall back to known-incompatible Icarus/older Verilator for the aggregate RTL syntax.
- Report the first unexpected failure with exact command/result. After two failed recovery attempts, escalate once to Terra with files/logs rather than repeating the same loop. Recovery packets report after at most eight tool calls. Use structured arguments or script files rather than nested PowerShell/Bash quoting.
- Run a focused test before broad regression or synthesis. Repeat checks only for changed dependencies, actual failures or unresolved results. Batch routine documentation/link/hash checks at a source boundary; independently review critical code and acceptance changes, not every bookkeeping edit.
- Maintain this execution block plus compact receipt pointers. Keep raw logs and captures in files, retrieve only exact relevant evidence, and avoid repeated status narratives or large file reads. Preserve histories as histories; do not recatalog them unless reproducibility is actually blocked.
- When only external configuration/observation is missing, state the precise required input and keep that gate open. Do not spend further local tokens trying to manufacture physical evidence or weaken completion requirements.

Completion still requires every mandatory gate and candidate-bound evidence. This sequence reduces wasted work; it does not waive timing, physical, campaign, multiplayer, performance or installation acceptance.

## Current execution state — C34 requalification

There is no accepted release candidate. Candidate49 and its package are historical:
C34 source changes supersede their source qualification. Freeze the implementation,
rebuild affected artifacts and qualify a new immutable candidate before promotion.
Historical checkpoints below retain their original scope; this section governs
current work.

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

## Current execution entry point and mandatory audit amendments

**Refresh, 8 September 2026:** use the seven-batch
[root execution guide](../../CORE_COMPLETION_AUDIT.md) as the compact critical
path. This document remains the detailed C01–C34 closure authority. The
[current audit refresh](REFRESH_AUDIT.md) adds R01–R12 with exact evidence,
reproductions, fixes and acceptance requirements. These amendments override
older statements below that call candidate `a1fc74f…` current. Its recorded
artifacts still match, but nine source inputs have changed; candidate-bound
verification now rejects it. Earlier passes remain historical receipts.

| Amendment | Apply to | Mandatory closure addition |
| --- | --- | --- |
| R01 — stale candidate | C18/C25/C27/C29/C30 | Freeze sources, rebuild affected ARM/FPGA artifacts, create and verify a new immutable candidate, and qualify it. Do not relabel old binaries as a new-source build. |
| R02 — semantic closure admission | C18/C21/C25/C29/C31/C32 | Enforce evidence schemas, required test results/log integrity, valid non-null release candidate, coverage and numeric targets. Reject the synthetic failing-evidence reproduction. |
| R03 — source mutation during verification | C18/C27/C28/C29 | Run isolated snapshots; revalidate dependencies/artifacts before publishing. Preserve drift evidence and fail the mutation regression. |
| R04 — checkout-dependent runtime admission | C16/C18/C26/C32 | Add deployment-manifest validation independent of developer source/Git; clean runtime-only relocation must launch and mismatched files must fail. |
| R05 — missing board/menu adapter | C16/C17/C23/C24/C28/C29/C32 | Implement a concrete target profile and board runner; bind current boot, reserved memory, loaded artifacts, physical observations and safe cleanup. A configured `not_run` stub cannot close a board gate. |
| R06 — candidate identity parser could corrupt Git status | C18/C26/C28/C29 | `git_identity()` used `str.strip()`, which removed the leading porcelain status column on the first line. A source tree whose first changed path was worktree-only could therefore produce a manifest that immediately failed verification. Preserve only line endings, add a regression with a leading ` M .gitignore` record, regenerate the final candidate and rerun all bound receipts. |
| R07 — remote package metadata was not integrity-bound | C28/C29/C32 | `mister_preflight.py` previously trusted the remote `package-manifest.json` while checking only the four listed runtime files. Hash the metadata file before consuming its records, add tamper/missing regressions, and rerun the staged preflight. |
| R08 — clean-checkout fixtures depended on ignored build outputs | C26/C27/C28/C29 | A detached checkout failed 13 tests because `.work/build` and ignored `build_id.v` were assumed to exist. Make the affected tests bootstrap deterministic temporary fixtures and clean them up; retain a fresh-checkout receipt and keep clean Quartus/ARM rebuilds as separate open gates. |
| R09 — Quartus pre-flow mutated an immutable snapshot input | C18/C26/C27/C28/C29 | `sys/build_id.tcl` rewrites `build_id.v` during Quartus compile, so later timing/compression actions rejected the same snapshot. Preserve generated inputs around every native Quartus action, add a regression, and retain a clean compile/compress/timing receipt with all setup corners passing. |
| R10 — scandoubler vertical-sync timing is unqualified | C13/C25/C31 | The former `sys/scandoubler.v:20` TODO is now replaced by an explicit progressive 31 kHz disposition with VSync/VBlank sampled on the same input-hsync pipeline and deterministic colour mode. Candidate43 has fresh Quartus timing evidence, but no connector capture or sync/geometry observation exists yet. Keep C25/C31 open until each advertised row is physically observed on the same candidate. |
| R11 — ARM transport and reference build roles were conflated in scene qualification | C18/C19/C26/C28/C29 | The deployable `arm-transport.cmake` binary and the `arm-reference.cmake` scene binary are different roles. Running the clean transport binary with `DIABLO_NATIVE_SCENARIO` produced no captures because the reference-only scenario hooks are absent. Record role, recipe and binary hash in every scene receipt; use the reference artifact only for software equality and the transport artifact for ABI/board qualification. A role/hash mismatch must fail admission. |
| R12 — board-suite fallback text is stale and contradicts the configured adapter | C28/C29 | **Implemented.** The generic fallback now explains that --board-configuration is required and points to board_runner.py; test_verification.py covers it. Regenerate candidate-bound receipts. |
| R13 — package acceptance lacked an executable install/update transaction | C16/C18/C29/C32 | **Implemented locally.** `package_release.py` now emits NOTICE/SETUP documents; `deploy_package.py` performs verified staging and atomic activation; `deployment_lifecycle.py` records clean install, interrupted update, rollback and save-preservation evidence. Physical menu/target execution remains open. |

C01–C05/C08 already have implemented local fixes; preserve them and prove their
remaining integrated/target requirements rather than repeating the original audit.
C26's original untracked-file observation is historical; the intended source
overlay now runs from a detached checkout with no private data. Candidate43 is
the FPGA source-policy/build lineage remains historical, and candidate49 is a
historical release-tooling development checkpoint superseded by C34/P01-P06 source commits. Candidate49 has candidate-bound local and
ARM/QEMU receipts, both role-aware scene-oracle passes, package verification,
read-only target preflight and a passing local deployment lifecycle receipt.
Promotion is still deliberately withheld: source review/commit,
connector-specific video, active physical audio, controls,
campaign/save/multiplayer, performance, menu activation and clean-target
acceptance remain open. The scene receipts explicitly use the separately
identified ARM-reference role under R11. Evidence and remaining acceptance
requirements are in REFRESH_AUDIT.md.


For full completion, supplement town/scene benchmarks with campaign progression
coverage: early/mid/late game, bosses/endings, relevant class/skill/spell/UI,
cinematics and Hellfire-specific content. Cover all declared output modes,
controller-only workflows, multiplayer and clean-install/update/rollback checks.
Existing numeric targets remain mandatory. An approved exception must be stated
as reduced scope, never silently reported as absolute total completion.

The current implementation checkpoint is recorded below. The next work is the
remaining integrated transport gaps, a real target profile/configuration and
physical/campaign qualification. Read only the active detailed package and exact
evidence; keep large outputs in files and rerun checks by dependency invalidation.
Do not duplicate historical logs into this plan or state.

## Current implementation checkpoint

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

This section is the active work order after the candidate38 implementation pass.
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
or call the core complete until those candidate-bound receipts and the C01–C34/R01–R12
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

## How to execute and maintain this plan

Each C-item contains its dependencies, affected code, implementation procedure,
verification and closure evidence. Follow the stage overview first, then the
detailed work packages. Proposed scripts and interfaces are implementation
deliverables; a documented command is only executable when its prerequisites and
expected result are stated. Use the current execution block and machine state as the active checkpoint; treat Candidate49 and older candidate paragraphs as historical evidence.

### C01 — Fix changed-run rectangle coalescing

**Status: IMPLEMENTED — local renderer differential regression passes; C19/C28/C29 and target evidence remain open · P1 · closes F01.** Dependencies: none for the fix; C28/C29 for repeatable recorded regression. Code: `support/reference/mister_command_scene.hpp`, renderer tests; audit fixture `repro_changed_runs.cpp`.

**Implementation procedure**

1. Reproduce the source pixels `(10,0)=7` and `(20,1)=7` against a zero shadow and retain the incorrect rectangle output as the pre-fix result.
2. Make the previous-column map explicitly invalid before any row is processed. Prefer a generation value that cannot represent the previous row, or clear indices to a negative sentinel; avoid zero simultaneously meaning “unset” and “row zero.”
3. Before dereferencing a previous run, require a valid generation, `0 <= index < previous_count`, equal x, width and colour, and no earlier continuation. Keep the lookup tied to the previous row while populating the current row's mapping.
4. Preserve bounded storage and the current complete-copy fallback on capacity failure. Verify that partial command construction is never published after failure and End always has reserved capacity.
5. Add the regression to the maintained C++ renderer/scene test suite rather than relying solely on the report's standalone executable.

**Verification**: empty first row; changes only in row one; unrelated equal-colour runs; disappearance/reappearance of an x position; first/last columns; adjacent runs; all three target slots; non-default source pitch; record capacity/End boundary. Run at least 10,000 deterministic seeded sparse/dense cases, execute generated records against a copy of the shadow, and compare the entire target to the source whenever construction succeeds.

**Close only when** all cases agree byte-for-byte, failures take the safe full-copy path, and the rebuilt ARM candidate contains the fixed header. Retain failing/passing logs, seeds, input hashes and build ID; F01 stays open if only host code is fixed but an affected accepted ARM binary is still advertised as current.

### C02 — Make per-slot caches coherent across all writers

**Status: IMPLEMENTED — mixed direct-command/fallback cache regression passes; C07/C19 integration evidence remains open · P1 · closes F02.** Dependencies: C01 for scene integration; coordinate cache-reset semantics with C07. Code: `mister_transport.hpp`, `mister_transport_sdl.hpp` and adapter tests.

**Implementation procedure**

1. Inventory every writer of slot pixels and palettes: initial full copy, dirty copy, FPGA commands, recovery and diagnostic capture/probes. Define one authoritative content generation per slot and epoch.
2. Add a session API for external writes/invalidation. Before a command submission can modify a slot, invalidate the full-copy session's palette and dirty-pixel cache for that slot. Successful completion may install a new known shadow; failure must leave it invalid.
3. Consolidate the command and session shadow ownership if practical. If retaining separate caches, document the generation checks that prevent either cache being used after the other writer changes memory.
4. Invalidate on epoch change, aborted/unknown command completion and source reattachment. Do not invalidate just because a displayed frame is retired: ownership and content validity are different facts.
5. Keep command mode and dirty-copy mode composable; reject an unsupported combination explicitly until the implementation is correct.

**Verification**: promote `repro_palette_cache.cpp`; test A→B→A and A→B→B palettes, changes at unsampled pixels, alternating full/dirty/command paths for every slot, palette-only changes, timeout followed by fallback and reset while caches are valid. Compare actual slot memory, not the ARM shadow, after each successful completion.

**Close only when** the production adapter path passes those transitions with dirty-copy both enabled and disabled, no unnecessary stale-cache assumptions survive, and completed target-scene equality under C19 confirms mixed paths. Save mode/configuration, command outcomes and complete memory comparisons.

### C03 — Remove the two-vblank presentation ceiling

**Status: IMPLEMENTED — scanout simulation stages the next frame without a forced second vblank; C09/C21 target qualification remains open · P1 · closes F03.** Dependencies: coordinated design with C04/C05; C09 provides backpressure integration. Code: `rtl/diablo_framebuffer_scanout.sv`, scanout testbench.

**Implementation procedure**

1. Draw the current prepare/claim/palette/activate/retire state transitions and identify all operations unnecessarily gated by `vblank_rise`.
2. Split preparation from activation. Poll/claim a safe ready candidate and stage its palette while the current frame remains displayed. Keep one explicitly owned pending frame; never replace it without a defined release protocol.
3. At vblank, commit an already prepared frame and immediately allow preparation of the next one once required retirement writes are safe. Do not start an entire acquisition only after waiting for the next boundary.
4. Handle no-ready-frame, candidate-not-yet-prepared and DDR-stall cases by keeping the last complete frame. Expose separate counters for no producer frame, preparation overrun and missed activation.
5. Check the scaler's actual FB_BASE latch and FB_VBL relationship so a core-local state update corresponds to the intended displayed refresh.

**Verification**: replace manual two-pulse assumptions with a periodic boundary generator. Supply ready frames before deadlines, run at least 1,000 refreshes, and check activation IDs/base changes every refresh after warm-up. Repeat with bounded randomized DDR delays, different vblank phase and continuous audio/input traffic. Verify skipped frames only when a declared deadline is missed.

**Close only when** RTL has no built-in alternate-refresh limit and a rebuilt board candidate demonstrates expected activation cadence with real vblank. Keep separate ARM publish and FPGA display traces so a 60-call/s producer cannot disguise 30 displayed frames/s.

### C04 — Reclaim superseded frames without violating ownership

**Status: IMPLEMENTED — scanout simulation retires stale same-epoch READY slots; C06/C09/C23 target stress remains open · P1 · closes F04.** Dependencies: C03 interface; C06 command ownership. Code: scanout RTL, ABI generator/header, transport tests as needed.

**Implementation procedure**

1. Specify the presentation policy in the ABI document. Retain latest-ready selection for low latency only if explicit superseded retirement is implemented; otherwise implement FIFO and document its bounded queue delay.
2. Under latest-ready selection, identify old READY descriptors in the current epoch that can never be displayed after the chosen frame. Recheck generation/state at the protocol's safe point before retiring them.
3. Distinguish retirement reason: displayed completion versus superseded without display. Do not increment a display counter or claim a frame was seen for a skipped frame.
4. Ensure FREE is the final publication of retirement after all metadata needed by the next owner is complete. Preserve ARM-owned descriptor fields and byte enables.
5. Never retire current display, pending palette/frame, ARM-writing or outstanding-command slots. Handle epoch changes by the common quiescence protocol, not stale snapshot writes.

**Verification**: older slot 2/id 6 alongside active id 8; all slots ready out of order; producer faster than display; equal/stale IDs; wrap policy; reset during retirement; delayed retirement writes. Maintain a scoreboard accounting for every allocation, submission, display and superseded retirement over thousands of frames.

**Close only when** every submitted frame has a terminal ownership outcome, available capacity returns after producer stop, no prohibited slot is freed, and board stress no longer leaves old READY IDs stranded. Preserve the scoreboard and before/after slot-state dumps.

### C05 — Commit palettes and frame bases atomically

**Status: IMPLEMENTED — palette/base handoff is guarded by vblank plus a bounded blank fallback in scanout simulation; scaler and target atomicity evidence remains open · P1 · closes F05.** Dependencies: C03; inspect imported scaler before choosing an implementation. Code: scanout palette logic, `Diablo.sv`, relevant `sys` scaler interface if required.

**Implementation procedure**

1. Establish whether the scaler's core palette is live, banked or latched and when its framebuffer address is sampled. Record the exact imported source paths and timing relationship.
2. Keep next-frame palette data in private staging RAM. Do not upload it into a palette currently used by the old frame during active scanout.
3. Prefer a palette-bank select that changes with the frame base if the framework supports it. Otherwise implement an explicitly bounded blanking commit sequence whose completion precedes the scaler's first read of the new frame. Add bank support only with a documented wrapper change if blanking cannot guarantee atomicity.
4. Couple pending palette generation to pending frame ID/epoch. A late or incomplete palette keeps both old frame and old palette active.
5. Handle reset and palette-only animation without exposing partially uploaded entries or acknowledging the wrong generation.

**Verification**: use two index images and sharply different palettes such that every wrong pairing is observable. Decode output RGB in a scaler-level fixture, randomize palette DDR delay across vblank, and assert no active pixel combines generations. Include all 256 entries and repeated palette-only updates.

**Close only when** the old ordering reproduction is prevented, decoded integration output has zero mixed-generation pixels, and physical capture of alternating palettes/palette animation matches the intended sequence. A count of 256 palette writes is not sufficient evidence.

### C06 — Implement command timeout and fault completion lifecycle

**Status: IN PROGRESS — adapter keeps an asynchronous fence submission record, uses a monotonic deadline, and faults rather than recycles a late-writable slot; C07/C09 reset and target fault qualification remain open · P1 · closes F06.** Dependencies: C07 epoch protocol, C09 fault injection; coordinate C04. Code: SDL adapter command path, runtime, command consumer and shared ABI status.

**Recorded implementation (2026-09-07):** command submissions retain slot, epoch, fence, publication sequence and an absolute monotonic deadline; completion is reconciled on later presentation calls so the normal path does not block for the full recovery budget. A timeout marks the still-writable slot `FAULT`, invalidates its command shadow and raises the shared command-fence fault; a late fence is consumed only for that original submission and cannot publish or recycle the timed-out slot. Epoch mismatch now resets every adapter-side command shadow, next-slot cursor, fence seed and outstanding record together with `TransportSession::RebindEpoch`; the SDL fixture directly verifies that reset invariant. Candidate-bound local and ARM/QEMU receipts for the current development candidate pass these regressions. Completion-before/after-deadline, delayed DDR writes, repeated timeout recovery and board fault/relaunch evidence remain open.

**Implementation procedure**

1. Introduce an outstanding submission record containing slot, epoch, fence, publication sequence, deadline and state. After publishing commands, retain that record until completion or acknowledged cancellation.
2. Replace poll-count timing with an absolute monotonic deadline. Normal presentation must not block repeatedly for the full recovery budget; poll/reconcile outstanding work on subsequent service steps.
3. On timeout, stop new writes to the owned slot and preserve the last display. If the fence arrives late, either publish the completed frame if still useful or retire it safely; never leave the allocation forgotten.
4. Publish command consumer errors with code/detail/epoch and make the ARM supervisor observe them. Define behavior for bad records and ring cursor violations without waiting on an unwritten global fault field.
5. For unrecoverable work, quiesce producer and consumer, acknowledge the stopped epoch, then initialize a fresh one. Do not reset ring cursors or FREE slots while FPGA writes can still arrive.

**Verification**: completion just before/after timeout, timeout in each command phase, invalid opcode/layout, delayed writes, fence-number wrap, core reload and repeated timeouts exceeding slot count. Assert that each outstanding record reaches completion or an acknowledged abort and that no late write reaches a recycled slot.

**Close only when** usable service returns within the configured live-interface recovery budget, fatal interface loss is visible and safe, all slots remain accounted for, and board fault/relaunch tests match host/RTL results. Record faults as outcomes, not successful frames.

### C07 — Serialize reset recovery with audio and adapter state

**Status: IN PROGRESS — callback-held atomic runtime ownership, callback-owned resampler reset generations, and a generation-validated reader/transition gate now prevent live reset recovery from racing a callback entry. SDL device quiesce/prime and target interleaving evidence remain open · P1 · closes F07.** Dependencies: define the protocol jointly with C06; C17 ownership applies to process-level resets. Code: adapter, runtime and audio callback overlay.

**Recorded implementation (2026-09-07):** an audio callback first confirms an even transition generation, increments its reader count and confirms the same generation again before loading/using the runtime. Recovery atomically turns the generation odd and proceeds only if no confirmed reader remains; otherwise it restores the even generation and lets normal SDL pacing retry. This closes the previously unsafe check-then-recover interval without blocking the audio thread. The SDL input/transport test explicitly exercises callback-held recovery denial, transition-time callback denial and post-transition resumption. It passes when invoked with the recorded local SDL include/library configuration. Full lifecycle stress, a target audio-device pause/lock decision and board reset proof remain required.

**Implementation procedure**

1. Identify callback, presentation and lifecycle threads and list shared fields. Assign one owner to resampler phase/history and make session lifetime explicit.
2. Add lifecycle states such as RUNNING, QUIESCING, DETACHED and PRIMING. The control thread requests quiescence; the callback stops publishing and acknowledges it without allocating or performing an unbounded wait.
3. Use an appropriate SDL audio-device lock/pause or an explicit atomic handshake supported by the actual Aulib integration. Avoid a lock inversion where the control thread waits for a callback while holding a resource the callback needs.
4. Only after callback and FPGA access are quiesced may the control page/epoch be reinitialized. Reset resampler history, slot caches, pending fences and delivered-input state through their owners.
5. Wait for validated FPGA attachment, prime PCM, then resume normal publication. Normal shutdown follows the same lifetime guarantees before unmapping.

**Verification**: a host callback/lifecycle harness repeatedly interrupts publication at controlled points; use ThreadSanitizer on a supported native build for ordinary shared state and protocol assertions for MMIO. Run resets during resampling, command waits and full copies, plus shutdown while a callback is scheduled.

**Close only when** there is no unsynchronized mutable callback/session state, no callback access after unmap or during header reinitialization, and repeated on-board resets recover audio/video/input. Sanitizer unavailability must be recorded; alternate evidence must still test the interleavings explicitly.

### C08 — Make malformed rectangle handling safe and consistent

**Status: IMPLEMENTED — widened software/RTL clipping tests pass for extreme coordinates and checked pitch arithmetic rejects overflow; C19 oracle vectors and sanitizer evidence remain open · P2 · closes F17.** Dependencies: none; feeds C19's trustworthy oracle. Code: `mister_command_renderer.hpp`, `mister_transport.hpp`, command validation RTL/tests.

**Implementation procedure**

1. Specify accepted coordinate/dimension ranges and behavior for empty, negative, offscreen and malformed records. Separate valid clipped no-ops from invalid protocol records.
2. Perform additions, negations and extent calculations in a sufficiently wide signed type before clamping. Never negate INT_MIN or add extents in int32. Validate pitch/height multiplication against span size without overflow.
3. Convert back to narrow indices only after bounds establish representability. Review packed copy-source coordinates for deliberate int16 truncation versus validation.
4. Apply the same input semantics in FPGA decode; a software no-op must not become an FPGA write or vice versa.

**Verification**: INT_MIN/INT_MAX coordinates and extents, zero/negative dimensions, crossing each edge, huge pitch/span claims, copy overlap in both directions and malformed flags. Use sanitizer-supported host tests and seeded property tests against a simple widened oracle.

**Close only when** every case rejects or clips deterministically without undefined arithmetic/out-of-bounds access and software/RTL outcomes agree. Save boundary-case vectors so future optimization cannot weaken validation silently.

### C09 — Prove integrated DDR service bounds and recovery

**Status: IN PROGRESS · shared delayed-DDR regression instantiates every production client, fixes command starvation and now fails closed on missing DDR service; deadline calculations and target combined-load stress remain open · P2.** Dependencies: C03–C07 interfaces; final closure after their fixes. Code: `rtl/diablo_transport_ddram_arbiter.sv`, `support/tests/diablo_transport_integrated_tb.sv`, top-level transport harness, arbiter, consumer state machines and tests.

**Recorded implementation (2026-09-07):** `diablo_transport_integrated_tb` puts the real control reader, framebuffer scanout, PCM player, input capture and command consumer behind the real arbiter and one deterministic 1–4-cycle DDR responder. It validates live control attachment, input producer advancement, PCM acknowledgement, a vblank display-state transition, command fill/copy/end-fence completion and equal accepted-read/response counts under contention. The first run discovered that continuous PCM/input/frame traffic left the command client permanently unserviced. The arbiter now retains response and write-burst ownership but gives a pending command request one accepted transfer after at most seven higher-priority grants. It also has parameterized response and pre-acceptance-busy watchdogs: either timeout latches a fail-stop fault, blocks new requests, keeps all clients backpressured, and drains a late reply only to the recorded original owner. The top-level session, framebuffer enable, LED and board-visible preflight indicator observe that fault; reset is the explicit recovery boundary. Zero-valued response/busy watchdogs and zero-valued client poll/sample intervals are clamped to a one-cycle limit so parameterized stress builds cannot underflow into effectively disabled service. The arbiter fixture injects both a missing reply and permanently busy DDR and verifies that contract. Registered RTL receipt `20260907T034106Z-c24f58de-9074-4693-955d-e23b6827fcc1.json` passed all RTL fixtures including this integration case and fault injection for source snapshot `f661b7d60ef235767f2d1b6d4408f90de4999bb71477c4af8da37b297cd6da96`. These are local fail-stop and bounded-service checks only: the watchdog values are not yet derived from audio/display/input deadlines, and no target combined-load stress has been run.

**Implementation procedure**

1. Instantiate real control reader, scanout, PCM, input and command clients behind the actual arbiter, backed by a shared-memory scoreboard rather than independent ideal responders.
2. Model request acceptance, response delay and single/multiple outstanding behavior exactly as supported. Preserve read ownership until the final expected response; verify resets cannot assign stale responses to a new client.
3. Define a bounded-DDR service assumption for normal-operation tests. Calculate each client's deadline from queue depth, sample rate and display timing and reserve service accordingly. Add fairness/aging or credits only if strict priority cannot meet the measured bounds.
4. Separately inject missing responses and stuck busy. Design a visible fatal timeout/recovery path without fabricating a response or releasing memory that may still be written.
5. Exercise control rechecks and relaunch while command traffic is continuous, not only when the port is idle.

**Verification**: reproducible seeds and adversarial maximum allowed delays; PCM/input saturation; command fills/copies; palette upload at boundary; epoch change; late response after reset. Assert region bounds, owner routing, no client starvation under the bounded model and safe stop under unbounded failure.

**Close only when** the integrated scoreboard remains correct, measured service times meet configured budgets and target combined-load stress confirms no growing queues or unobserved faults. Unit fixtures remain useful but cannot replace this harness.

### C10 — Wire real OSD focus and release/reconcile held controls

**Status: IN PROGRESS — real `OSD_STATUS` capture and host focus/release reconciliation regressions pass; C07 lifecycle, overflow, engine and target workflows remain open · P1 · closes F08.** Dependencies: C12 delivered-state model; coordinate C07 lifecycle. Code: `Diablo.sv`, input capture RTL, input ABI/reducer and SDL adapter.

**Recorded implementation (2026-09-07):** `Diablo.sv` now connects the wrapper's `OSD_STATUS` signal to `diablo_input_capture`; the RTL publishes focus transitions separately from controller-button payload changes and the host adapter releases delivered keyboard/mouse state on focus loss, retains desired physical state, and requires a neutral/repress sequence after focus regain. The SDL regression covers unchanged button bits during OSD transitions, held-key release ordering, filtered key recovery and shared keyboard/controller ownership. Receipt `20260907T050305Z-ad75216e-54e9-4b22-975f-0e6903644782.json` passed the local foundation, host, SDL and RTL suites for source snapshot `01c2814daab244d9bbc85444b0638a27ddd49a3bfe8f793d87c78e215a80a249`. Overflow/reconnect behavior beyond the bounded host fixture, engine-level focus behavior and physical target workflows remain open.

**Implementation procedure**

1. Route `OSD_STATUS` to input capture and establish its polarity and clock-domain contract from the MiSTer wrapper. Synchronize it if required; do not infer focus from physical button bits.
2. Publish focus changes with epoch/generation and define ordering relative to queued input. On focus loss, suppress gameplay delivery and release every delivered held action, including keyboard and mouse/controller-derived keys.
3. Retain physical desired state separately while OSD owns input. On focus gain, apply the documented policy: require neutral/repress for actions that must not fire immediately, and resynchronize safe state.
4. Handle lost focus events through snapshots/generation changes so ring overflow cannot leave permanent focus disagreement.

**Verification**: OSD opened via menu/software with unchanged button bits; held attack/move/click on open; close while still held; rapid toggling; overflow; reset; device reconnect. Verify engine actions, not only focus-event logs.

**Close only when** normal OSD interaction never drives the game behind it or leaves controls stuck afterward, RTL event ordering is tested and physical keyboard/controller OSD workflows pass on the rebuilt candidate.

### C11 — Complete transported keyboard modifiers and text entry

**Status: IN PROGRESS — physical modifier tracking and text-active US-layout SDL regressions pass; engine naming/chat and target validation remain open · P1 · closes F09.** Dependencies: C10 focus semantics and C12 shared delivered state. Code: SDL adapter and pinned engine input integration overlays.

**Recorded implementation (2026-09-07):** `mister_transport_sdl.hpp` tracks left/right Shift/Ctrl/Alt and Caps Lock from physical keyboard state, emits per-event modifier masks, keeps controller modifiers out of typed text, and translates the documented US-layout printable subset to `SDL_TEXTINPUT`. A pending bit now bridges the two-event failure case: if SDL accepts a keydown but filters or rejects its text event, bounded reconciliation retries the text exactly once; key release, focus loss and discontinuity clear stale pending characters. `mister_transport_input_test.cpp` covers shifted text, filtered keydowns, filtered text recovery and release ordering. Receipt `20260907T050305Z-ad75216e-54e9-4b22-975f-0e6903644782.json` passed the local suites for source snapshot `01c2814daab244d9bbc85444b0638a27ddd49a3bfe8f793d87c78e215a80a249`. Engine naming/chat, composition/locale policy, repeat semantics and target validation remain open.

**Implementation procedure**

1. Inventory actual engine consumers of modifier state, keyboard-state polling and SDL text events. Define the supported keyboard layout/text encoding rather than guessing text from arbitrary scancodes.
2. Maintain physical key state and aggregate modifiers, including left/right Shift/Ctrl/Alt and lock-key behavior. Supply both per-event modifier fields and the state queried by engine consumers using a deliberate backend integration.
3. Implement text input only while text entry is active, with UTF-8-safe events, shifted characters, repeat/backspace and composition policy. Prevent duplicate text when another SDL input backend is active.
4. Preserve distinct keyboard and controller sources so synthetic controller modifiers do not accidentally alter typed text or cause premature key-up of a physically held key.
5. Reset delivered state on focus loss, disconnect and epoch transition using the common reconciliation path.

**Verification**: hero naming, save/name fields, chat, punctuation, Shift+letters, Ctrl+wheel, simultaneous left/right modifiers, lock states, held-repeat and text cancellation. Add engine-level assertions for modifier queries and text buffers rather than merely checking SDL event type.

**Close only when** keyboard-only naming/chat/gameplay combinations work on target and controller mappings do not corrupt them. Record layout limitations explicitly; an unsupported required naming/chat path remains open.

### C12 — Correct mouse masks and make queue recovery reliable

**Status: IN PROGRESS — translated motion masks, bounded failed-event reconciliation and shared-source releases pass in host regression; full queue/physical recovery remains open · P2 · closes F10.** Dependencies: none for mask fix; joint delivered-state interface with C10/C11. Code: SDL adapter event injection and input reducer tests.

**Recorded implementation (2026-09-07):** `mister_transport_sdl.hpp` maps PS/2 left/right/middle bits to the SDL left/right/middle masks for motion, advances delivered state only after `SDL_PushEvent` reports queued, and reconciles keyboard, mouse and controller state through a bounded 32-event budget. Mouse cursor deltas are widened to 64-bit before accumulation, so extreme signed packets clamp safely without signed-overflow UB. The host fixture covers right-button motion/edge ordering, extreme mouse deltas, OSD release/repress, filtered keyboard delivery, shared keyboard/controller holds, shifted text and a filtered text event that is recovered on the next pass. Receipt `20260907T050305Z-ad75216e-54e9-4b22-975f-0e6903644782.json` passed foundation, host, SDL and RTL checks for source snapshot `01c2814daab244d9bbc85444b0638a27ddd49a3bfe8f793d87c78e215a80a249`. Filled-queue saturation, ring overflow/reconnect and physical mixed-input workflows remain open.

**Implementation procedure**

1. Translate PS/2 left/right/middle bits to SDL button masks explicitly for motion, matching the existing button-edge translation.
2. Replace fire-and-forget event injection with a result that distinguishes queued, filtered and failed events. Inspect the actual SDL return contract before using it to advance state.
3. Maintain desired versus successfully delivered state. Do not advance delivered masks when an event is rejected; retry/reconcile using a bounded queue rather than accumulating an unbounded event backlog.
4. Aggregate keyboard and controller contributions to shared keys. Emit a key-up only when no active source still holds that key.
5. On overflow/disconnect/focus change, use a complete state reconciliation or explicit release sequence. Preserve motion/wheel ordering without replaying stale clicks.

**Verification**: right/middle drag with motion-state checks; filled SDL event queue during down/up; filtered events; ring overflow; held controller+keyboard same key; unplug and reconnect. Assert final engine state equals desired state after recovery and every release is eventually delivered.

**Close only when** all event masks agree, failures cannot strand controls and bounded recovery passes adapter tests plus physical mixed-input workflows.

### C13 — Deliver correct gameplay on every required output mode

**Status: IN PROGRESS — the top level now has an explicit gameplay/diagnostic source policy and forces the framework framebuffer/scaler when a valid indexed frame is committed; target mode, timing and physical gameplay evidence remain open · P1 · closes F11.** Dependencies: C03/C05 display protocol; C25 timing; C31 output matrix. Code: `Diablo.sv`, `rtl/native_test_pattern.sv`, `sys/emu_ports.vh`, `sys/sys_top.v`, framebuffer/scaler and native RGB routing.

**Recorded implementation (2026-09-07):** `Diablo.sv` still sets `FB_FORMAT=5'b00011`, `FB_WIDTH=640`, `FB_HEIGHT=480` and `FB_STRIDE=640`; `FB_EN` and `VGA_SCALER` now share `gameplay_video_valid`, so diagnostic/startup states cannot advertise stale indexed framebuffer metadata. It adds a `Video source` OSD option (Gameplay by default, Diagnostics explicit), drives the framework path only when a valid gameplay frame is available, and passes diagnostic/startup state into `native_test_pattern`. The native generator keeps its 640×480/60 Hz timing, emits the selected bars/pixels/ramps only in explicit Diagnostics mode, emits a dark-red startup/fault screen before a valid frame, and emits black on the direct RGB bus for normal gameplay while the framework scaler is selected. `support/NATIVE_VIDEO.md` records the actual `sys_top.v` mux (`cfg[12]`, `cfg[2]`, `direct_video`, `vgas_en`) and the absence of a core-side inverse direct-video override. The native RTL fixture passes the original timing/pattern checks plus source-guard checks. This proves source-selection intent and local timing only; framework mux behavior, indexed/palette consumption, target modes and physical gameplay output remain open. Preserve `.mister/evidence/native-hdmi-delay12-build.json` as historical timing evidence while keeping the output acceptance gate open.

**Recorded implementation (2026-09-08, candidate42 source-policy pass):** the
source decision is now factored into `rtl/diablo_video_source_policy.sv` and
wired from `Diablo.sv`. Its regression covers attach-without-frame,
frame-ready gameplay, explicit diagnostics, and return-to-gameplay; it asserts
that `FB_EN` and `VGA_SCALER` cannot advertise a partial/stale frame and that
the direct diagnostic generator is disabled during gameplay. The closure matrix
now enumerates separate HDMI framebuffer/scaler, direct RGB and
analog/scandoubler rows, and `support/NATIVE_VIDEO.md` records the connector,
geometry, source and MiSTer configuration contract for each. The imported
scandoubler's old vertical-sync TODO is replaced with a documented progressive
three-line VSync/VBlank pipeline disposition and a deterministic `.mono(1'b0)`
connection. Local policy, matrix and full-suite regressions pass. Candidate43
now binds a fresh direct Quartus compile, compressed/raw RBF and SOF; the
four-corner timing receipt has zero setup violations and 0.188 ns minimum
positive slack. This closes the source/build portion of the item while physical
connector qualification remains open.

**Implementation procedure**

1. Freeze the C31 output matrix before changing wiring. For each row, record connector, progressive/interlaced mode, active width/height, pixel clock or `CE_PIXEL` relationship, sync polarity, RGB depth/order, palette ownership, `FB_*` versus direct-`VGA_*` source, forced-scandoubler/scaler setting, and the required physical observation. Mark a row `supported`, `diagnostic-only`, `unsupported-by-scope-decision`, or `blocked-by-equipment`; do not let an unmarked row inherit the HDMI result.
2. Trace the framework end to end from `emu_ports.vh` through `sys_top.v` and the imported video modules. Draw the actual mux for direct RGB, framebuffer/scaler RGB, HDMI and analog outputs, including where `FB_EN`, `FB_FORCE_BLANK`, `VGA_SCALER`, `VGA_DISABLE`, `VIDEO_ARX/ARY` and `forced_scandoubler` take effect. Add a small source-of-truth comment or interface note beside the mux so a future diagnostic cannot silently become the release source.
3. Define one explicit top-level video-source state: `diagnostic_pattern`, `game_framebuffer`, `startup_error`, or `blank`. Select it from a documented OSD/debug option and transport/framebuffer validity. In normal launch, select `game_framebuffer` only after a complete frame and palette generation is committed; select `startup_error` or `blank` with a visible, deterministic indication on attach/fault. Never leave the diagnostic pattern as the implicit fallback for a requested gameplay mode.
4. For each scaler-supported row, route the committed indexed framebuffer and palette through the real `FB_*` interface, then prove the framework consumes those signals rather than the direct test-pattern bus. Check base/stride/width/height and palette-bank timing against C05; keep `FB_EN` low until the first valid atomic frame. Add RTL assertions that the selected source, sync, blanking and palette generation agree at every frame boundary.
5. If a required row bypasses the scaler, implement a separate native scanout only after a bandwidth calculation under C09. Use a bounded line buffer, indexed palette lookup, explicit DDR ownership and a timing generator with declared read-ahead margin. Prove that scanout never reads an active/pending slot being retired, and that a lost DDR response enters the C09 fail-stop state instead of emitting stale or mixed pixels.
6. Keep `native_test_pattern` as a diagnostic fixture with an explicit mode and test it independently. Add a mux-level simulation that runs pattern → gameplay → palette-only change → reset → transport fault; assert that gameplay pixels appear in every advertised gameplay row and that pattern colours cannot appear unless diagnostic mode is selected.
7. Update the mode guide and launcher defaults only after the mux test passes. State the exact MiSTer profile, connector, resolution, refresh, aspect/scandoubler setting and known limitations for each row. If a row is removed from scope, record the decision, rationale, user-visible consequence and required plan/status updates; do not close F11 by relabelling it.

**Verification**: first run the mode-matrix/mux RTL test with assertions for source selection, frame/palette generation, sync polarity, blanking and reset/fault behavior. Then run patterns followed by deterministic Diablo and Hellfire gameplay scenes, palette animation, aspect changes, core switching and relaunch on each supported row. Capture output timing and RGB/palette transitions at the physical connector; verify sync lock, all four borders, geometry, RGB order and 8-bit ramp precision. Correlate each capture with the exact C18 ARM/RBF/ABI IDs and C25 timing report. A recognizable pattern or a framebuffer register dump alone is insufficient.

**Close only when** every required/advertised row has a passing mux/RTL result, complete indexed/palette equality for its gameplay source, matching timing evidence and a physical observation on the same immutable candidate. The closure record must link the final mode matrix, mux test receipt, C19 scene-equality receipts, C25 timing/endpoint review and per-connector captures. If equipment for a required row is unavailable, mark that row `BLOCKED`, name the missing adapter/display/measurement and the exact next observation; the parent item remains open.

### C14 — Make configuration and startup failure deterministic

**Status: IN PROGRESS — strict parser, entry-path host tests and terminal SDL-backend failure handling pass; ARM mapping, launcher and admission coverage remains open · P1 · closes F18.** Dependencies: launcher reporting under C16; runtime source checks under C17. Code: `mister_main.cpp`, SDL adapter initialization and CMake entry overlays.

**Recorded implementation (2026-09-07):** `mister_main.cpp` continues to use the shared strict `DIABLO_MISTER_TRANSPORT` parser and now treats failure to set the required dummy SDL backend as a terminal startup error instead of logging and entering transport with an unknown video backend. The foundation receipt `20260907T042145Z-f9d97680-9394-49c0-81ec-20af9e1fa566.json` covers the entry/lifecycle regression suite for source snapshot `fa6681649351b8187470f9ed7aad730d98f4251bb4fbd578283494c7a07df50f`; direct ARM mapping, ABI-ready and target launcher failure propagation remain open.

**Implementation procedure**

1. Introduce one configuration parser for transport enablement and related environment options. Define absent, `0`/`false`, `1`/`true` and malformed values consistently; reject ambiguous values with a clear diagnostic.
2. Select dummy SDL video only when transport is positively enabled and its startup policy requires it. Disabled mode retains normal SDL behavior.
3. Propagate mapping/ABI/epoch/FPGA-ready failures from initialization to the entry point or engine startup result. Explicitly requested transport must not continue invisibly with dummy video after failure.
4. Preserve useful error causes and exit statuses for the launcher: missing source, conflicting source, invalid address, map failure, mismatched ABI and attachment timeout.
5. Bound startup waiting with a monotonic deadline and clean up mappings/locks on every failure path.

**Verification**: table-driven parser tests; transport absent/disabled/enabled/malformed; both mapping sources present; nonexistent/short backing file; invalid epoch; FPGA never ready; normal non-transport launch. Assert exit status, cleanup and whether a visible backend or transport was selected.

**Close only when** all startup states have documented outcomes, no silent dummy-only failure remains and the menu launcher presents a useful failure on target without leaving a process/lock behind.

### C15 — Eliminate active-playback PCM starvation

**Status: IN PROGRESS · the ABI now exposes atomic PCM queue/cursor and underrun/resync snapshots, while the adapter records callback/frame publication and drop totals and reports counter deltas. Active-load measurement, priming/watermark tuning and physical audio remain open · P1.** Dependencies: C07 lifecycle, C09 service guarantees, C20/C21 measurement; physical routing from C25. Code: PCM RTL, audio resampler/publisher and Aulib overlay.

**Recorded implementation (2026-09-07):** the ARM can read a coherent PCM health snapshot containing producer, consumer, queued frames, FPGA underruns and resyncs. The SDL adapter samples it on a bounded presentation cadence and logs any diagnostic delta with local successful/dropped callback and frame totals. The ABI regression sets packed FPGA diagnostics and verifies the decoded values. This makes future active-playback traces able to distinguish ring priming from starvation; it does not turn historical or idle counters into a zero-underrun claim.

**Candidate38 continuation (2026-09-08):** the FPGA now publishes local FIFO occupancy through the ABI flags word. The target callback uses 1024 frames and candidate38 instantiates an 8,192-sample prime / 16,384-sample local FIFO. The physical normal60 trace records `local_queue=7257`, startup `underrun=6766`, `resync=0`, `drops=0` and no further underrun/resync delta during the observed steady interval. This is a promising priming result, not closure: C15 still requires 30-minute active Diablo and Hellfire traces, physical stereo inspection and zero steady deltas.

**Candidate41 physical update (2026-09-08):** the quiescent candidate41 Diablo
normal-session receipt records `local_queue=8033`, startup `underrun=6732`,
`resync=0`, `drops=0` and no observed steady underrun/resync/drop delta after the
startup sample. It remains blocked because the observer was black/stale and no
speaker output was physically inspected. The required 30-minute Diablo/Hellfire
traces, physical stereo inspection and zero steady deltas remain open. The
separate candidate41 timedemo attempt was blocked by a concurrent MAME core and
was aborted without timedemo evidence.

**Candidate43 continuation (2026-09-08):** the ARM transport binary is unchanged
and candidate-bound local/ARM/QEMU checks pass, but no candidate43 board run was
started because the target remains owned by an external MAME core. C15 therefore
still requires an exclusive target window, 30-minute active Diablo and Hellfire
traces, physical stereo inspection, and zero steady underrun/resync/drop deltas.

**Implementation procedure**

1. Establish counter meaning and sample units. Add or expose queue occupancy, high/low watermarks, source callbacks, published/dropped frames, consumed frames, underruns and resyncs with epoch and lifecycle phase.
2. Define STARTING/PRIMING/PLAYING/DRAINING/STOPPED intervals. Start acceptance counters only after sufficient priming; distinguish legitimate stopped-producer silence from active starvation without hiding active failures.
3. Capture callback interval distribution and DDR service delay on the candidate. Calculate buffer coverage from 48 kHz consumption and measured worst-case refill time; identify whether starvation originates in scheduling, resampling, ring publication or FPGA arbitration.
4. Fix the measured cause: bounded callback work, correct resample frame accounting, suitable priming/watermarks and scheduled DDR fetches. Increase buffering only with measured latency cost; do not drop chunks or repeat stale audio to make counters look clean.
5. Verify source format/channel/rate assumptions against actual obtained SDL audio format and handle mismatch explicitly. Preserve sample continuity through callback boundaries.

**Verification**: ramps/sine/left-right markers, callback-size variation, rate continuity, ring wrap, under/overflow injection, reset and silence. Run 30 minutes active combined load per campaign, sampling counter deltas while the producer is alive; listen/capture physical channels and inspect discontinuities.

**Close only when** active intervals have zero underrun/resync delta, no unreported drops, correct sample/channel behavior and physical sound. Retain traces explaining historical underruns and how the new candidate addresses their cause.

### C16 — Implement the real MiSTer launcher lifecycle

**Status: IN PROGRESS · project-owned preflight and foreground supervision exist; target menu/profile binding, matching accepted artifacts and physical lifecycle qualification remain open · P1.** Dependencies: C14 startup contract, C17 admission, C18 artifact manifest; C10 focus. Code: `support/scripts/diablo_launch.py`, new project-owned launcher/install scripts, runtime entry point and packaging configuration.

**Recorded implementation (2026-09-07):** `diablo_launch.py` defines a shell-free loader contract rather than assuming an undocumented menu API. It accepts only hash-verified RBF and ARM engine artifacts from an immutable candidate manifest; validates Diablo/Hellfire archives without modifying them; creates campaign-specific writable saves; generates one no-replace current-boot admission record; and passes candidate, mapping and lock configuration to the runtime. A loader must exit successfully and write the selected candidate ID to a per-run ready file before the foreground engine is started. Loader, engine and optional menu-return commands have bounded timeouts, process-tree termination, capped logs and explicit cleanup of transient readiness/admission records. The launcher now acquires an OS advisory lease on the configured transport lock before creating the admission record and holds it through loader, runtime and optional unload; a second launch fails before starting either command, and a crashed process releases the lease through descriptor lifetime. The locked descriptor is handed into each child (`pass_fds`/Windows handle list), and the Linux runtime validates and adopts a duplicate of that exact file instead of reopening the held pathname, eliminating a parent/child lock race. Artifact preflight now rejects a symlink before resolving it, so a redirected RBF or engine cannot inherit a trusted target's hash. Unit fixtures prove matching-artifact preflight, symlink rejection, readiness sequencing, inherited-lock metadata, failed-loader non-start of the runtime, cleanup and exclusive-lease rejection; foundation receipt `20260907T042145Z-f9d97680-9394-49c0-81ec-20af9e1fa566.json` passed for source snapshot `fa6681649351b8187470f9ed7aad730d98f4251bb4fbd578283494c7a07df50f`. The development ARM/RBF candidate and host/RTL/ARM-QEMU evidence now exist in C18; C16 still needs a supported MiSTer menu/profile binding, current-boot loader readiness, data compatibility evidence and physical Diablo/Hellfire campaign/save/core-switch qualification before it can close.

**Deployment preflight update (2026-09-08):** `mister_preflight.py` performs a
read-only SMB/package hash check and target probe without loading an RBF or
claiming physical acceptance. Candidate33 matches the complete 190-file package,
including `package-manifest.json`, on
`\\192.168.0.69\sdcard\_CodexDiabloCandidate33`. It found `MiSTer`, `menu.rbf`,
root `MiSTer.ini` and `config/cores_recent.cfg`. Receipt
`20260908T-preflight-candidate33b.json` has SHA-256
`51723c30cba19d5a1098f89d7b9bebb8271d10b0dec661f5e1e5f2176d7d4152`.
Activation, current-boot admission, installed-engine execution, campaign/save
behavior and physical observer evidence remain required.
The reachable target's existing `Scripts/wifi.sh` and `Scripts/MiSTer_SAM_on.sh`
also document a local loader command of the form
`load_core /media/fat/<path>` written to `/dev/MiSTer_cmd`. The read-only
observation is recorded in
`.mister/evidence/receipts/20260908T-loader-interface-candidate27.json`
(SHA-256 `8a1ffe1a1b56e9f1da5e224c50d11afe8e0065bd9a40f3e37e044a522f94665a`).
This is a target interface to bind into the authorized board profile, not yet a
successful Diablo activation receipt.

**Current implementation addendum (2026-09-08):** support/scripts/mister_launcher.py
is the self-contained target entry point. It verifies deployment/package v2,
requires the complete asset tree, creates a current-boot admission, owns the
POSIX lease and passes the locked FD to the ARM child. Its loader gate requires
both FPGA operating state and an exact /proc MiSTer process carrying the requested
RBF path. Candidate31 normal target smoke passed those checks and published live
frames; the observation is limited because capture was black/unavailable, the
API/OSD reported AO486 and PCM underruns increased. Candidate32 added a paced
timedemo path; candidate38 carries the current source/package identity and the
large-FIFO/local-queue telemetry fix. Its physical normal60 pass proves admission
and frame publication, while video identity, active audio, controls, campaign/save
and second-launch behavior remain open.
**Candidate38 launcher receipt (2026-09-08):** the package38 preflight receipt `20260908T-candidate38-preflight.json` (SHA-256 `01fe2ca6d599c41bbed92b4974ced77c5dc696ee61855792a183e0cf1f7260a2`) and physical normal60 receipt `.mister/evidence/receipts/20260908T-physical-launch-candidate38-normal60.json` (SHA-256 `a1d73353347f08e70d92e64c8f2fc45c58d461437784c7e776e42e07646ba9bb`) now bind candidate38. The launcher pass proves admission, exact RBF process, FPGA operating state, frame publication and controlled termination. Video identity, physical audio/control, campaign/save and second-launch behavior remain open.

**Candidate41 launcher update (2026-09-08):** package41 preflight and the
candidate-bound local suite pass. A quiescent 60-second Diablo normal-session
receipt proves exact RBF admission, FPGA `operating`, controlled exit and no
steady PCM drop/resync delta after startup, but records a black observer and
6,732 startup underruns. A separate Diablo timedemo attempt was blocked by a
concurrent MAME core and aborted without evidence. C16 therefore remains open
for menu/profile binding, physical video/audio/input, both campaigns, save/load,
core-switch/relaunch and clean lifecycle qualification.

**Implementation procedure**

1. Inspect the pinned MiSTer/menu and donor integration contracts read-only. Define a daemon-free entry path, expected filesystem layout, arguments/environment and how launch receives/selects the campaign.
2. Validate matching ARM/RBF/ABI manifests and required user-supplied campaign data before launch. Keep commercial data read-only; put logs/config/saves in explicit writable locations and avoid sharing test fixtures with real saves.
3. Acquire exclusive runtime ownership, validate current-boot memory admission, load the matching RBF and wait for readiness before starting normal transport writes.
4. Supervise the foreground process with bounded startup and shutdown. Handle normal quit, error exit, reset, menu return and core switch; stop callbacks/commands before releasing mappings or locks.
5. Preserve error output in a bounded log and return a menu-visible message. Handle spaces in paths, missing storage, read-only save paths and failed core loading without continuing in a half-started state.
6. Define stale-lock recovery based on actual ownership/liveness, not merely deleting an existing lock file.

**Verification**: host fake-board backend for launch/failure sequencing; target Diablo and Hellfire launch, save/load, quit, reset, switch away/back and second launch. Test killed process, missing MPQ, binary mismatch and storage removal/error in a controlled fixture.

**Close only when** both campaigns run through the intended menu entry without manual environment setup, lifecycle failures clean up safely and real saves survive the acceptance sequence. Keep final clean-install packaging verification under C32.

### C17 — Enforce current-boot reserved-memory admission and ownership

**Status: IN PROGRESS · strict physical-aperture parsing, current-boot/candidate admission matching and a kernel-released exclusive lease are implemented and host/ARM-QEMU file-backed runtime checks pass. Board reservation evidence and launcher ownership hand-off remain open · P1.** Dependencies: C18 compatibility manifest; C16 consumes this API. Code: mister_transport_admission.hpp, runtime mapping, DDR preflight/probes and launcher admission helper.

**Recorded implementation (2026-09-07):** production /dev/mem mapping now rejects signs, whitespace, trailing text, overflow and any aperture whose mapping offset/span cannot fit off_t; it requires a bounded no-symlink admission record containing the live Linux boot ID, exact base/bytes and `DIABLO_MISTER_CANDIDATE_ID`. The launcher acquires an OS advisory lock on that configured lease path before creating admission, passes the locked descriptor to child processes, and keeps it until teardown; the Linux runtime validates the inherited descriptor against the no-symlink pathname and adopts a duplicate. File-backed/QEMU mappings now acquire the same lease before opening the shared file, so standalone runtime probes cannot race a launched writer; the QEMU ABI probe supplies and exercises a dedicated lock path. A process crash releases the descriptor lock without treating pathname deletion as recovery. The standalone destructive probe performs the same admission and lease checks before mapping/writing. `mister_transport_admission_test.cpp`, `test_command_transport.py`, `test_diablo_launch.py`, and ARM/QEMU's file-backed `transport_runtime_probe` pass; `transport-abi-layout-test.json` (SHA-256 `5ad038eea5c9b0976aeb2a738f067ae614f72ca9d9a65f8afe2ade56fe79fcf6`) records the QEMU run, while foundation receipt `20260907T042145Z-f9d97680-9394-49c0-81ec-20af9e1fa566.json` remains the historical launcher receipt for its earlier source snapshot. The physical path is intentionally not claimed until C16 produces the admission record and C23 records a supported board boot.

**Implementation procedure**

1. Document why the aperture is reserved on supported MiSTer kernels and how the current boot exposes that fact. Validate the actual memory map/kernel/framework configuration; a successful mmap or old receipt is not proof of reservation.
2. Validate start/length/alignment and address representability before casting to `off_t`. Reject negative text, trailing junk, arithmetic overflow, out-of-range addresses and overlap with live framework buffers.
3. Define one ownership mechanism shared by launcher, runtime and every diagnostic writer. Acquire it before any challenge/header writes and hold it for the complete live session.
4. Keep read-only inspection separate from destructive probes. A DDR challenge writes the ABI header region and must refuse to run while an engine/other probe owns it.
5. Bind admission evidence to boot identity, kernel/framework identity, aperture and candidate. On boot/core-layout changes, revalidate instead of silently trusting a cached pass.

**Verification**: alternate/unsupported maps, second instance, concurrent probe, stale lock, unaligned and overflowing addresses, failed mmap and crash cleanup. Use file-backed or mocked fixtures for invalid-address cases; never test rejection by writing arbitrary physical memory.

**Close only when** incompatible layouts and conflicting writers fail before writes, the supported board boot has recorded reservation evidence and normal relaunch reacquires ownership safely.

### C18 — Establish immutable candidate and acceptance identities

**Status: IN PROGRESS · candidate manifests are content-addressed and immutable; source/artifact mutation and overwrite refusal are unit-tested. A current development ARM/RBF candidate now exists, while target admission, qualification and acceptance promotion remain open · P1 · closes F12.** Dependencies: C27 build inputs and C29 receipt schema developed together. Code: `support/scripts/candidate_manifest.py`, build helpers, state links.

**Recorded implementation (2026-09-07):** `candidate_manifest.py create` records every configured source input, relevant dirty source status, supplied tool identities and artifact hashes. Its source ID and candidate ID change when their respective inputs change; `verify` rejects mutation. Publication uses a unique temporary file plus a no-replace link, so an existing manifest cannot be overwritten. Source inputs, launcher artifact paths, manifest paths and all parent path components are now rejected before symlink resolution; malformed manifests fail as bounded verification errors; generated `__pycache__`/`.pyc` files are excluded from the canonical source set so test runs cannot mutate candidate identity; the candidate/launcher regressions pass. The earlier FPGA-only manifest `.mister/evidence/candidates/fpga-candidate-20260907-1.json` remains preserved as historical evidence (manifest SHA-256 `ac7298722bae3b26d43c022234d84fb54b6d04e25130b109b19b6ee76bbe60ee`, candidate ID `b9979b1ca4f2640aa10516b53a88959e84f7767588363340df7243f4c11b4110`); the first artifact-path symlink fix correctly invalidated it. The four-artifact candidates `.mister/evidence/candidates/fpga-candidate-20260907-2-arm.json` (manifest SHA-256 `c97cd7a8b30a409b4d69a540d2532ab520dabd494b7020822519bd0d1729303d`, source ID `fd1c317bdafcc9179107fe21ccaa13813a4f8a8ada68feafb741c09a226ec37a`, candidate ID `f3ca93d3816c12d8a3f8c724e924357cb1b034d300052a5378eb47b7c4b41901`) and `.mister/evidence/candidates/fpga-candidate-20260907-5-arm.json` (manifest SHA-256 `8d2b603ec3e91cb0240cdda00c37317d32366cc8d616a9890326eac55183a214`, source ID `dfe50a9cc7af178954cc819e4b93fdd21993148fe70ac9663858062e5a4a1a4e`, candidate ID `a1fc74fdbf27f9759691391fe576480b5f4e8d4548a287ed08f34ec272a7058c`) are preserved as historical development evidence and were superseded by subsequent source hardening. The historical development manifest `.mister/evidence/candidates/fpga-candidate-20260907-6-arm.json` verifies with four artifacts (manifest SHA-256 `8984b1c944641ba55ed7fe78ad7b6068004a7852b88e93b53f774bacdbcf6762`, source ID `48cbaf2d4ff36ac820e22ca0008b213d539629ef1880c40634ba203a0e8fa5e7`, candidate ID `08b43647e181c2c099ddc77049e44d7e40f3ab26fd94d07334bb9157d07284e4`). The bound ARM artifact is 8,518,704 bytes with SHA-256 `11ed2bf67edfc99b80ed6ff541cd991d20cd39cbd82f6b43c9b038dbb06f3ced`; the compressed and raw RBF both have SHA-256 `56da955190bd2f39b45b2fd137ee17bd771e06ebb77b6150e9a634f93b793f9c`, and the SOF has SHA-256 `d44b772d6e62bc29ac402c0e24b66ef0ff4b340a5a84792f09edf90b78ab6cb1`. The configured candidate-bound local and ARM/QEMU receipts pass, but this remains development-only: target loader admission, current-boot mapping proof, physical I/O, deterministic campaign equality, performance and acceptance promotion remain open.

**Historical candidate record (2026-09-08):** candidate25 `.mister/evidence/candidates/fpga-candidate-20260907-25-arm.json` has candidate ID `14eaf763fab2f4ced58d72dc095a03d65293f4609631a098a0f0eb5b5d162bdf`, manifest SHA-256 `27c4d2b04c0d00bab6aa3f3df04a33327f6107cc8b73dfd5baed37c631237416` and source ID `4ae4640bfc0888e7899eeac37e337f8a703e517ffff6a326b8e40a304c305797`. It binds the existing 8,518,704-byte ARM engine (`11ed2bf67edfc99b80ed6ff541cd991d20cd39cbd82f6b43c9b038dbb06f3ced`), raw/compressed RBF (`56da955190bd2f39b45b2fd137ee17bd771e06ebb77b6150e9a634f93b793f9c`) and SOF (`d44b772d6e62bc29ac402c0e24b66ef0ff4b340a5a84792f09edf90b78ab6cb1`) because only test-fixture/bootstrap source changed after the prior artifact build. Candidate-bound local, ARM/QEMU, Diablo/Hellfire scene-oracle, package and read-only target-preflight receipts all pass. This candidate remains development-only until clean native rebuild/timing, target activation, physical qualification and release lifecycle evidence are complete.
**Historical candidate record (2026-09-08, candidate27):** candidate27 `.mister/evidence/candidates/fpga-candidate-20260908-27-arm-clean.json` has candidate ID `95eaf3535aaf52d55b63f85b9bc566178c8e24b0d6f00d1e29d28a54021bcaf8`, manifest SHA-256 `e83b4d6a3142ab930419bf04caf9f273df4d628619010906e51e7f0fd16a0f13` and source ID `29e74b2685e333470ee383d40a977aa8b5a6da87a1a3d5106025890f1e9a42f4`. It binds the clean ARM transport engine (`6a623b7f4c94215f51ff7e6ebfcfd46c4d48072d434ba5ccb19bf0f70a30c4a3`), clean Quartus SOF (`53ccc445cec939d29128bae87272d7861b84a6403117e2757e9ad44ece4516f2`), raw/compressed RBF (`566f24bd1d667265648173b8d4fba255f7035718540d5ef6046bf6f572758d3f`) and ABI (`aefc42fc0a1969800ef9ed8cbddb5d76155b7433ecaa1b6dc1a04a507e1737cd`). Candidate-bound local/ARM/QEMU, Diablo/Hellfire scene-oracle, clean ARM/FPGA build, package and read-only target-preflight receipts all pass; the scene oracle records the separate ARM-reference role. Target activation, physical qualification, R10/R11/R12 closure and release lifecycle evidence remain open.

**Historical candidate record (2026-09-08, candidate43):** candidate43
`.mister/evidence/candidates/fpga-candidate-20260908-43-video-policy.json`
(candidate `82ebd70596f62e5c3e60c00d6609a728359da1186b8ad140c1cd2e90ef6f534f`,
manifest SHA-256 `680c79298f3db7747e40dc20087861c193416aa6a0590e1820e561a17fcc2ddd`,
source `10486a2923b134085cbdb7d71e65b419545a4bce979e2fd5d6e9f73907a9c87f`)
verifies with 190 artifact records. It binds the transport ARM ELF, fresh SOF,
raw/compressed RBF and ABI; the build receipt records four passing setup
corners. Candidate-bound local, ARM/QEMU, scene-oracle, package and target
preflight receipts pass. Physical activation and release acceptance remain open
because the target is currently owned by an external MAME core.

**Implementation procedure**

1. Inventory historical accepted ARM/RBF hashes and current local outputs without overwriting either. If a historical binary is unavailable locally, mark the reference unavailable; never relabel a new binary with the old acceptance.
2. Build a canonical manifest of project source, engine/donor/template identities, overlays, generated ABI, constraints/QSF, dependency lock, tool versions/options and source-tree cleanliness or dirty snapshot.
3. Derive an immutable build ID from canonical inputs and store artifacts under a build-specific directory. Capture full hashes/sizes and distinguish compressed RBF from other formats.
4. Maintain separate pointers for development candidate, tested candidate and board-accepted candidate. Promotion requires successful checks applicable to that exact input/artifact set.
5. Before loading/running on target, verify local and copied target hashes. Record the board boot/configuration and observation window in the resulting receipt.

**Verification**: changing one source/header/constraint invalidates the ID or acceptance; modified artifact fails verification; partial build cannot promote; two concurrent builds cannot overwrite one another; absent historical files are reported accurately.

**Close only when** current source and artifact identities are reconciled, manifests reconstruct every acceptance claim, and one complete fixed candidate has matching build/test/board receipts. Infrastructure implementation can finish early; final promotion occurs after relevant qualification gates.

### C19 — Prove complete accelerated scene equality

**Status: IN PROGRESS · the independent host-versus-ARM scene oracle now passes both maintained town scenarios for candidate27's separately identified ARM-reference role; FPGA readback, complete campaign coverage, role-aware evidence schema and physical displayed-frame agreement remain open · P1.** Dependencies: C01–C08, C18, C22; C23 covers physical workflow breadth. Code: scenario/capture runners, `support/scripts/scene_oracle.py`, independent renderer oracle and target readback tooling.

**Recorded implementation (2026-09-08, candidate27):** `scene_oracle.py`
validates both run envelopes, requires matching campaign/scenario/demo identity,
rejects missing or partial captures, compares every indexed pixel and all 256
RGB888 palette entries, and publishes a no-replace candidate-bound receipt.
Diablo and Hellfire `town-v1` each compare five native640 frames exactly between
the host reference and the separately identified ARM-reference build
(`20260908T-scene-oracle-diablo-candidate27.json`, SHA-256
`86af2b4e5d74bee51786d485a58c6b7350c17e46cb35a860107b0cfd49be3c30`;
`20260908T-scene-oracle-hellfire-candidate27.json`, SHA-256
`945c4b226a9cd62093fd2fc035a953d107309ff3f8cbc887602f3478e4a1b764`).
These receipts establish a reusable software oracle only; they do not claim
FPGA scanout, physical HDMI/audio/input, FPS or full-campaign acceptance.

**Candidate43 continuation (2026-09-08):** the same role-separated town oracle
was rebound to candidate43. Diablo and Hellfire each compare five indexed/palette
frames and pass in the candidate43 receipts recorded in the current checkpoint.
This refresh proves the new candidate identity is attached to the software
oracle; it does not replace the remaining dungeon/combat/campaign coverage or
physical displayed-frame and palette checks.

**Implementation procedure**

1. Define deterministic scenarios for both campaigns covering town, dungeon, combat, automap, UI/cursor restoration, palette fades/cycling, cinematics and loading boundaries. Record seed, replay/input stream, engine/data identities, config and expected capture checkpoints.
2. Use an independent software reference, avoiding shared changed-run logic as the oracle. Align comparisons by logical checkpoint/frame ID, not wall-clock filename alone.
3. Add a qualification-only capture protocol that pins a completed slot until index and palette readback finishes. Do not read a slot after FREE or while the FPGA is still executing commands.
4. Capture all pixels, palette and metadata; compare exact indices/palette, then decoded RGB where appropriate. Report first difference and total differences, preserving private frame artifacts outside distributable evidence.
5. Exercise software-only, command-only where feasible, and mixed fallback paths with dirty copy on/off. Include forced overflow and late completion so fallback correctness is tested under real adapter flow.

**Verification**: known corruption must fail the comparison; missing/extra capture checkpoints must fail; repeat reference captures first to establish determinism. Run maintained scene cases on actual ARM/FPGA after host/RTL tests pass.

**Close only when** every specified scene has complete equality on the matching candidate and physical displayed-frame/palette checks agree. Emulated ARM capture alone cannot close accelerated target equality.

### C20 — Measure every presentation outcome without bias

**Status: IN PROGRESS · every locally observable presentation return records an explicit outcome and an optional bounded mixed-outcome trace; target measurements and profiler-overhead qualification remain open · P2 · contributes to closing F15.** Dependencies: C06 outstanding-work model; feeds C21. Code: `support/reference/mister_transport_sdl.hpp`, adapter profiling, runtime/engine timing hooks.

**Recorded implementation (2026-09-07):** the adapter starts its profile interval before runtime lookup and accounts for runtime absence, recovery deferred/failed, invalid surface, command published/rejected, frame published, non-backpressure publish failure and exhausted backpressure separately. A failed full-frame publish flushes and records before returning, closing the prior unaccounted early-return path. Publish/flush/present clock arithmetic rejects unavailable or backwards monotonic samples rather than fabricating an unsigned duration; present outcomes are still counted, marked timing-invalid and excluded from duration averages. When `DIABLO_MISTER_PROFILE_TRACE` names a writable file, shutdown writes a versioned JSONL trace from a preallocated 4,096-record ring. Its header reports retained records, overwritten telemetry records and timing-invalid records; each retained record has sequence, timing-validity, publication/backpressure flags and outcome. Trace publication now uses exclusive create (`wbx`), rejects an existing path instead of overwriting prior evidence, removes a newly created partial file on write/close failure and exposes `profile_trace_write_failed` in the aggregate profile output. The SDL fixture verifies mixed outcomes, invalid timing retention, successful trace writing, overwrite refusal and ring overflow retaining the newest window while reporting two drops. The refreshed local receipt is recorded at the top of this plan; target traces and profiler-overhead measurements remain required for closure.

**Implementation procedure**

1. Define non-overlapping stage intervals and an end-to-end presentation interval. For asynchronous work, record timestamps separately rather than summing overlapping durations as if sequential.
2. Use scope guards or a single finalization path so success, overflow, publish failure, timeout, invalid surface and backpressure all produce records/counter updates.
3. Add reason codes and counts: no slot, record capacity, payload capacity, command error, late fence, full-copy fallback, skipped display and recovery. Preserve total attempted work including a failed build followed by copy.
4. Use monotonic clocks and bounded preallocated storage. Make logging asynchronous or sampled with a measured overhead mode; never print per pixel or allocate in the audio callback.
5. Report dropped telemetry records explicitly and make acceptance traces invalid if missing data could hide deadline misses.

**Verification**: inject each early return and assert event/counter totals; compare stage accounting with outer elapsed time within timer/measurement overhead; test counter wrap and shutdown flush; compare profiling enabled/disabled performance.

**Close only when** unsuccessful work is represented, aggregate counts reconcile to calls/submissions/completions and a saved mixed-outcome trace can be analyzed without excluding failures.

### C21 — Qualify tail latency, display cadence and acceleration benefit

**Status: IN PROGRESS · versioned presentation-trace analysis rejects incomplete telemetry and reports outcome/tail distributions; reproducible paired target benchmarks and physical latency runs remain open · P2 · completes F15 with C20.** Dependencies: C03, C15, C18–C20 and C31 acceptance config. Code: `support/scripts/analyze_presentation_trace.py`, benchmark runner/analyzer and end-to-end latency instrumentation.

**Recorded implementation (2026-09-07):** `analyze_presentation_trace.py` validates the C20 JSONL schema before calculating any metric. By default it rejects a trace with overwritten records, mismatched header counts, discontinuous sequences, malformed/invalid timing or non-monotonic timed starts; `--allow-dropped` is inspection-only and marks the result incomplete. It reports attempts, published and backpressure counts, outcome totals, timing-invalid records, present duration and presentation-start interval distributions using documented nearest-rank p50/p95/p99/p99.9/max values. Optional p99 gates fail explicitly when the needed sample class is absent or exceeds the supplied bound. Foundation tests cover mixed outcome reconciliation, the incomplete-trace rejection/inspection boundary and malformed timing/sequence rejection. Registered foundation receipt `20260907T035638Z-89124f61-3a40-432f-b478-866b630a6cbc.json` passed for source snapshot `d157cf8473fddb913c7d3b25bf2735631fe344a3d28ab4f3d4176be7de7115db`. This local analyzer does not yet supply campaign/scene definitions, target display identifiers, enough duration for target p99.9 confidence, paired software/accelerated artifacts or physical input-to-visible measurements.

**Implementation procedure**

1. Implement an executable benchmark matrix with exact scene, campaign, configuration, pacing authority, candidate IDs and warm-up/run durations. Produce paired software-only/accelerated binaries from the same base.
2. Collect frame intervals, prepared-frame deadlines, newly displayed IDs, queue age and per-stage outcomes. Separate simulation tick rate, render calls, publication and physical display rather than using one FPS number.
3. Analyze p50/p95/p99/p99.9 and max with a documented percentile method; include sample count, deadline misses and confidence/variation across at least three paired runs. Long enough runs are required for a meaningful p99.9; label insufficient samples rather than overstating precision.
4. Measure input-to-visible latency with a repeatable action and synchronized timestamps or physical trigger/capture. Calibrate clock domains; report transport-only figures separately when physical measurement is unavailable.
5. Identify the limiting stage, implement a bounded optimization, then repeat the same correctness and A/B matrix. Do not compare old dummy-SDL runs with different settings as paired evidence.

**Verification**: analyzer fixtures with known distributions/misses; missing trace rejection; paired order variation; loading stalls classified without dropping them from all reporting. Check the planned performance/input targets per scene, not only a pooled average.

**Close only when** reported distributions are trustworthy, required targets are met and acceleration improves the measured bottleneck without pixel, timing or service regression. If 60 FPS is not achieved, leave the performance gate open and retain the limiting-stage evidence and next implementation action.

### C22 — Separate diagnostic checksums from full correctness evidence

**Status: IN PROGRESS · ABI minor 1 now names absent, sampled CRC32 and full CRC32 checksum kinds, rejects undefined kinds and requires the publisher to declare the kind explicitly; full byte-equality qualification remains open · P2 · closes F16.** Dependencies: ABI compatibility/versioning in C18/C29; used by C19.

**Recorded implementation (2026-09-07):** `support/transport/transport_abi.json` advances the ABI minor from 0 to 1 because the meaning of the existing frame `flags`/`crc32` fields is now contractual. Generated C++ and SystemVerilog outputs define `FRAME_CHECKSUM_ABSENT`, `FRAME_CHECKSUM_SAMPLED_CRC32`, `FRAME_CHECKSUM_FULL_CRC32` and the kind mask. ABI validation rejects unknown flag bits, kinds above full CRC32 and nonzero CRC values marked absent. Both frame-publish APIs require an explicit kind; the indexed publisher selects sampled or full based on `DIABLO_MISTER_FULL_CRC`, while direct command frames declare absence. The host/RTL ABI fixture verifies generated-file freshness, sampled metadata, absent direct frames and rejection of kind 3. Receipt `.mister/evidence/transport-abi-layout-test.json` passed the host and RTL ABI checks. Full indexed-pixel/palette readback, CRC overhead comparison and final candidate compatibility evidence remain required for closure.

**Implementation procedure**

1. Define checksum kind explicitly: absent, sampled diagnostic or full indexed+palette checksum. Specify byte order, sampling pattern, polynomial/algorithm and included fields.
2. Update producer, generated ABI/docs and tools together. If adding a field or changing interpretation requires an ABI version/capability change, make mismatched peers fail clearly.
3. Keep normal command frames from appearing verified merely because their checksum is zero. Represent absence rather than interpreting zero as a valid comparison result.
4. Use completed-slot full readback and byte comparison for qualification; checksum may accelerate triage but must not replace the actual mismatch location/details.
5. Measure and label the overhead of full CRC/readback; keep diagnostic and performance configurations distinct.

**Verification**: modify a column skipped by the sampled CRC and ensure full qualification fails; change only palette; known checksum vectors; absent versus legitimate zero checksum; old/new ABI mismatch; command and full-copy frames.

**Close only when** no report can mistake sampled/absent metadata for full equality and target corruption in any pixel/palette byte is detected by the qualification pipeline.

### C23 — Complete physical gameplay, lifecycle and endurance qualification

**Status: OPEN · P1.** Dependencies: fixed candidate from C18/C19/C25, launcher C16, I/O C10–C15. This is an acceptance work package, not a substitute for fixing failed cases.

**Implementation procedure**

1. Build a campaign × output × input × workflow matrix with a separate result for every required combination. Include town/dungeon/combat, cinematics, menus, inventory/spells, save/load, quit, reset, switch away/back and relaunch.
2. Record board/kernel/framework, display/audio/peripheral configuration, artifact hashes, refresh/pacing mode, data identities and save fixture IDs before each run.
3. Use deterministic scripted actions where possible, plus documented physical observations for visual/audio/control claims. Capture meaningful checkpoints, counters and failures; lack of a crash is not proof that actions worked.
4. Execute at least 30 minutes combined gameplay per campaign, 2 hours idle with periodic input/audio/display checks and 100 safe lifecycle cycles. Exercise controlled storage failures using disposable test saves/storage fixtures, preserving real user saves.
5. For a failure, retain reproduction steps, checkpoint, logs and candidate ID, link it to its responsible C-item, implement the fix and rerun affected cases plus a representative full lifecycle. Do not restart the entire matrix unless changes invalidate it.

**Verification/closure**: every required cell passes on the same compatible candidate; no lost/corrupt saves, stuck controls, unexplained frame mismatch, unbounded queue or unrecovered fault. Physical display, speaker and peripheral observations must be explicit. Mark unavailable equipment/observation as BLOCKED, not skipped-success. Store the completed matrix and per-run receipts.

### C24 — Complete controller-only and multiplayer workflows

**Status: OPEN · P1.** Dependencies: C10–C12, C15/C16, compatible candidate C18; coordinate C23 fixtures.

**Implementation procedure**

1. Enumerate every required action and its controller binding: naming, menus, movement, attack, inventory, equipment, spells, automap, saving, pause and exit. Include text-entry or an explicit controller-accessible naming interface.
2. Test disconnect/reconnect, analog deadzones, simultaneous sources and focus changes. Fix unreachable actions in the mapping/UI integration rather than substituting a keyboard for a controller-only test.
3. Establish two compatible endpoints with exact engine/campaign/network settings and isolated saves. Test target as both host and joiner for Diablo and Hellfire where supported.
4. Run 30-minute sessions under normal rendering/audio/input load. Inject bounded delay/loss and disconnect/reconnect using controlled test infrastructure; cover failed join, host exit, wrong campaign/version and chat input.
5. Capture user-facing errors, connection recovery and transport/audio health. Ensure networking work cannot block the video/input service path indefinitely.

**Verification**: replay the complete action matrix with only the controller connected, then run both host/join directions and each campaign-compatible pairing. Confirm naming/chat, normal gameplay and graceful disconnect while audio/video/input service counters remain within their gates; compare saves before and after failure tests.

**Close only when** the action matrix is complete without hidden keyboard dependencies and both target host/join workflows pass with safe failure behavior. If a second endpoint or physical controller is missing, retain an exact blocked test list. Evidence includes endpoint versions, network settings, durations, action results and resulting save integrity.

### C25 — Close final-candidate timing, inference and endpoint coverage

**Current timing gap (8 September):** reviewed C34 evidence passes constrained
setup/hold/recovery/removal/minimum-pulse summaries at all four corners. C25
source review and validator acceptance are complete in commit `8e74223`: the
independent validator passes its 18 fixtures, correctly rejects the separate
infinity fixture, and real setup, hold, recovery, removal and minimum-pulse
results are positive at all four corners. A fresh current-SDC FPGA build is
underway. The reviewed unconstrained scope is narrowed from 4 input ports/22
output ports to 3 input ports/10 output ports. The pre-patch C34 scope receipt
`.mister/evidence/receipts/20260908T023811Z-c34-unconstrained-io-scope.json`
(SHA-256 `9d76b9cf1d1aa797bd081b9162f340c2a56d818393e20d7bb328606163a80219`)
records the original 4-input/22-output baseline and identifies residual
I2C/audio/multifunction interfaces and the unmatched
`LED_*` exception. Resolve each real launch/capture or asynchronous boundary;
use documented external requirements or narrow justified exceptions. Do not
invent delays or use blanket false paths. Terra corrected the initial SD interpretation: this core tristates SD SPI, and
these pins are analog-video/Z aliases. Narrow status/analog-alias exceptions are
authorized; residual I2C/audio contracts remain unresolved.
The residual external-contract review records missing board/software contracts
for HDMI_I2C_SCL/SDA, HDMI_TX_INT, HDMI_I2S/LRCLK/SCLK, IO_SCL/SDA and
USER_IO[2,4,5]. The repository has no board schematic, ADV7513/MCP23009
datasheets or measured RC/trace/cable budget; nominal device claims and fitted
diagnostics do not supply production timing constraints. The 3-input/10-output
residual set remains unresolved. Fully constrained acceptance stays open, and
no physical acceptance is inferred from this timing evidence.


**Status: OPEN · P2.** Dependencies: C13 supported modes, C18/C27 immutable builds; final check after RTL changes. Code: QSF/SDC, report contracts/parser, `support/EXTERNAL_INTERFACES.md` and relevant framework boundaries.

**Candidate43 build evidence (2026-09-08):** direct Quartus compile,
compression and timing ran from the immutable snapshot
`.work/build/fpga-candidate-20260908-43-video-policy/source`. The build receipt
`.mister/evidence/fpga-build-candidate43.json` records four setup corners, three
paths per corner, zero violations and 0.188 ns minimum positive slack. This
closes the reproducible native-build portion of the item; endpoint review,
connector-specific electrical behavior and physical mode evidence remain open.

**Implementation procedure**

1. Compile the complete snapshot with the configured Quartus and retain synthesis/fit/assembly/STA logs, resource reports and all operating corners under the candidate ID.
2. Inventory active clocks, generated clocks, input/output paths and unconstrained endpoints for every supported mode. Distinguish unused pins from asynchronous inputs and synchronous external interfaces.
3. Derive I2S/MCLK/I2C/storage/user-port constraints from actual waveform/clock relationships and receiver requirements. Review reset/mode transitions and CDC paths; do not apply broad false paths to silence warnings.
4. Reconcile the resource inventory with expected RAM shapes, entities, PLL/DSP use and register budgets. Review exact diagnostics with report hashes and rationale, separating errors from qualified exceptions.
5. Validate HDMI skew/delay assumptions and output-mode electrical/timing behavior on the board where required; retain the distinction between design budgets and measured quantities.

**Verification**: require all applicable timing checks/corners, zero unreviewed active endpoints, matching constraints/source IDs and no unsupported exception. Test parser failure on missing corners, stale review hashes and unexpected RAM shape.

**Close only when** final-candidate reports and endpoint reviews pass, physical assumptions have required evidence and no later RTL/constraint change has invalidated the verdict. A positive summary from another build cannot close this item.

### C26 — Make the complete implementation reproducible from version control

**Status: VERIFYING · P1 · closes F13.** Dependencies: initial inventory now; final verification uses C27–C29 and candidate source C18.


**Recorded implementation (2026-09-08):** the candidate source inventory now hashes the reviewed top-level, RTL, framework, overlay, test and support inputs while excluding generated interpreter/test caches such as `__pycache__`, `.pyc` and `.pyo`; a regression mutates a generated cache and proves the source ID remains unchanged. Candidate27 contains 194 source files, including the verification tests, `LICENSE.fpga`, `mister_preflight.py`, the scene oracle and its package-manifest regression, with no generated bytecode. This removes one machine-local reproducibility hazard, but a reviewed source inclusion, dependency acquisition and commit/package audit are still required before C26 can close.
**Recorded implementation (2026-09-08, R06/R07):** `candidate_manifest.py` now preserves the leading Git porcelain status column by trimming only CR/LF terminators. `mister_preflight.py` also rejects empty/dot/parent/absolute probe paths with bounded `ValueError` results instead of indexing an empty path tuple, and now hashes the remote `package-manifest.json` before consuming its file records. Candidate27 was regenerated after this metadata-integrity hardening; its local, ARM/QEMU, scene-oracle, package and target-preflight evidence is bound to the resulting IDs. The preflight probe uses the observed MiSTer layout with `MiSTer.ini` at the SD-card root rather than under `config/`; focused preflight coverage passes 4 tests plus the missing/tampered-manifest regression.
**Recorded implementation (2026-09-08, R08):** a detached worktree from committed `HEAD` with the intended source/support overlay now runs `python -m unittest discover -s support/tests -p test_*.py -q` without private data or pre-existing generated outputs. The run passed 129 tests with one declared Windows privilege skip and zero failures/errors. `test_compile_fpga_snapshot.py` creates and removes its temporary `.work/build`; `test_diablo_launch.py` creates and removes a deterministic temporary `build_id.v`, eliminating the ignored-build-output dependency that previously caused 13 clean-checkout failures. Receipt `.mister/evidence/receipts/20260908T-clean-checkout-candidate26.json` (SHA-256 `382496e1f7ac129b208bc8ae4926506c6d622c580093feaff11eb62925ae54b7`) remains valid for the unchanged Python/RTL source snapshot. This advances C26 to VERIFYING; source review/commit, dependency acquisition and package audit remain required for closure.
**Recorded implementation (2026-09-08, R11):** the clean deployable ARM transport build was reproduced from the pinned engine checkout with the portable ARM toolchain and `support/cmake/arm-transport.cmake`; receipt `.mister/evidence/receipts/20260908T-clean-arm-build-candidate27.json` (SHA-256 `2355fd68ed569464d7ee604ab0405ed83fda3f3638db09dec670414658fa644b`) binds the 8,518,704-byte ELF to candidate27. The separate `arm-reference.cmake` build remains the scene-oracle role. The clean source/build result advances reproducibility, but review/commit, dependency acquisition, role-aware scene evidence and package audit remain open.
**Recorded implementation (2026-09-08, committed source packets):** P01-P06 are committed through `a65a8ec0708fcbc0d4c3e390fc2c0056d935c437`. The durable packet records are [the source-packet classification](refresh-evidence/c26-source-packet-classification.json) (SHA-256 `ef21ea107eea6f3f3c6a381e6024e54ff97220c1bf35b2ad39f01b803c1242e2`) and [the commit ledger](refresh-evidence/c26-commit-ledger.json) (SHA-256 `07fb9d6de77f77281544e09bf7f846ab18738a2fb372875f6fc729053bd30e28`), copied byte-identically from the private work ledger. C26 remains VERIFYING until the current docs/evidence packet and clean-checkout qualification are accepted.

**Implementation procedure**

1. Inventory tracked, modified, deleted, untracked and ignored files with bounded output. Classify intended source, generated output, private assets, historical evidence and accidental files; preserve all existing user work.
2. Review intended RTL, `sys`, top-level project files, overlays, scripts, tests and documentation for completeness and provenance. Preserve the intentional deletion of the obsolete implementation plan.
3. Add only reviewed project files in coherent changes. Do not blindly stage all untracked content or include commercial MPQs, saves, screenshots/private captures or local toolchain binaries.
4. Preserve framework/import identities and required notices. Ensure any runtime-required generated file has a deterministic generation step rather than depending on an ignored local copy.
5. Reconstruct from a fresh isolated checkout without access to existing `.work`/build caches except explicitly pinned/downloaded dependencies. Use separate private fixture staging for data-dependent tests.

**Verification**: clean checkout can discover tools, generate ABI/build metadata, compile the intended host/RTL/ARM/FPGA paths and run applicable tests. Record which tests need private data/hardware, and verify those inputs are outside Git/package output.

**Close only when** committed source represents the complete candidate and the fresh-checkout result matches declared inputs/artifacts within documented reproducibility limits. Review/commit work is future implementation, not performed by this document edit.

### C27 — Replace hidden build dependencies with complete snapshots

**Status: VERIFYING · P2 · closes F14.** Dependencies: C18 manifest contract; C26 complete source. Code: `compile_fpga_snapshot.ps1`, build helpers/configuration.

**Recorded implementation (2026-09-07):** `support/scripts/compile_fpga_snapshot.ps1` now selects Quartus directly from `-QuartusRoot` or `DIABLO_QUARTUS_ROOT`, retaining `D:/Q17/quartus` only as this host's default; it no longer invokes the external `D:/vibes/fpga/bin/quartus-safe.ps1` wrapper. `-Action sync` requires an empty destination, copies the complete FPGA input set (top-level project/constraint files, `rtl`, `sys` and the timing Tcl script), and writes `.mister/fpga-source-snapshot.json` with per-file size/SHA-256 records. Compile, timing and compression validate that manifest before running the configured executable and write bounded per-action logs. `support/tests/test_compile_fpga_snapshot.py` passes clean-copy, path-with-spaces, non-empty-destination refusal, tamper detection and missing-Quartus-root cases. A fresh identified snapshot at `.work/build/fpga-candidate-20260907-2` then passed direct Quartus compile, STA and compression: 84 source inputs, snapshot manifest SHA-256 `9acb434d09aec3edbefaccf4a8d447c168ed28d945744146e8fe0dd1b258d8ec`, SOF SHA-256 `d44b772d6e62bc29ac402c0e24b66ef0ff4b340a5a84792f09edf90b78ab6cb1`, raw and compressed RBF SHA-256 `56da955190bd2f39b45b2fd137ee17bd771e06ebb77b6150e9a634f93b793f9c`, and timing report SHA-256 `23a552cd2a649d56bf838ca8d3572a427b8a817e23efba8008589753549da9df`; STA reported three setup groups with zero violations and a conservative 0.161 ns worst-case slack. The FPGA and rebuilt ARM artifacts were first bound to the historical C18 manifest `.mister/evidence/candidates/fpga-candidate-20260907-6-arm.json` (manifest SHA-256 `8984b1c944641ba55ed7fe78ad7b6068004a7852b88e93b53f774bacdbcf6762`, candidate ID `08b43647e181c2c099ddc77049e44d7e40f3ab26fd94d07334bb9157d07284e4`); final C27/C18 closure still requires reproduction from a clean checkout and current-boot target qualification. Candidate26 carries the clean Quartus artifacts and adds the generated-input restoration fix; its ARM bytes remain reused because the source delta does not change the ARM engine. This snapshot is complete for the allowlisted FPGA input set; it does not substitute for a clean-checkout native rebuild or target qualification.
**Recorded implementation (2026-09-08, R08):** clean-checkout foundation verification no longer depends on a stale ignored `.work/build` directory or a developer-generated `build_id.v`; the focused snapshot and launcher tests create deterministic temporary fixtures and remove them after use. The clean-checkout receipt under C26 proves the Python/launcher layer from the detached source overlay.
**Recorded implementation (2026-09-08, R09):** a clean direct Quartus compile reproduced a snapshot failure: `sys/build_id.tcl` rewrote `build_id.v` during the pre-flow hook, causing the following compression and timing actions to reject the snapshot. `compile_fpga_snapshot.ps1` now backs up and restores `build_id.v` around every native Quartus action. Candidate26's clean receipt `.mister/evidence/receipts/20260908T-clean-fpga-build-candidate26.json` (SHA-256 `a93a9c9573ef838ccd703a1fa54a56989b4ae72fdcdf26ad741a5ce709f00842`) proves direct compile, compression and timing all exit 0; the four reported setup corners have zero violations and minimum positive slack 0.014 ns. The helper regression is included in the candidate-bound 129-test foundation run. The generated date remains in the FPGA output, while the snapshot source bytes remain stable for subsequent actions.

**Recorded implementation (2026-09-08, candidate27):** candidate27 rebinds the clean ARM transport artifact to the clean FPGA/ABI artifacts. Candidate manifest `.mister/evidence/candidates/fpga-candidate-20260908-27-arm-clean.json` (SHA-256 `e83b4d6a3142ab930419bf04caf9f273df4d628619010906e51e7f0fd16a0f13`) verifies; the clean ARM receipt, candidate-bound local receipt `20260907T163914Z-2ac2bd6a-bae2-4739-938c-ed10ed28b557.json` (SHA-256 `2b6238cdc2037f136d09ef6480575c445d1219457ca34dec4be0deb0e368e0d4`) and ARM/QEMU receipt `20260907T163836Z-341002e5-50d2-4999-bae0-a83a5fe8351c.json` (SHA-256 `7733003b414f9530481a630c9587714bb7e8f250c26b69aef6da7e8e8d6cc0e8`) pass. The exact clean FPGA receipt remains the candidate26 clean snapshot receipt because the FPGA/ABI bytes are unchanged; package27 create/verify and read-only target preflight also pass. C27 is still VERIFYING until the candidate source is reviewed/committed and build dependencies are pinned/documented for another operator.


**Historical candidate-bound refresh (2026-09-08, candidate33):** manifest
`.mister/evidence/candidates/fpga-candidate-20260908-33-plan-refresh.json`
(SHA-256 `f0ab6bee4630014486c48c7f4b252dc40f118489af6d3337926b26f646cfd15c`)
verifies. The candidate33 local receipt
`20260907T183544Z-8711dc3b-a375-4873-b2eb-cd28bdbb0352.json` (SHA-256
`dfa73666ce5f221cf576461838ebd21dbe3d34109a76b959882c2162fd3c5100`) passes
all 20 registered checks; the ARM/QEMU ABI receipt
`20260907T184334Z-743163a2-7604-477a-aa22-97489698e87e.json` (SHA-256
`6152548dc0dbaac46cff5443f43e71c5fd236567c3dc83d62d98e7377d99c722`) passes;
and the role-aware Diablo/Hellfire scene-oracle receipts
`20260908T-scene-oracle-diablo-candidate33b.json` and
`20260908T-scene-oracle-hellfire-candidate33.json` pass. These receipts cover
software/reference equality and ABI only; they do not close target video,
audio, controls, gameplay, performance or release lifecycle.

**Implementation procedure**

1. Make Quartus root a parameter/configuration value; retain `D:/Q17` as this host's default. Invoke required Quartus executables directly and capture exit codes/logs for compile, STA and compression independently.
2. Remove reliance on `D:/vibes/fpga/bin/quartus-safe.ps1`, or deliberately vendor/pin an inspected wrapper if it provides necessary behavior. No undeclared machine-local executable may remain required.
3. Create snapshots in new empty build-ID directories from an allowlisted complete source manifest: top-level files, RTL, sys framework, QIP/Tcl/SDC and generated metadata inputs.
4. Avoid recursive merging into an old snapshot; obsolete files must not silently survive. Validate every source reference resolves inside the snapshot or to a declared tool/dependency root.
5. Separate sync status from native executable status and propagate errors accurately. Parameterize concurrency/tool paths and keep logs/artifacts outside source.

**Verification**: path with spaces; absent/wrong Quartus; native nonzero exit; removed RTL file; stale destination; incomplete sys tree; independent compile/timing/compress actions. Rebuild from a clean checkout without the external runner location available.

**Close only when** documented build commands work from the complete snapshot, fail deterministically on missing inputs and yield hashed artifacts/reports tied to C18.

**Candidate43 continuation (2026-09-08):** the snapshot helper was exercised
again after the video-source-policy and exact output-matrix changes. Candidate43
records fresh compile/compression/timing logs and artifact hashes from the
allowlisted snapshot; all four reported setup corners pass. C27 remains open
only for source review/commit, another-operator dependency reproduction and
physical target qualification.

### C28 — Provide one bounded verification entry point


**Status: IN PROGRESS · `python support/scripts/diablo.py verify --suite {foundation,host,rtl,local,arm,board}` is the bounded entry point. Candidate-bound local, ARM/QEMU, role-aware scene-oracle and target deployment-preflight evidence now pass for development candidate `d95d4cfd03154bd659343c5a77a1230bcd4efc7c45d81d4f2299a0d754128611`; candidate49 package lifecycle evidence also passes and board qualification remains an explicit incomplete tier · P2.** Dependencies: C29 result format; can be implemented early. Code: `support/scripts/diablo.py`, `support/scripts/verification.py`, `support/scripts/mister_preflight.py`, `support/scripts/scene_oracle.py`, `support/scripts/board_runner.py`, existing standalone test runners.


**Historical implementation (2026-09-08, candidate24):** each executed subprocess has a per-step timeout, process-tree termination, isolated build output and retained log. The runner records missing prerequisites and unregistered tests as `not_run`, yielding exit code 2 rather than a false pass. Candidate-24 local receipt `20260907T140421Z-4617cc3e-557c-4747-80d0-fc313b52982d.json` (SHA-256 `98d36f13b240f8f2312150ae5d2a51521883eeb4aebece831724eb40f859d7b9`, 20 registered results, 125 foundation tests with one Windows privilege skip) and ARM/QEMU receipt `20260907T140805Z-52fffaf7-e6b5-4c6b-84bb-fdd92b507e8f.json` (SHA-256 `b0d4c40b13d9d489061752d97113a218df3f8a997e0952d306e443379341c273`) pass. Both bind candidate `01eda1749ecb4d747b9dba7e914a36939c66e05a3f61a617dda85569702c019c`, manifest source identity `d50f7c4f19ae8cb5156b09a22b2e95ebe39f7bbc8518a791486a7af293d3202f` and verification source snapshot `765764590737f77ad860753cadfb3973554ab782799c3aed8827aa3825e15110`. `mister_preflight.py` separately passed the remote package/target probes for that candidate; the board-suite receipt `20260907T140958Z-0abba2b0-e961-4e94-9400-03654860b94e.json` (SHA-256 `38cbb9648b86f413f4a6220b80a3061ebdb12cdbf3f09ca4d32568e70fb69a7d`) remains historical and intentionally incomplete because no physical board configuration was supplied.
**Recorded implementation (2026-09-08, candidate25):** local receipt `20260907T145145Z-9fdcba94-f5fe-48d6-80f1-722ae3c33d27.json` (SHA-256 `235db6e6c2765ff7f4d9d4e82c3350c149b14ed61c09b760255f03a34372d8f4`, 20 registered results and 128 foundation tests with one Windows privilege skip) and ARM/QEMU receipt `20260907T145928Z-8a3731f0-66b4-445f-8fc9-869a5f8b190f.json` (SHA-256 `ef781dec13313daa1cc2ef90aba7703d08a2a6fee1707c567eb8191c2f58654a`) pass for candidate `14eaf763fab2f4ced58d72dc095a03d65293f4609631a098a0f0eb5b5d162bdf`, manifest source identity `4ae4640bfc0888e7899eeac37e337f8a703e517ffff6a326b8e40a304c305797` and manifest SHA-256 `27c4d2b04c0d00bab6aa3f3df04a33327f6107cc8b73dfd5baed37c631237416`. The clean-checkout receipt is recorded separately under C26. Both scene-oracle receipts and the read-only target preflight now bind candidate25; the board-suite receipt remains intentionally incomplete because no physical board configuration was supplied.
**Historical implementation (2026-09-08, candidate26):** local receipt `20260907T154930Z-b18c688f-47a0-4057-b23c-e206ff16ab69.json` (SHA-256 `942c0b064b51a270abe48c4e79f57f2bf6620ff9570264533930726e57082ff8`, 20 registered results and 129 foundation tests with one Windows privilege skip) and ARM/QEMU receipt `20260907T155216Z-a01d3027-eef8-43f1-8461-3d6704cd7b6c.json` (SHA-256 `829ff4b02004f5af52158dcfb435f29a5d7273314935840549a97f8675062865`) pass for candidate `b4f6f38b2bb5ec0b4ef9ff3e6624340030e0b15c234e007be2ee0fd2ce5c9dbb`, manifest source identity `13d7c55ed51ffd4b869a14271a5a780815e6c7eb0ad02166d62ee994c5ba30fd` and manifest SHA-256 `c4cfd9bc39c2361134ee107def0ea740590fb0d5e6e95d95bbcabc04f3575776`. The clean FPGA build receipt, both scene-oracle receipts, read-only target preflight and intentionally incomplete board receipt all bind candidate26.
**Recorded implementation (2026-09-08, candidate27):** local receipt `20260907T163914Z-2ac2bd6a-bae2-4739-938c-ed10ed28b557.json` (SHA-256 `2b6238cdc2037f136d09ef6480575c445d1219457ca34dec4be0deb0e368e0d4`, 20 registered results and 129 foundation tests with one Windows privilege skip) and ARM/QEMU receipt `20260907T163836Z-341002e5-50d2-4999-bae0-a83a5fe8351c.json` (SHA-256 `7733003b414f9530481a630c9587714bb7e8f250c26b69aef6da7e8e8d6cc0e8`) pass for candidate `95eaf3535aaf52d55b63f85b9bc566178c8e24b0d6f00d1e29d28a54021bcaf8`, manifest source identity `29e74b2685e333470ee383d40a977aa8b5a6da87a1a3d5106025890f1e9a42f4` and manifest SHA-256 `e83b4d6a3142ab930419bf04caf9f273df4d628619010906e51e7f0fd16a0f13`. Candidate27 scene-oracle receipts use the separately identified reference ARM role under R11; package27 and target preflight pass, and the board receipt remains intentionally incomplete. R12 is implemented: the fallback diagnostic and regression now explain the configured board runner; candidate32-bound receipts still need regeneration.
**Historical verification record (2026-09-08, candidate33):** local receipt `20260907T183544Z-8711dc3b-a375-4873-b2eb-cd28bdbb0352.json` (SHA-256 `dfa73666ce5f221cf576461838ebd21dbe3d34109a76b959882c2162fd3c5100`) passes all 20 registered checks; ARM/QEMU receipt `20260907T184334Z-743163a2-7604-477a-aa22-97489698e87e.json` (SHA-256 `6152548dc0dbaac46cff5443f43e71c5fd236567c3dc83d62d98e7377d99c722`) passes; and the role-aware Diablo/Hellfire scene-oracle receipts `20260908T-scene-oracle-diablo-candidate33b.json` and `20260908T-scene-oracle-hellfire-candidate33.json` pass. These are software/reference and ABI checks; board video, audio, input, gameplay, performance and release lifecycle remain open.
**Historical verification record (2026-09-08, candidate38):** the full Python suite passes 132 tests with one declared Windows privilege skip; `test_transport_control.py`, ABI generation check, candidate manifest verification and package verification pass. Host timedemo replay passes. ARM/QEMU timedemo replay passes with a 600-second bound and `replay_outcome_matches=true` at `.work/runtime/arm-replays/742d6ace2dd84dea88b391094bf84e9b/run.json` (SHA-256 `14aca7fd2d1af4faaba56815314d1206abb3eeecba0652e7a3f14505b155d385`). These checks still do not close board video, audio, input, gameplay, performance or release lifecycle.
**Historical verification record (2026-09-08, candidate43):** the full Python suite
passes 136 tests with one declared Windows privilege skip. Candidate-bound local
verification passes all 21 registered checks, the configured ARM/QEMU suite
passes, both role-aware scene-oracle receipts pass, package verification passes,
and the candidate43 target preflight passes. The board tier remains explicitly
incomplete because no candidate43 activation or physical observation was run.
**Current verification record (2026-09-08, candidate49):** the full Python suite
passes 141 tests with one declared Windows privilege skip. Candidate-bound local
verification, ARM/QEMU, both role-aware scene-oracle receipts, package verify,
target preflight and the deployment lifecycle receipt pass. `board_runner.py`
now publishes immutable CLI results, but candidate49 has no physical activation
or physical observation, so the board tier remains explicitly incomplete.
**Implementation procedure**

1. Add explicit suites for foundation/Python, host C++, RTL, ARM/QEMU and board qualification. Keep cheap local verification usable independently of hardware or ARM toolchain availability.
2. Discover/configure Python, C++ compiler, Icarus, WSL distribution, cross-toolchain/sysroot and QEMU; eliminate hardcoded personal cache paths as mandatory defaults.
3. Use per-process timeouts and process-tree cleanup on failure; store full logs in files and return bounded summaries. Set deliberate CPU/I/O concurrency to avoid port/lock/build-directory collisions.
4. Integrate all maintained fixtures, including audit regressions, long PCM, ABI layout and I2S/native pattern. Distinguish suite-level failure from unsupported optional prerequisites.
5. Require explicit board target/configuration for hardware suites. A generic local test command must not silently load an RBF or run destructive DDR probes.

**Verification**: simulate missing compiler/QEMU, failing compile, failing assertion, hung simulation and malformed result; ensure nonzero required-suite status, bounded termination and preserved logs. Check each test is registered once and not accidentally omitted.

**Close only when** one documented command per tier runs the full intended set, all audit regressions are included and skipped tiers never masquerade as pass. Store a suite inventory and machine-readable summary.

### C29 — Make evidence immutable and dependency-complete

**Status: IN PROGRESS · verification receipts are versioned, unique, atomic and no-replace; they bind each result/log to a full source-and-test dependency snapshot. Promotion and legacy receipt migration remain open · P2.** Dependencies: C18 IDs and C28 execution results developed together. Code: `support/scripts/verification.py`, receipt writer and acceptance validation.

**Recorded implementation (2026-09-07):** `diablo-verification-receipt-v1` stores UUID, UTC interval, requested argv/cwd, sanitized `DIABLO_*` environment, discovered tool identities, suite status, source/candidate identity, each exact command, exit/timeout result and SHA-256/size of its preserved log. Receipts are written under `.mister/evidence/receipts/` with a timestamp and UUID, using a no-replace atomic publish. Unit tests prove failed commands retain logs and an earlier receipt cannot be replaced. A supplied candidate manifest is verified before checks run; without one the record explicitly says it is a source snapshot and cannot promote a board candidate.

**Candidate49 evidence continuation (2026-09-08):** candidate-bound local and
ARM/QEMU receipts retain the candidate ID plus the verification source snapshot;
the scene-oracle, package-preflight and deployment-lifecycle receipts bind the
same candidate and use no-replace publication. The new board-runner CLI also
refuses to overwrite a result or log. Promotion remains open until physical
receipts enumerate the exact output matrix, audio, input, campaign, performance
and lifecycle observations.

**Implementation procedure**

1. Define a versioned receipt schema with unique run ID, UTC times, candidate/input hashes, exact argv/cwd, tool identity, environment allowlist, test configuration/seeds, exit/timeout status and evidence scope.
2. Hash transitive relevant inputs: source, included headers/generated ABI, testbench, fixtures, overlays, scripts, build options and lockfiles. Do not record only the top-level `.sv` when its ABI include can change.
3. Write to a new path atomically; never overwrite dated historical acceptance files on a rerun. Keep failures and aborted runs as first-class receipts.
4. Represent pass/fail/skipped/not-run separately for host, RTL, QEMU and physical board. An ARM-skipped run must not inherit a top-level “ARM passed” claim.
5. Validate referenced paths/hashes before promotion and redact secrets/private data from public receipt content. Private captures can be referenced by private identity without embedding them.

**Verification**: mutate an included file, delete a log, tamper with a receipt/artifact, rerun same date, interrupt writing and skip ARM. Acceptance must reject mismatched/incomplete evidence and preserve earlier files.

**Close only when** all maintained runners use the schema or have an explicit historical adapter, dependency changes invalidate acceptance and every closed item links to resolvable immutable evidence.

### C30 — Reconcile README, root guide and machine state

**Status: IN PROGRESS · README, root guide, ARM runtime guide and `.mister/state.json` distinguish implemented local capability from a current accepted candidate and designate this plan as closure authority. Automated guide/state digest and local-link validation now reject stale descriptions; candidate-specific promotion and final receipt-link validation remain open · P2.** Dependencies: C18 current identity, C29 evidence and this plan's status model. Code: README, `CORE_COMPLETION_AUDIT.md`, `support/ARM_RUNTIME.md`, `.mister/state.json`, `support/scripts/guide_status.py`, audit index links.

**Recorded implementation (2026-09-07):** README no longer says there is no adapter, ABI or accelerator; it describes the prototype and its acceptance limits and lists the immutable local verification entry point. The root completion guide defers current-candidate decisions to this detailed audit plan and machine state. The ARM guide documents the current physical mapping contract: candidate ID, live-boot admission record and non-conflicting lease are all mandatory before `/dev/mem` mapping. Historical observations remain preserved but explicitly cannot validate later source changes. `support/scripts/guide_status.py` now requires the three guides to link the detailed plan, checks every local Markdown link, verifies that `.mister/state.json` hashes this plan, rejects prose labeled as an exact command, and requires an explicit no-current-candidate state until C18/C29 promotion exists. Its unit fixture covers a valid guide set, stale digest, broken link and misleading command label.

**Candidate49 documentation continuation (historical, 2026-09-08):** its source/manifest
identities, package staging path and local/ARM/scene/preflight/lifecycle receipts
remain preserved as historical evidence. `.mister/state.json` declares
`no-current-accepted-candidate`; C25 is source-accepted, a fresh current-SDC FPGA
build is underway, and physical qualification blockers remain explicit. The guide
digest must be recomputed after this plan edit before state validation can pass.

**Implementation procedure**

1. Replace stale “no adapter/ABI/accelerator” descriptions with implemented capability and its precise evidence limit. Reopen correctness claims affected by F01–F18 while preserving historical successful test facts.
2. Make one document the execution authority and link other documents to it. Retain this detailed C-item plan as the closure reference; do not leave multiple conflicting next-action paragraphs.
3. Separate current candidate/accepted candidate/current blockers from historical process IDs, failed experiments and old build narratives. Move history into referenced immutable receipts without deleting evidence.
4. Store either an actual executable command with cwd/prerequisites/expected outcome, or a clearly named `next_action` for non-command work. Never label a prose paragraph “exact command.”
5. Update the guide digest and evidence pointers consistently when changing the root guide during future implementation. Add validation for missing links, mismatched guide hash and closed items without receipts.

**Verification**: read the project as a fresh contributor; commands and status must agree with source/artifacts. Automated checks reject stale hashes and broken receipt links. Confirm the intentionally removed old plan is not reintroduced.

**Close only when** README/guide/state consistently identify the candidate, remaining gates and next action, and their status checks pass. This recorded progress validates local documents and the detailed-plan digest; a promoted immutable candidate with all closed-item receipt links remains required before closure.

### C31 — Encode explicit scope, dependencies and measurable acceptance

**Status: IN PROGRESS — the machine-enforced matrix remains valid, but the output scope was refined on 2026-09-08 into separate HDMI framebuffer/scaler, direct RGB and analog/scandoubler rows; new matrix-bound evidence and a closure record are required · P2.** Dependencies: this document defines the policy; C13/C21/C23 consume the checked matrix. Later matrix, scope or measurement changes reopen this item through the recorded invalidation policy.

**Recorded closure (2026-09-07):** `support/qualification/closure-gates.json` is a versioned matrix covering C01–C34 exactly once. It fixes the required Diablo/Hellfire, output, control, multiplayer and lifecycle scope; records the 60 Hz/60 FPS, p99, input-latency and duration thresholds; declares every C-item's prerequisites, required immutable evidence and invalidating change classes. `support/scripts/closure_gates.py` validates the linked C-item headings and matrix shape, hashes the full matrix into each closure record, rejects missing/open/blocked dependencies, verifies cited artifacts and passing receipt hashes/source identities, and requires a named approver/rationale for a waiver. Its synthetic fixture proves complete evidence can pass while open work, changed source identity and tampered receipts fail. Foundation receipt `20260907T031308Z-1941aea9-335b-45e1-930a-80bed7a12797.json` passed these checks for source snapshot `41a151bc771d6ab81fe1fe71573fa50c202c5e13a0a576a37eea0bed6b2e9243`.
**Recorded closure (2026-09-07):** `support/qualification/closure-gates.json` is a versioned matrix covering C01–C34 exactly once. It fixes the required Diablo/Hellfire, output, control, multiplayer and lifecycle scope; records the 60 Hz/60 FPS, p99, input-latency and duration thresholds; declares every C-item's prerequisites, required immutable evidence and invalidating change classes. `support/scripts/closure_gates.py` validates the linked C-item headings and matrix shape, hashes the full matrix into each closure record, rejects missing/open/blocked dependencies, verifies cited artifacts and passing receipt hashes/source identities, and requires a named approver/rationale for a waiver. Its synthetic fixture proves complete evidence can pass while open work, changed source identity and tampered receipts fail. Foundation receipt `20260907T031308Z-1941aea9-335b-45e1-930a-80bed7a12797.json` passed these checks for source snapshot `41a151bc771d6ab81fe1fe71573fa50c202c5e13a0a576a37eea0bed6b2e9243`.

**Scope refinement (2026-09-08):** `scope.output_modes` now names the three
release rows verbatim and the validator rejects a return to generic two-line
video descriptions. Candidate43 and its receipts bind matrix digest
`09bb6127f33e110b5a676358d892fe588f216d41027726948dac749311dccbe7`. C31
remains open until the mode-specific physical evidence and final approval are
recorded; candidate49 carries the same matrix digest for release-lifecycle
evidence but does not waive the three physical rows.

**Implementation procedure**

1. Convert stage and C-item dependencies into a maintained gate matrix with required host/RTL/board/package evidence. Separate implementation status from acceptance status.
2. Record supported campaigns, output modes, control devices, multiplayer combinations and lifecycle workflows. The current baseline matrix has broad entries for native MiSTer timing output and accelerated indexed framebuffer presentation; before C13 qualification, expand `output_modes` into the exact applicable rows (HDMI framebuffer/scaler, direct native RGB, analog/scandoubled or other required connector paths) with connector, geometry, refresh, sync, palette/source and equipment requirements. Update the matrix hash and reopen C31 through its invalidation policy while this scope refinement is reviewed; existing requirements remain required until an explicit scope decision changes them.
3. Encode simulation/render/publication/display rate definitions and the numeric correctness, latency, service and duration targets from this plan in versioned qualification configuration.
4. Preserve the approximately 60 FPS target as an open gate. If a different release threshold is proposed, document the tradeoff and obtain the scope decision rather than silently reducing the requirement.
5. Define which changes invalidate which gates: renderer changes reopen equality/performance; RTL/SDC changes reopen build/timing/board; launcher changes reopen lifecycle/install. Avoid both blanket invalidation and unjustified evidence reuse.

**Verification**: run the gate evaluator against incomplete/failed/mismatched receipts and ensure release remains blocked; test a complete synthetic fixture and a source-change invalidation fixture. Review that every C01–C34 has a required closure record and no circular acceptance dependency.

**Close only when** scope and targets are explicit, machine/document checks enforce them and no pending requirement can disappear through a changed label. Writing this plan establishes intent but does not alone implement the gate evaluator.

### C32 — Produce and verify the clean-install release package

**Status: IN PROGRESS — package/deployment v2 and target launcher verification are implemented; clean install/update/rollback, notices/setup, menu integration, second launch and physical acceptance remain open · P2.** Dependencies: all required correctness/runtime/physical/performance gates, C18/C25–C31. Code: `support/scripts/package_release.py`, `support/scripts/deployment_manifest.py`, launcher and release documentation.

**Recorded implementation (2026-09-08):** package_release.py now emits
deployment/package manifest v2 with four fixed runtime roles and the complete
asset tree. Candidate33's package contains devilutionx, Diablo.rbf,
transport_abi.hex, diablo_launcher.py, deployment.json, package-manifest.json
and 184 asset files (190 files total); local verification and target preflight
pass. The target launcher independently verifies that contract and runs without
a Git checkout. Candidate31 normal launcher smoke proved current-boot admission,
exact RBF process matching and live frame publication; it did not prove video,
audio, input, gameplay or performance. Clean-image install/update/interrupted-
update/rollback, a menu-visible entry, required notices/setup instructions and
second launch remain release gates.
**Candidate38 package continuation (2026-09-08):** the corrected v2 package is `.work/package-board-candidate-38`, staged at `\\192.168.0.69\sdcard\_CodexDiabloCandidate38`, and contains 190 files: the four runtime roles plus 184 assets. Package manifest SHA-256 is `115998423d0409a2f10c192cf5c8487d340bc4bfd3cae2e2d88d37c1d3182896`. The package intentionally excludes licensed MPQs, saves and private captures; C32 remains open until a clean supported image proves install/update/rollback, notices, menu entry, both campaigns and a second launch.

**Candidate41 package continuation (historical, 2026-09-08):** package41 was a historical
190-file runtime package with 184 assets, staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate41`; its package manifest SHA is
`3c2b274f139b8b50a4a7107b395c1685f321985c9daacd8ddfb4290556d711c9`. Candidate
manifest verification, package verification and target preflight pass. The
package intentionally excludes licensed MPQs, saves and private captures. C32
remains open for clean-image install, interrupted update, rollback, menu entry,
notices, both campaigns, save preservation and a second launch.

**Candidate43 package continuation (historical, 2026-09-08):** package43 was a historical
190-file runtime package with 184 assets, built from the candidate43 manifest,
verified locally and staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate43`. Its package manifest SHA is
`595049590830e384a359aec6a70a080483563e151c93de2df205bafc95f10154`; the
read-only target preflight passes at
`.mister/evidence/receipts/20260908T-candidate43-preflight-rerun.json` (SHA
`993ccfd3d45d22cdf911016fabd2572c1912897b639e945b4f1baa6adc8ca60b`). A
transient first probe missed root `MiSTer.ini` and is retained as a failed
diagnostic; the immediate rerun passed. C32 remains open for clean-image
install, interrupted update, rollback, menu entry, notices, both campaigns,
save preservation and a second launch.

**Candidate49 lifecycle continuation (historical, 2026-09-08):** package49 was a historical
192-file runtime package with 184 assets, `NOTICE.txt` and `SETUP.md`, built from
the candidate49 manifest, verified locally and staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate49FinalLocal`. Its package
manifest SHA is `f09bd76e1b4c80d7eb6391409dc1724f573a5931d4cf644ed7092573e49e63f3`;
the target preflight passes at
`.mister/evidence/receipts/20260908T-candidate49-preflight.json` (SHA
`64d827d9d29953396c55be9314ae19fde04aa63820370573fab9de3d594a1b78`). The new
`deploy_package.py` transaction and
`.mister/evidence/receipts/20260908T-candidate49-deployment-lifecycle.json`
(SHA `324d8ad330f940de78d52d77f372b8c04cbf7dce10eeb3278e899410dee14c01`)
prove local install, interrupted-update preservation, update, rollback, save
preservation and final manifest verification. Clean supported-image install,
menu entry, both campaigns, save/load/reset/core-switch/relaunch and second
launch remain physical gates.

**Implementation procedure**

1. Define an allowlisted package containing matching ARM/RBF, launcher, ABI/build manifest, redistributable assets, notices and setup instructions. Resolve each component's recorded distribution disposition before including it; do not infer an aggregate license.
2. Build from immutable accepted artifacts, verify all hashes and scan package contents for MPQs, saves, private captures, donor-only material, credentials and machine-specific paths.
3. Implement install/update preflight, enough-space checks, verified staging and a recoverable activation sequence. Preserve existing saves/configuration and keep a compatible previous install recoverable on failure.
4. Guide users to supply their own data and clearly report missing/incompatible data. Avoid overwriting user content to make a test install pass.
5. Test on a clean supported MiSTer using the distributed package, then run both campaign launch/play/save/load/quit/reset/core-switch/relaunch workflows and a second independent launch.

**Verification**: package hash mismatch, interrupted copy, insufficient space, wrong ABI, missing data, old install upgrade and rollback. Verify resulting files exactly match the manifest and save/config hashes are preserved where expected.

**Close only when** the clean install and upgrade/failure matrix pass using final accepted artifacts, required notices/provenance are complete and no unresolved required gate is hidden by packaging success.

### C33 — Clean generated root artifacts without losing evidence

**Status: IN PROGRESS · P3.** Dependencies: C26 classification; C18 preserves meaningful artifacts. Code: ignore rules, build/log output paths and root generated files.

**Recorded implementation (2026-09-07):** the refresh inventory identified only
the untracked Icarus/VVP default `a.out` and Quartus `c5_pin_model_dump.txt` at
the project root. Their hashes and non-private generated disposition are recorded
in `refresh-evidence/generated-root-disposition.json`; both files were moved to
`.work/build/root-generated-disposition`, `/a.out` and
`/c5_pin_model_dump.txt` are now narrow ignores, and `clean.bat` removes them.
The root listing is clean for these artifacts; a detached clean-checkout check
only shows those artifacts were absent at inspection time.

**Superseded observation (2026-09-08; not closure evidence):** the current root and detached clean-checkout
contain neither `a.out` nor `c5_pin_model_dump.txt`; both files have explicit
ignore and cleanup rules, and the disposition artifact remains passing. The
candidate49-bound receipt is
`.mister/evidence/receipts/20260908T-candidate49-root-cleanliness.json`
(SHA-256 `98627a4bb17ea6e62e571cf37e9730ca0f672520048cdf6d9dced4dcd9b36da7`).
This observation does not close C33: producer execution and destination evidence
are still required.

**Implementation procedure**

1. Identify who created `$null`, `a.out`, pin dumps and similar root files, whether they are referenced by receipts, and whether they contain unique useful diagnostics. Do not delete solely by filename.
2. Preserve referenced evidence in a build/run-specific ignored location and update references before moving it. Move disposable generated output to `.work`/configured build directories or remove only after confirming it is reproducible/unneeded.
3. Fix the producing commands: use shell-correct null redirection and explicit compiler/log output paths so the clutter does not immediately return.
4. Add narrow ignore rules for generated executables/simulations, keeping source reproductions and non-private audit results reviewable. Avoid ignores broad enough to hide intended source.
5. On Windows, verify absolute source/destination paths are inside the intended workspace before recursive operations; use native literal-path operations.

**Verification**: run representative build/tests and inspect Git status/root listing; no accidental files return, evidence references resolve and private data remains excluded.

**Close only when** all identified clutter has a documented disposition and its producers write to the intended locations. This is cleanup, not permission to discard unrelated user files.

### C34 — Refactor stale scaffolding and clarify ownership boundaries

**Status: OPEN · P3.** Dependencies: functional interfaces C01–C17 stabilized; C28 regression entry point. Code: adapter, stale comments, demo/template files and project source lists.

**Implementation procedure**

1. Inventory obsolete comments (“future consumer,” “slot zero”), duplicated initialization and apparently unused demo files. Prove usage through QIP/source lists and references before removing anything.
2. Centralize initialization/reset logic around explicit lifecycle state, ensuring repeated initialize/shutdown/rebind calls reset the intended fields exactly once.
3. Split the large SDL adapter along real ownership boundaries: lifecycle/session, frame submission/cache, command completion, audio publication/resampling and input reconciliation. Keep clear APIs and avoid introducing cross-module mutable globals.
4. Keep this refactor separate from behavioral fixes so regressions can be bisected. Preserve fixed-capacity storage and callback constraints; do not add allocations or blocking calls on hot paths.
5. Update comments and architecture documentation to explain actual ownership and failure behavior, including what stays in the imported framework.

**Verification**: full local suites, differential scene cases, startup/shutdown/reset repetition and profiling-overhead checks. If generated binaries/RTL change, create a new candidate and rerun gates invalidated under C31.

**Close only when** unused scaffolding is demonstrably unused/removed, module ownership is documented, behavior remains equivalent and the final candidate's evidence is still valid.

## Finding-to-closure traceability

| Audit finding | Required work packages |
| --- | --- |
| F01 rectangle corruption | C01; integrated equality C19 |
| F02 stale mixed-writer caches | C02; epoch handling C07; C19 |
| F03 two-vblank cadence | C03; integrated scheduling C09; display measurement C21 |
| F04 stranded READY slots | C04; C09; target stress C23 |
| F05 palette/frame mismatch | C05; decoded equality C19 |
| F06 forgotten timeout ownership | C06; reset C07; fault integration C09 |
| F07 audio/reset race | C07; active audio qualification C15 |
| F08 wrong OSD focus source | C10; physical controls C23 |
| F09 modifier/text integration | C11; naming/chat/controller qualification C24 |
| F10 mouse masks/queue recovery | C12; focus/state C10; physical C23 |
| F11 native output test pattern | C13; timing C25; physical C23 |
| F12 stale artifact identity | C18; immutable receipts C29; state C30 |
| F13 unversioned implementation | C26; clean builds C27; install C32 |
| F14 external runner/snapshot dependency | C27; clean-checkout verification C26 |
| F15 biased/incomplete performance metrics | C20 and C21; acceptance definitions C31 |
| F16 incomplete checksum meaning | C22; full equality C19 |
| F17 unsafe clipping arithmetic | C08; independent oracle C19 |
| F18 silent dummy startup failure | C14; launcher error handling C16 |

Additional original blockers are explicitly owned: active audio C15; launcher C16; memory admission C17; full scenes C19; physical endurance C23; multiplayer/controller-only C24; external timing C25; test/evidence infrastructure C28/C29; release/provenance/private-data exclusion C32. Maintenance improvements are C33/C34, R06 tracks the candidate-identity parser regression, R11 tracks the ARM evidence-role split, and R12 tracks the stale board-fallback diagnostic. No original recommendation is implicitly waived.

## Final completion checklist

- [ ] Every C01–C34 and R01–R12 has a CLOSED record and its compact checklist box checked, or an explicitly approved scope disposition linked to the original requirement. A blocked item prevents an unqualified “everything complete” statement.
- [ ] Every F01–F18 has its primary fix and listed integration/qualification evidence; all new failures discovered during implementation have their own tracked closure.
- [ ] All passing evidence matches the final source/ARM/RBF/ABI/configuration; changed components have reopened and re-passed affected gates.
- [ ] Complete equality, real-vblank cadence, active audio, physical controls, campaigns, save integrity, multiplayer, timing and performance targets pass.
- [ ] Clean checkout/build, package composition, installation/update and second-launch qualification pass; private data and user saves remain protected.
- [ ] README/root guide/state identify the final accepted build, supported modes, measured results and any explicit limitations consistently.

Only then report the audit as fully closed. Report the actual measured outcomes and artifact IDs, not merely the number of implemented patches.

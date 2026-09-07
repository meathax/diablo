# Diablo project audit — 7 September 2026

## Verdict and scope

The working tree contains a substantial ARM/FPGA integration prototype, but it is not ready for release or a claim of correct accelerated gameplay. Existing unit tests pass, yet this audit reproduces pixel corruption, palette-cache corruption and a permanently stranded frame slot. The scanout state machine also prevents one new frame per display refresh. Fix these before treating further command-path performance results as acceptance evidence.

This is an audit of the local working tree, not merely HEAD. `source-manifest.json` records the reviewed project source hashes and Git commit. Existing user changes were preserved. The original completion guide and state document were not rewritten; a proposed replacement sequence is in `PROPOSED_PLAN.md`, and the complete recommendation checklist is in `SUGGESTED_CHANGES.md`.

Reviewed: project RTL and integration, C++ transport/render/input/audio adapters, build overlays and scripts, Python tests, RTL fixtures, source locking, local Quartus summaries, and relevant historical hardware receipts. The engine was inspected selectively at integration boundaries; this is not an exhaustive audit of all upstream DevilutionX or imported MiSTer source. No board was loaded, no live board state was changed, and no fresh Quartus or full ARM/host engine build was performed. Hardware observations below are explicitly from saved receipts. Commercial data and donor checkouts were left untouched.

## Verification performed

| Check | Result |
| --- | --- |
| Python unittest discovery under `support/tests` | 68 tests passed |
| Generated transport ABI freshness | Passed |
| C++ software command renderer | Passed |
| C++ command-ring publisher | Passed |
| C++ transport ABI/session fixture | Passed |
| RTL ABI fixture using the audit-generated C++ header image | Passed |
| Command consumer, DDR probe, framebuffer scanout, frame ownership, input capture | All five existing RTL fixtures passed |
| PCM player, long PCM queue, DDR arbiter, control reader | All four existing RTL fixtures passed |
| I2S serializer and native test pattern | Both existing fixtures passed |
| New changed-run reproduction | **Failed equality: two incorrect pixels** |
| New mixed-writer palette-cache reproduction | **Failed equality: expected byte 2, actual byte 9** |
| Extended scanout diagnostic | **Confirmed stale READY slot and palette upload before frame-base switch** |

Twelve RTL fixtures passed in total, including ABI. Logs and reproduction sources are beside this report. The first ad hoc invocation of the long PCM fixture omitted its RTL dependency; that audit-harness mistake was corrected and the proper test passed (`pcm-long.log`). It is not a project finding.

The existing `output_files/Diablo.sta.summary` contained 148 timing entries with no negative slack/TNS in those entries: minimum setup 0.188 ns, hold 0.078 ns, recovery 4.319 ns, removal 0.421 ns and minimum pulse width 0.396 ns. This is a reading of existing reports, not fresh timing sign-off or proof of complete constraints. `timing-summary.json` preserves the extraction.

## Findings

Priority P1 means fix before correctness/qualification acceptance; P2 means address before reproducible release or reliable measurement. “Reproduced” refers to new local execution; “code-confirmed” refers to an explicit implementation path; “risk” means the triggering full-system behavior has not been reproduced here.

### F01 — P1 — Rectangle coalescing corrupts pixels on the second row [reproduced]

Location: `support/reference/mister_command_scene.hpp:43–44,66–80`.

`previous_by_x` and `map_generation` begin at zero. On row 1, a column that had no run on row 0 can nevertheless satisfy `map_generation[start] == row - 1`. Its default index selects run zero from the previous row. If width and colour match, the code extends that unrelated rectangle and marks it continued without checking its x coordinate or that the entry was actually populated.

Minimal case: zero-filled shadow; source has colour 7 only at `(10,0)` and `(20,1)`. `BuildChangedRuns` succeeds but emits one rectangle `(10,0,1,2)`. Executing it leaves two pixels wrong. See `repro_changed_runs.cpp` and its log.

Change: use an unambiguous invalid generation/index, verify the previous index is below `previous_count`, and require matching x. Add sparse second-row, absent-column, empty-first-row and randomized full-frame differential tests. Rebuild the ARM overlay and invalidate prior accelerated pixel-correctness conclusions for affected binaries.

### F02 — P1 — Command writes invalidate neither full-copy palette nor dirty-pixel caches [reproduced palette; code-confirmed dirty-copy risk]

Locations: `support/reference/mister_transport.hpp:85–130`; `support/reference/mister_transport_sdl.hpp:369–398`.

The full-copy session caches each slot's palette and optionally its pixels. The command path writes that same slot directly, bypassing those caches. After full-copy palette A, command palette B, then full-copy palette A again, the session believes A is still in memory and skips its write. The reproduction uses the public ownership state machine and the same direct palette write used by the command adapter: requested byte 2 remains byte 9.

With both `DIABLO_MISTER_COMMAND_SCENE` and `DIABLO_MISTER_DIRTY_COPY` enabled, the analogous stale pixel shadow can suppress required pixel writes. The palette failure does not require dirty-copy mode.

Change: centralize per-slot content generations/cache ownership, or explicitly invalidate both session caches on every command write. Cover A→B→A palette changes and command/full-copy/dirty-copy transitions in integration tests.

### F03 — P1 — Scanout needs two vblank edges per new displayed frame [code-confirmed]

Location: `rtl/diablo_framebuffer_scanout.sv:223–243,305–314`.

Metadata acquisition starts only on a vblank edge when no frame is pending. After acquisition and palette upload, a second edge activates the pending frame. The activation branch does not start acquiring the next frame. Consequently, steady-state activation can occur at most every other vblank even with ready frames and fast DDR. At a 60 Hz vblank source this is a 30-new-frame/s ceiling, independent of ARM rendering speed. Actual HDMI refresh was not measured here.

The existing fixture explicitly supplies two vblank pulses for each frame (`support/tests/diablo_framebuffer_scanout_tb.sv:154–169`), so it accepts this limitation.

Change: prepare the next frame between boundaries; commit it once per vblank. Add a periodic-vblank throughput test with continuous ready frames, asserting one activation per refresh after warm-up and measuring admission-to-display latency.

### F04 — P1 — Superseded READY frames are never reclaimed [reproduced and supported by historical board logs]

Location: `rtl/diablo_framebuffer_scanout.sv:87–96,224–239,315–322`.

Selection chooses the newest ready frame newer than the active frame. Only a previously displayed slot is retired. An older ready frame that loses selection is never displayed and never freed. It permanently consumes a slot until session reset.

The extended fixture leaves slot 2 at READY/id 6 after id 8 is active and after further vblanks. Historical live-command evidence similarly ends with READY/id 7 while id 157 is displaying; the relaunch has READY/id 15 while id 145 displays (`.mister/evidence/arm-command-scene-live-hardware-20260907.json`, `runs.*.frames`). This undermines the “full three-slot pipeline” assumption even where command cursors match.

Change: specify FIFO presentation or an explicit safe superseded-frame retirement protocol. Never free a displayed, pending, command-owned or still-written slot. Add sustained producer-faster-than-display tests with an invariant that every submitted frame is eventually displayed or explicitly retired.

### F05 — P1 — Palette and indexed frame are committed at different boundaries [reproduced ordering; visible effect inferred]

Location: `rtl/diablo_framebuffer_scanout.sv:165–192,224–239,305–314`; scaler connection at `sys/sys_top.v:802–809`.

The next palette is uploaded to the live scaler palette interface before the pending framebuffer base is selected on a later vblank. The diagnostic observes 512 palette writes while the old frame base remains selected. The existing fixture uses the same palette pattern for both frames, so it cannot detect wrong palette/frame pairing.

A palette-changing scene can therefore present old indices with the next palette; upload completion under delayed DDR also lacks a displayed-frame atomicity guarantee. Physical pixels were not captured here.

Change: stage palette privately and make palette/base ownership atomic at the presentation boundary, using a supported bank switch or a bounded blanking commit protocol. Test deliberately different palettes, palette animation and delayed palette reads against decoded RGB output.

### F06 — P1 — Command fence timeout can strand ARM-owned slots without recovery [code-confirmed]

Locations: `support/reference/mister_transport_sdl.hpp:306–317,330–383`; `Diablo.sv:217–233`; `support/reference/mister_transport_runtime.hpp:135–146`.

Once records are published, timeout returns false while the acquired slot remains `ArmWriting`. There is no retained pending-submission object to finish or retire that frame when its fence later arrives. Repeated late completions can strand every slot. Immediate abort would also be unsafe because queued FPGA writes may still execute.

The command consumer's `command_fault` is wired only to a local top-level wire, while ARM recovery reacts only to shared `fpga_state == Fault`. A command-path fault or late fence does not necessarily trigger that recovery. The default wait is 25 ms, already longer than the desired 16.67 ms presentation deadline, and poll counts plus nanosleep are not an absolute wall-clock deadline.

Change: retain outstanding slot/fence/epoch state; reconcile late completion; expose command faults through the transport status; recover via a quiesced epoch handshake. Use monotonic deadlines. Test a completion just after timeout, malformed records, reset during writes and eventual recovery without buffer reuse races.

### F07 — P1 — Video reset recovery races the audio callback [code-confirmed concurrency risk]

Locations: `support/reference/mister_transport_sdl.hpp:128–133,207–274`; `support/reference/mister_transport_runtime.hpp:135–146`; `support/reference/transport_abi.hpp:159–161`; `support/cmake/arm-transport.cmake:135–138`.

The Aulib SDL audio callback calls `PublishPcmBytes` on the shared adapter. Concurrently, presentation recovery reinitializes the shared control page and mutates the session epoch and non-atomic resampler fields. There is no callback quiescence or synchronization around that recovery. Atomics on ring cursors do not protect the ordinary C++ resampler/session state or the control-page memset.

Change: stop/quiesce callback publication during epoch transitions, retain a single owner for resampler state, and resume only after a validated attachment. Exercise repeated resets while audio is active. This audit did not reproduce an audio-thread race with a sanitizer or on hardware; normal engine shutdown already deinitializes sound before video cleanup, so this finding specifically concerns live recovery.

### F08 — P1 — OSD focus transport is connected to button bits, not OSD status [code-confirmed]

Locations: `Diablo.sv:196–205`; `rtl/diablo_input_capture.sv:92,283–293`; `sys/emu_ports.vh:153`.

The input capture emits focus changes from the two `buttons` bits. The actual `OSD_STATUS` top-level input exists but is not connected to this transport. Opening or closing OSD is therefore not reliably represented by the focus events consumed by `PumpInput`.

Change: pass the actual OSD state, define focus-loss behavior, release held game actions and resynchronize on focus gain. Test OSD navigation while keys, mouse buttons and controller actions are held, including opening OSD without a physical button transition.

### F09 — P1 — Keyboard bridge lacks modifier/text-state integration [code-confirmed missing paths]

Locations: `support/reference/mister_transport_sdl.hpp:664–688,806–814`; upstream `.work/sources/devilutionx/Source/engine/events.cpp:63` and `Source/diablo.cpp:813,831`.

The bridge pushes key events with `KMOD_NONE`, does not maintain SDL modifier state and emits no text-input events. The engine reads `SDL_GetModState` for actual actions, including Ctrl+wheel automap behavior. Synthetic key queue entries alone are insufficient to supply that state or the text-input pipeline needed by SDL text consumers. Key-event conversion receipts do not establish character naming/chat correctness.

Change: define a keyboard state/modifier and text-entry integration for the transport backend; validate Ctrl/Shift combinations, character naming and multiplayer chat in the actual engine. Avoid duplicate text generation when a real SDL backend is also enabled.

### F10 — P2 — Mouse motion masks and queue-failure recovery are incomplete [code-confirmed]

Locations: `support/reference/mister_transport_sdl.hpp:657–661,691–734,737–757`.

Mouse button-edge events translate PS/2 left/right/middle order, but motion events copy the raw PS/2 mask directly into SDL's left/middle/right mask field. Right and middle are consequently inconsistent between motion and button events. In addition, failed SDL queue publication only logs; local mouse/controller masks advance anyway, potentially preventing a dropped press/release from being retried. Overflow recovery sends focus events and clears local masks rather than explicitly reconciling all held keys.

Change: translate motion masks explicitly, retain desired versus delivered state, and resynchronize after queue failure/focus changes. Test right/middle dragging, queue saturation and keyboard/controller keys held simultaneously.

### F11 — P1 — Native VGA/direct-video path still displays the test pattern [code-confirmed; output-mode qualification open]

Location: `Diablo.sv:35,263–267`.

Game pixels are supplied through the indexed framebuffer/scaler interface. Native `VGA_R/G/B`, sync and DE remain driven by `native_test_pattern`, with `VGA_SCALER = 0`. A mode consuming native video therefore receives the diagnostic pattern rather than the game. User-configured scaler-based analog output may behave differently; this audit did not observe the board.

Change: explicitly support and test the intended analog/direct-video modes, route game output where required, or state a supported-output limitation and hide incompatible choices. The plan's “inspect analog output” gate needs an implementation prerequisite, not just a visual check.

### F12 — P1 — Current artifact paths no longer identify the accepted board binaries [measured local mismatch]

Locations: `.mister/state.json` (`arm_engine_transport.artifact`, `latest_fpga_command_consumer_build`); `.mister/evidence/fpga-command-consumer-faultclear-build-20260907.json`; `CORE_COMPLETION_AUDIT.md` Step 10.

At inspection, `output_files/Diablo.rbf` hashed to `e35716dded560a183aca422490948de01b57de594788b29719c36c869c697c23`, rather than the guide/board receipt's `4142126272d5b8613b990e6ecc5c25687e9c4c54d8a2c9d37fe7508bae4a77f5`. The local ARM artifact hashed to `949bf5a8cbf40727e59839cdb9867be74644aa51a6467e314b61d9606621f173`, rather than the state's `29d0870b3f98ec3f33aee29c719fc88c185f5fbd36c63776b3a0d16c4717919e`.

The latest referenced FPGA receipt says seed 1; the current QSF selects seed 2. Current timing minima also differ from that receipt. These may be legitimate newer development builds, but the old acceptance cannot be transferred to them. No claim is made that the board's files changed. The completion-document hash itself matches state correctly.

Change: immutable build-ID directories and a manifest binding source snapshot, constraints, toolchain, ARM binary, RBF, ABI and tests. Separate `development_candidate` from `board_accepted`; validate all hashes before deployment or reusing evidence.

### F13 — P1 — The implemented core is largely outside version control [measured]

At inventory, Git reported 329 untracked files among 361 status entries, including `Diablo.sv`, project files, `rtl/`, `sys/`, adapters, overlays, tests and the new completion guide. A fresh checkout of committed HEAD cannot reproduce this working prototype. This audit adds further report files; the counts above precede those later additions.

Change: review and commit intended implementation/support files in coherent changes, preserving the requested deletion of the obsolete plan. Exclude generated binaries, reports that contain private data, and accidental `$null`/`a.out` artifacts. Validate a clean checkout before packaging. Do not blindly add all untracked content.

### F14 — P2 — Build helper retains an external runner dependency and incomplete snapshot contract [code-confirmed]

Location: `support/scripts/compile_fpga_snapshot.ps1:12,22–39`.

The guide says the retired custom runner is not required, but the helper invokes `D:/vibes/fpga/bin/quartus-safe.ps1` for compile/timing/compression. It exists on this machine, so this is a portability/reproducibility blocker rather than a present missing-file failure. Its sync action copies top-level files and RTL but relies on an already populated `sys/` tree and retains obsolete destination files.

Change: invoke a configured Quartus installation directly, or vendor/document the runner deliberately. Define a complete clean snapshot operation with framework provenance and exact file manifest. Keep external invocation exit status separate from sync operations.

### F15 — P2 — Performance instrumentation excludes expensive failures and lacks the requested metrics [code-confirmed]

Locations: `support/reference/mister_transport_sdl.hpp:352–387,487–550`.

Build timing is recorded only after successful command construction and End insertion, so overflow builds are omitted. Fence timing is recorded only after successful waits, excluding timeouts. Those exclusions can make reported stage averages look better while fallback and failure rates increase. Only counts, averages and maxima are emitted; p95/p99/p99.9, missed deadlines and input-to-visible latency requested by the guide are absent.

The guide records about 11–12 FPS for its recent command timedemos. This remains far below its target, and those short dummy-SDL runs are not a controlled comparison against a matching software-only run. Earlier saved runs use different builds/configurations and should not be compared as a clean A/B experiment.

Change: record every attempted stage, its outcome, fallback cause and wall-clock deadline; collect bounded histograms or timestamp traces. Benchmark paired binaries on identical deterministic scenes, warm-up and configuration, with uncertainty and loading stalls separated. Fix F01–F06 before optimizing this path.

### F16 — P2 — Checksums do not establish complete frame correctness [code-confirmed]

Locations: `support/reference/mister_transport.hpp:194–215`; `support/reference/mister_transport_sdl.hpp:390–391`.

Default “CRC” samples only one of every 16 pixel columns, and command-rendered frames publish zero CRC. Neither verifies actual FPGA-written pixels. This is acceptable as explicitly labeled diagnostic metadata, but must not support full-frame equality claims.

Change: version/name sampled and full checksums distinctly. Qualification must compare every index and palette byte from the completed target slot against an independent reference, then separately check displayed RGB. Keep expensive readback out of production timing runs or account for its cost explicitly.

### F17 — P2 — Malformed rectangle arithmetic can overflow the software oracle [code-confirmed boundary risk]

Location: `support/reference/mister_command_renderer.hpp:152–159,177–178`.

Rectangle addition/subtraction and negation use signed 32-bit arithmetic on 32-bit record coordinates. Values such as `INT_MAX + width` or `-INT_MIN` exceed that range. Normal scene-generated coordinates are small, but malformed-record testing must not rely on an oracle with undefined arithmetic at exactly those boundaries.

Change: validate dimensions and use widened checked clipping arithmetic; add extreme-coordinate/property cases and compare software/RTL rejection semantics. This audit did not run sanitizer-based reproduction of this issue.

### F18 — P2 — Launch failure can silently leave a dummy SDL game without transport output [code-confirmed]

Locations: `support/reference/mister_main.cpp:10–16`; `support/cmake/arm-transport.cmake:27–33`; `support/reference/mister_transport_sdl.hpp:42–49`.

The entry point chooses dummy video for any nonempty transport value, even `0` or `false`, while the adapter activates only for `1`/`true`. The injected initialization ignores the adapter's false result. A typo or failed mapping can leave the engine running with dummy video and no FPGA publication.

Change: share one strict configuration parser, fail visibly when explicitly requested transport cannot initialize, and propagate startup status to the launcher. Test disabled, malformed, missing mapping, bad attachment and startup-timeout cases.

## Open qualification blockers, distinct from newly reproduced bugs

- **Physical display/audio/controls:** the guide correctly keeps these open. Queue acknowledgements and dummy SDL do not establish visible pixels, audible channels or complete control workflows.
- **Audio health:** `.mister/evidence/arm-pcm-health-20260907.json` records active-run underruns increasing from 1,406 to 3,706 between samples. This is observed starvation in that historical build, not merely an untested gate. Later end-of-run counters mix playback and producer shutdown, so do not assign all of them to active gameplay. Require active-window deltas and priming/shutdown boundaries on the new candidate.
- **DDR/reset stress:** individual randomized consumer tests do not constitute an integrated shared-arbiter stress test. Strict priority and a pending read without a watchdog need bounded-service tests for input, audio, scanout, command and control, including relaunch under load.
- **Memory admission:** `TransportRuntime::Open` accepts a supplied physical address but does not establish that the range is reserved on the current boot or exclusively owned. Prior board preflight does not substitute for a production launcher admission/ownership check. The diagnostic DDR probe writes the transport header area and must not run concurrently with a game.
- **Full gameplay equality:** accepted reference evidence is useful but concentrated on town captures and selected replay scenarios. Deterministic accelerated dungeon, combat, UI/cursor restoration, automap, palette animation, cinematics and Hellfire coverage remains required.
- **Launcher/package:** a C++ entry point exists; the dedicated daemon-free MiSTer menu wrapper, installation contract, campaign data discovery, save/config isolation, core switching and clean-install evidence remain incomplete.
- **Multiplayer:** physical controller workflows, host/join, naming/chat, campaign compatibility and disconnect behavior have no accepted target qualification.
- **External timing:** the local report's positive constrained paths do not close the I2S/MCLK/I2C/storage/user-port work explicitly listed in `support/EXTERNAL_INTERFACES.md`. Review remaining active interfaces and exceptions against the final candidate, not just the earlier delay12 build.
- **Distribution provenance:** keep the already-required component notice/composition review and private-data exclusion gate. This audit does not provide a legal licensing opinion.

## Assessment of the current plan

`CORE_COMPLETION_AUDIT.md` is the current guide; the removed `.mister/DIABLO_IMPLEMENTATION_PLAN.md` should not be restored. The guide has good source-pinning, read-only data, exact-RBF hashing, independent-reference and physical-evidence rules. Its distinction between dummy-SDL preparation and real-board acceptance is especially useful.

However, the next sequence is now wrong for the observed code: repeating the current command build on a display would not resolve F01/F02 corruption, the scanout cadence ceiling or stranded slots. Steps 4/9/10 use broad “passes” language that must be narrowed to the tests actually performed. The README is substantially stale: it says no ARM adapter/shared ABI/accelerator exists and native-pattern work is next, although those implementations are present. The state mixes current decisions with old processes/builds and calls a prose paragraph `next_exact_command`.

Recommended plan changes:

1. Establish an immutable current candidate and distinguish historical board acceptance from current local artifacts.
2. Make command/full-copy correctness, palette atomicity and ownership recovery explicit blockers before acceleration qualification.
3. Prove one activation per refresh in integrated RTL before a real-vblank 60 FPS claim.
4. Close OSD, keyboard/text and audio-reset integration before physical workflow acceptance.
5. Introduce executable test tiers and exact evidence schemas; every stage has prerequisites, commands, measurable acceptance and remaining limitations.
6. Move minimal launcher/admission and installation skeleton work earlier so physical tests exercise the real lifecycle. Retain final clean-install/release acceptance at the end.
7. State whether 60 FPS is a hard release criterion or a performance milestone; distinguish simulation rate, presentation calls, successfully published frames and newly displayed frames.
8. Replace hardware “keep this file loaded” assumptions with hash-checked candidate selection. Preserve historical receipts rather than relabeling them as current success.

See `PROPOSED_PLAN.md` for the concrete execution order and `SUGGESTED_CHANGES.md` for the full prioritized work list. No production fixes were applied as part of this audit.

# Audit closure checklist — C01–C34

Unchecked items are not release-closed; several already have implemented local fixes. Use the current status in [the detailed plan](PROPOSED_PLAN.md), and start with [the execution guide](../../CORE_COMPLETION_AUDIT.md). Check an item only after its complete closure gate passes with matching evidence. References F01–F18 identify historical findings in `PROJECT_AUDIT.md`; [REFRESH_AUDIT.md](REFRESH_AUDIT.md) records current findings R01–R05. P1 blocks correctness/qualification; P2 is required for reproducible release; P3 improves maintainability.

## Mandatory refresh additions

- [ ] **R01 → C18/C25/C27/C29/C30:** replace the stale candidate with a verified source-matched rebuild; retain old receipts as historical.
- [ ] **R02 → C18/C21/C25/C29/C31/C32:** reject semantically failing evidence even when hashes and envelope labels match; enforce measured targets and a real candidate.
- [ ] **R03 → C18/C27/C28/C29:** isolate verification inputs and reject source/artifact mutation during a run before publishing acceptance evidence.
- [ ] **R04 → C16/C18/C26/C32:** deploy and validate a runtime-only package without a developer source/Git checkout.
- [ ] **R05 → C16/C17/C23/C24/C28/C29/C32:** implement the concrete menu/board adapter, current-boot admission and physical qualification records.

## Correctness and ownership

- [ ] **C01 / P1 / F01:** Fix the changed-run generation/index collision and validate previous-run x/index. Acceptance: the two-pixel reproduction and randomized source→command→renderer equality pass.
- [ ] **C02 / P1 / F02:** Unify or invalidate per-slot palette/pixel caches across command and full-copy writers. Acceptance: A→B→A palettes and mixed dirty-copy/command frames match every byte.
- [ ] **C03 / P1 / F03:** Pipeline scanout preparation between vblanks. Acceptance: one new frame per refresh after warm-up under a continuous producer and bounded DDR latency.
- [ ] **C04 / P1 / F04:** Define and implement safe retirement of superseded READY frames, or present FIFO. Acceptance: sustained producer overload never strands a slot or reuses an owned slot.
- [ ] **C05 / P1 / F05:** Commit framebuffer and palette together. Acceptance: deliberately alternating palettes/indices produce no mixed-frame RGB under backpressure.
- [ ] **C06 / P1 / F06:** Track outstanding command submissions across timeout, publish command faults and recover via a quiesced epoch transition. Acceptance: late fences and command errors recover without leaks or writes into recycled slots.
- [ ] **C07 / P1 / F07:** Synchronize live transport reset with the audio callback and invalidate/revalidate adapter caches on epoch changes. Acceptance: reset during callback/command/full-copy activity preserves memory safety and restores output.
- [ ] **C08 / P2 / F17:** Widen/validate rectangle clipping arithmetic and align malformed-record rejection semantics between software and FPGA. Acceptance: extreme signed-coordinate cases are deterministic and sanitizer-clean where supported.
- [ ] **C09 / P2:** Add integrated DDR arbitration/fault tests with bounded service deadlines, lost/delayed read responses and relaunch. Acceptance: no client stalls indefinitely and recovery is observable.

## Input, output and runtime

- [ ] **C10 / P1 / F08:** Transport actual `OSD_STATUS`; define focus gating and held-input reconciliation. Acceptance: OSD open/close cannot leave gameplay actions stuck.
- [ ] **C11 / P1 / F09:** Implement modifier state and the required text-entry path. Acceptance: naming, chat, Ctrl/Shift combinations and Ctrl+wheel work through transported input.
- [ ] **C12 / P2 / F10:** Correct mouse motion button masks and handle failed SDL queue publication with reconciliation. Acceptance: right/middle dragging, saturation and mixed keyboard/controller holds work consistently.
- [ ] **C13 / P1 / F11:** Implement or explicitly limit native analog/direct-video modes. Acceptance: every advertised output mode displays gameplay, with the diagnostic pattern clearly separated.
- [ ] **C14 / P1 / F18:** Use one strict transport configuration parser and propagate initialization failure. Acceptance: `0`/`false` retain normal behavior; requested but unavailable transport exits or displays a clear actionable failure.
- [ ] **C15 / P1:** Diagnose and eliminate active-playback PCM starvation on the candidate, with explicit priming/drain/shutdown accounting. Acceptance: zero active-window underrun delta in defined audio/gameplay stress tests and verified left/right speaker output.
- [ ] **C16 / P1:** Implement the minimal daemon-free MiSTer launcher lifecycle: data discovery, matching RBF/ARM selection, exclusive ownership, save/config paths, startup errors, quit, reset, core switch and relaunch. Acceptance: both campaigns launch through the intended menu workflow.
- [ ] **C17 / P1:** Make reserved-DDR admission boot-specific and enforce exclusive transport ownership before mapping. Acceptance: incompatible memory layouts, a second game instance and concurrent destructive probes are rejected before writes.

## Evidence and performance

- [ ] **C18 / P1 / F12:** Store immutable build manifests and artifacts; separate development and board-accepted builds. Acceptance: every referenced source/RBF/ARM/ABI/report hash resolves and matches before a validation claim is reused.
- [ ] **C19 / P1:** Add full accelerated-scene equality: town, dungeon, combat, automap, UI/cursor, palette effects, cinematics and Hellfire. Acceptance: completed target indices and palette match an independent reference; displayed RGB is separately checked.
- [ ] **C20 / P2 / F15:** Measure successful and failed/overflow command builds and waits, with fallback causes. Acceptance: stage totals reconcile with the complete presentation time.
- [ ] **C21 / P2 / F15:** Collect p50/p95/p99/p99.9, deadline misses, queue age, input-to-visible latency and service health. Acceptance: a repeatable paired software/accelerated benchmark reports distributions, workload/configuration and warm-up boundaries.
- [ ] **C22 / P2 / F16:** Label sampled CRCs distinctly and use complete readback only for correctness qualification. Acceptance: a changed unsampled pixel is detected by the qualification comparison.
- [ ] **C23 / P1:** Complete physical HDMI, real-vblank, peripherals, campaign/save-load, reset/core-switch, storage-error and long-duration tests on the accepted candidate. Acceptance: each advertised workflow has a receipt with exact artifact IDs and observation method.
- [ ] **C24 / P1:** Qualify controller-only workflows and multiplayer host/join/disconnect/chat for both campaigns. Acceptance: all required actions work under combined video/audio/network load.
- [ ] **C25 / P2:** Close active external-interface timing and reviewed exception coverage on the final RBF. Acceptance: no unreviewed active endpoint; all operating corners and supported output modes are covered.

## Build, documentation and release

- [ ] **C26 / P1 / F13:** Review/version the untracked implementation and intended test/documentation files; preserve private-data exclusions. Acceptance: a clean checkout contains the complete intended source and no private MPQs/saves/captures.
- [ ] **C27 / P2 / F14:** Remove the hardcoded external Quartus runner dependency or make it a pinned, explicit project dependency; implement clean complete snapshots. Acceptance: compile/timing/compress work from a fresh configured checkout.
- [ ] **C28 / P2:** Provide a single test entry point with explicit Python, host C++, RTL, ARM/QEMU and hardware tiers; parameterize toolchain/WSL paths and bound subprocess duration. Acceptance: missing prerequisites are reported per tier and timeouts fail clearly without hanging.
- [ ] **C29 / P2:** Make test/build receipts immutable and hash all dependencies, including included ABI headers and testbench inputs. Acceptance: changed inputs invalidate prior acceptance; skip-ARM runs cannot look like ARM success.
- [ ] **C30 / P2:** Update README and guide/state to the audited status; narrow broad pass claims and replace `next_exact_command` prose with executable commands or a clearly named action. Acceptance: one consistent current-candidate/status view, with historical evidence retained separately.
- [ ] **C31 / P2:** Adopt the revised dependency order, explicit stage acceptance, supported-output matrix and separate simulation/presentation/display-rate definitions. Decide whether 60 FPS is a mandatory release gate. Acceptance: every open gate has an objective completion condition.
- [ ] **C32 / P2:** Build a manifest-driven package and clean-install verifier, including component notices and explicit private-data exclusions. Acceptance: clean supported MiSTer install launches both campaigns, validates hashes, preserves saves and survives a second launch/core switch.
- [ ] **C33 / P3:** Move accidental/generated root files (`$null`, `a.out`, pin dumps) to ignored build/log locations after review; keep checked-in audit evidence separate from executables. Acceptance: intended-source status is readable and reproducible.
- [ ] **C34 / P3:** Remove stale “future consumer/slot zero” comments, duplicated adapter initialization and obsolete template/demo sources where unused; split the large SDL adapter by lifetime/ownership responsibilities. Acceptance: no functional change and existing tests remain green.

Follow the detailed plan's execution order: baseline/build/evidence infrastructure first, then rendering correctness, integrated ownership/recovery, runtime/I/O, target equality, physical/performance qualification and packaging. C26–C30 can proceed independently of physical hardware access. Further batching/caching/multicore optimizations must preserve the correctness and measurement gates. Writing this plan closes no implementation item.

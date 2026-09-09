# Diablo MiSTer FPS audit — 9 September 2026

## Follow-up: permanent affinity installed and verified

After the audit, the user authorized making affinity permanent. Candidate 098d98e6c084d52126aa30ad5806decc0fe8384b5f13b79d849551a00a3f7a01 is now installed and active. The launcher pins only its forked engine child to CPU 0 before exec; subsequently created audio threads inherit CPU 0. The launcher remains on CPU 1. This implementation relies on the launcher's existing single-threaded process model.

All 26 launcher/package tests passed, including real-process inheritance and failure-to-set-affinity tests. Target package verification passed. A fresh launch through the installed Scripts/Diablo.sh entry, deliberately started with CPU-1 affinity, produced game PID 4199 and audio TID 4204 on CPU 0 while launcher PID 4183 stayed on CPU 1. The engine and RBF hashes are unchanged from the previous release. The previous package is retained for rollback. Zoom was already restored to zero before this launch; lighting remains enabled.

The user briefly reported 22 FPS after restart. Inspection still showed correct affinity and 800 MHz. On the requested lighting-off/on recheck the user reported 43 FPS ON and 59.2+ OFF. The brief low reading's cause was not established; no other game fix was applied to explain it. Do not claim perfect worst-case frame time from these readings.

Deployment initially timed out over SMB while copying an inactive staging directory. Activation remained on the previous release. A bulk SSH transfer followed by the project's transactional installer on the target completed successfully. See affinity-install.json and affinity-fresh-launch.txt.

### Additional assessed optimization: remove redundant pitch division

Source/engine/render/light_render.hpp:33 calculates remainder and quotient to map a destination pointer to the lighting buffer. For nonnegative offsets with equal output and lightmap pitches, the result is algebraically just that offset. A guarded equal-pitch branch can remove division while retaining the old path for negative offsets and wall-bleed buffers with different pitches.

A standalone Cortex-A9 executable compared the arithmetic over 1,552,384 inputs spanning negative and positive offsets and four pitch pairs; all matched. Its four paired one-million-call runs on the live target measured original 217–238 ms versus guarded 37–51 ms. These results concern this isolated address routine with noinline calls, running alongside the game; they are not measurements of the inlined engine routine or an FPS prediction. The first dynamic benchmark build could not run against the target's older glibc; the recorded successful run used a static executable. Evidence and source: light-address-bench.txt and light-address-bench.c.

Updated implementation order: (1) affinity is complete; (2) assess the equal-pitch arithmetic branch in the real renderer with frame-level profiling and image equality; (3) uniform-lighting fast paths; (4) unchanged-lightmap caching; (5) native FPGA lit blits only if those are insufficient. No lighting or FPGA changes have been deployed. Maintaining the full view and per-pixel appearance is the acceptance requirement.

## Original audit result and recommendation

The largest demonstrated improvement is CPU affinity. The running game inherited CPU 1 from its launcher and competed with MiSTer's main thread on that same core, while CPU 0 was mostly idle. Moving both existing game threads to CPU 0 immediately improved the user's same-house test. No engine rebuild, RBF change, resolution change, or lighting-quality reduction was needed for this result.

| Full 640×480 view | Original affinity | Game threads on CPU 0 | Gain |
|---|---:|---:|---:|
| Per-pixel lighting OFF | about 39 FPS | about 59.7–60 FPS | about 53–54% |
| Per-pixel lighting ON | about 22 FPS | about 43 FPS | about 95% |

These are user-read on-screen FPS results, not an instrumented frame-time distribution. The later lighting-on value of 43 supersedes the ambiguous intermediate 59.7 reply. Zoom reached 60 FPS but the user rejected its reduced view as unplayable; it is excluded from the recommendation.

Priority: persist explicit game CPU placement; retain the full 640×480 view; implement and measure a correct uniform-lighting fast path; cache unchanged lighting work; then consider native FPGA rasterization if demanding scenes still miss 60 FPS. There is no evidence yet for a guaranteed 60 FPS with per-pixel lighting throughout the game.

## Live evidence

Active release: 082083dc76f53113f6fc8c6047dd1ecc74d0eb1781e25e093f4199a86d9f9113.
Engine SHA-256: dec3e6ed0cf78d2763899c2dd62dc03071c3cdab2ddaa156015740bd6fb0f051. This matches the local .work/build/arm-60fps-20260909/devilutionx binary.

The live configuration was 640×480, FPS display enabled, CPU frequency 800 MHz, governor performance, dummy SDL video/audio, software SDL renderer, indexed MiSTer transport enabled, and forced 60 Hz pacing enabled. COMMAND_SCENE and DIRTY_COPY were absent from the process environment.

Before the experiment:
- Launcher PID 3323: CPU 1.
- MiSTer main TID 3330: CPU 1; MiSTer worker TID 3331: CPU 0.
- Game main TID 3332 and audio TID 3337: CPU 1.
- Game main thread consumed about 43% of a CPU over a short sample, yet repeated wait-channel samples were zero, consistent with runnable CPU competition rather than a long intentional sleep. Aggregate samples showed CPU 1 saturated and CPU 0 mostly idle.

Experiment: taskset -pc 0 was applied to game TIDs 3332 and 3337 only. Subsequent /proc status confirmed both on CPU 0. MiSTer's affinity was unchanged. These PID-specific settings are temporary and will be lost when the game exits. No launcher or package files were edited.

With lighting on after the change, a five-second sample showed approximately 4.97 CPU seconds in the main game thread and 0.08 in audio: the rendering side is now close to saturating its assigned CPU. This supports CPU optimization as the next target; it does not identify an individual hot function.

Saved evidence: live-initial.txt, affinity-trial.txt, lighting-on-affinity.txt. The copied deployed-build-dx.cpp is an inspection snapshot of the local cached build overlay, not a new implementation.

## Ranked work

### 1. Persist CPU placement — proven, highest priority

The launcher starts the engine without assigning affinity (support/scripts/mister_launcher.py:476). A child inherits its parent's allowed CPUs; start_new_session does not provide CPU isolation. The observed launcher and game masks explain how the collision occurs.

Assign the engine to CPU 0 before it creates its audio/loading threads, while preserving MiSTer's main thread on CPU 1. Set affinity in the engine startup or a child-only launch wrapper; avoid changing the whole launcher's mask before it starts MiSTer. Retain a capability-checked fallback on other hosts. Do not persist hardcoded process IDs. Verify the actual masks after launch and audio-thread creation. This is core separation between the two main workloads, not complete isolation from kernel interrupts or MiSTer's worker.

Do not try to obtain the same result by increasing game priority on the shared busy core: that competes with input/service work. The successful experiment already demonstrates a better placement.

### 2. Uniform-lighting fast paths — strongest next software candidate

Source evidence:
- .work/sources/devilutionx/Source/levels/gendung.cpp:303 initializes town dLight to zero (fully lit).
- Source/engine/render/scrollrt.cpp:1275 builds the lightmap on every DrawGame invocation when the option is on.
- Source/engine/render/light_render.cpp:431 clears and reconstructs an expanded lightmap; :521 calls it whenever per-pixel lighting is enabled.
- Source/engine/render/scrollrt.cpp:610 requests wall-light bleed buffers; light_render.cpp:527 performs the corresponding copying when enabled.
- Source/engine/render/dun_render.cpp:965, :979 and :993 select the per-pixel variant before the existing fully-lit/fully-dark fast paths.
- Source/engine/render/blit_impl.hpp:68–84 performs per-pixel lightmap reads and palette-light table lookups, even for constant-color fill runs.

Implement a lighting classification for the actual sampled region: uniform fully lit, uniform dark, uniform intermediate, or varying. Fully-lit regions can use the existing direct rendering path after verifying equivalent table semantics; constant intermediate regions use a single translation table, and constant-color runs can map once then fill. Bypass lightmap construction/bleed only when all consumers have a correct constant-light representation.

Do not merely reorder the dispatch to trust one tile's light table: neighboring light levels may create a gradient. Town initialization is a strong opportunity, not proof that every town pixel and every later state is uniform. Preserve out-of-bounds behavior, foliage, transparency, sprites, special translations and wall lighting. Compare indexed images byte-for-byte with the current per-pixel renderer, including town edges and dungeon transitions.

At 43 FPS the interval is 23.256 ms. Reaching 60 requires removing 6.589 ms, or about 28.3% of that interval. This is a target, not a predicted gain from this optimization.

### 3. Cache unchanged lightmaps and wall-light data

BuildLightmap currently reconstructs its buffer each rendered frame. The stationary-house case is favorable for reuse. Introduce an explicit lighting generation/version and cache only while tile light values, camera/subtile offset, viewport dimensions, tile geometry/microtile length, level and other inputs are unchanged. Reuse wall-light computations under equivalent keys. Invalidate on moving light sources, missiles, monsters, camera motion, resolution/zoom changes and level changes.

Keep world lighting data separate from screen placement where that reduces invalidation cost. Avoid hashing or comparing a full lightmap every frame if a small dirty/version mechanism can describe the changes. Measure this separately from the uniform-light fast path so the same saved work is not counted twice.

### 4. Reduce repeated ARM rasterization and transport work

Consider cached static tile layers, decoded sprite data, or translated opaque tiles only after profiling. A stationary town is favorable, but doors, actors, occlusion and transparency require correct draw order and invalidation. A complete cached final frame is not safe while actors or UI animate.

The current transport accepts a CPU-rendered indexed surface. A packed 640×480 frame is 307,200 bytes; at 60 FPS its one-way payload is 18.432 MB/s before copies, scanout, palette, overdraw and arbitration. Transfer cost can still matter on an uncached mapping even when nominal DDR bandwidth is much higher. Preserve cached ARM rendering plus bounded burst publication unless measurement proves a better arrangement; directly rendering through an uncached FPGA-facing mapping could make small pixel writes slower.

Historical, different-build September 7 results are useful leads, not current measurements: indexed publish averaged 4.882 ms in one run; dirty copy reduced average publish from 4.413 to 3.432 ms and timedemo FPS from 28.3 to 29.3. Re-run on the corrected affinity before adopting it. Shadow comparison and stale-slot bookkeeping can outweigh transfer savings in moving scenes.

### 5. FPGA acceleration — native lit blits, not framebuffer-to-rectangles

The current command path is not a native Diablo GPU. support/reference/mister_command_scene.hpp:13 builds changed-color rectangles by scanning an already rendered CPU image. support/reference/mister_transport_sdl.hpp:187 calls it during Present, after the renderer's work. rtl/diablo_command_consumer.sv:77–79 implements Fill, Copy and End; it does not implement lit sprite decoding. Therefore merely enabling COMMAND_SCENE cannot remove lightmap generation or per-pixel shading from the ARM. Historical command-building measurements also included roughly 5 ms of ARM batch-building work and additional wait time.

The most useful substantial FPGA direction is an ordered native blitter: cached sprite/tile assets, clipped spans or native RLE/CLX commands, color-key/mask handling, a BRAM light-table lookup, optional lightmap input, and exact transparency translation. Emit commands where the engine currently rasterizes so the corresponding ARM pixel loops are skipped. Burst asset reads and framebuffer writes; batch commands; use frame-level ownership/fences rather than waiting after every sprite. Retain a whole-pass/frame fallback with explicit ownership.

Start with one independently comparable lit opaque tile/sprite operation, then measure end-to-end frame time including command production and DDR contention. Add blending and wall-light behavior only with image-equality coverage. A separate lightmap generator is another option, but uploading a CPU-built lightmap every frame still leaves its construction on ARM.

A full-screen final lighting pass is not automatically equivalent: UI, already lit pixels, special translations, foreground/background lighting and transparency can require different operations or ordering. It needs a representation that preserves those semantics. Avoid a naive shade-every-final-pixel design.

Local output_files/Diablo.fit.summary (September 7 build, NOT verified as the active RBF) reports 11,248/41,910 ALMs, 429,313/5,662,720 memory bits and 37/112 DSP blocks. This suggests substantial room for exploration, but is not resource/timing proof for a new accelerator or the deployed candidate. Lighting tables are suitable for block RAM; keep large assets/framebuffers in DDR with a measured cache/burst design. Re-fit and check timing, arbitration, video and audio after architecture changes.

### 6. Lower-priority work

The inspected cached ARM build is already Release, Cortex-A9/NEON hard-float, -O3, with LTO flags present. Recommending merely enabling optimization or NEON is not a new win. Consider profile-guided optimization only after the main algorithmic work; training must include menus, town and busy dungeon combat. Explicit SIMD may help contiguous copies/fills and lighting generation, but arbitrary per-pixel palette table lookups are not automatically cheap vector operations. Measure generated code and use uniform runs where possible.

Gameplay AI, save data and storage are low-priority targets for the stationary-scene symptom. Moving game logic wholesale to the FPGA has much greater implementation and compatibility cost than accelerating pixel work. More worker threads are not automatically beneficial: the other main CPU already services MiSTer. Audio's measured CPU time is small compared with the saturated renderer.

## Configuration decisions

- Keep full 640×480, zoom off for the recommended result. The user rejected the zoom tradeoff even though it reached 60 FPS with lighting.
- Lighting off already achieves about 60 FPS after affinity correction. Lighting on remains the optimization target.
- CPU performance governor and 800 MHz are already active; no gain from reselecting them.
- Keep the single forced 60 Hz pacer. The inspected overlay uses PaceFrame OR LimitFrameRate, not both on successful transport presents. Removing the cap will not create useful extra displayed frames in a 60 Hz pipeline and can increase ring pressure. Measure deadline behavior and unique displayed frames rather than optimizing an uncapped FPS number.
- Lowering HDMI output resolution or changing SDL scaling is not equivalent to reducing internal rasterization. The adapter checks for at least the fixed 640×480 indexed surface (mister_transport_sdl.hpp:167–169); changing the INI to a smaller buffer is not a supported free win.
- Leave command-scene off. Dirty-copy is enabled by the current launcher after the paired candidate benchmark; retain the explicit `DIABLO_MISTER_DIRTY_COPY=0` rollback override and continue real-vblank/scene qualification.

## Proof needed before claiming completion

First ship/test explicit affinity through a fresh normal A-button launch, verifying all relevant thread masks. Benchmark full-view lighting off/on with matched camera/save state and warm-up. Instrument render, lightmap build, wall bleed, tile/sprite rasterization, transport publish and wait time separately. Record median/p95/p99 and unique FPGA-displayed frame cadence, not just the FPS overlay. Account for profiler overhead.

For each lighting/cache change compare exact indexed pixels and palettes against the original per-pixel path. Cover stationary town, town edges, walking/scrolling, dungeons with moving lights and combat, menus/UI, Diablo and Hellfire. Ensure hardware input and audio remain healthy; existing engine logs contain accumulated PCM underruns, so this FPS result does not certify audio behavior.

Use a 16.667 ms display interval as the target and seek additional headroom, not a result that only barely holds 60 in this stationary scene. If uniform lighting and caching achieve the target with correctness, stop before a larger FPGA rewrite. If busy-scene profiles still show lit rasterization dominating, proceed with the native blitter using those profiles as its acceptance budget.

## Scope of the initial audit (before the permanent follow-up)

Completed live configuration/affinity inspection, temporary affinity A/B experiment with user FPS readings, code-path audit, review of historical profiling receipts, and resource-summary inspection. No permanent product changes or RBF builds were made. The temporary CPU-0 setting remains on the running game. Function-level costs and the FPS gains of proposed lighting/FPGA changes remain unmeasured; no finite audit can prove an absolute maximum over every possible redesign.

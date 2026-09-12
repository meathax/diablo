# Diablo MiSTer performance improvement report
Date: 12 September 2026  
Scope: report only; local source, existing board evidence, and FPGA resource reports. No implementation, build, deployment, settings changes, or new hardware benchmark was performed.

## Recommendation

**For the largest long-term improvement with full-view, per-pixel lighting, implement a native FPGA tile/sprite blitter that replaces ARM rasterization. For the best next step, qualify and benchmark the three lighting optimizations already staged in this repository. Then address the expensive ARM-to-shared-memory publication path.**

The evidence supports these priorities, but does not establish a precise FPS forecast for unimplemented features. The ranking below orders engineering potential; adjacent unmeasured items can change places after profiling. Settings alternatives and overlapping optimizations must not be added together.

The useful goal is **sustained 60 unique displayed frames/second in demanding gameplay, with lighting enabled**, plus headroom for combat, audio and input. Increasing an uncapped counter beyond the display cadence is not equivalent to improving visible performance.

## What is known

| Evidence | Result | Meaning |
|---|---|---|
| Earlier same-house, full-view affinity comparison; lighting off | About 39 → 59.7–60 FPS | Approximately 53% gain from avoiding competition with MiSTer's main thread. Already implemented in the launcher. |
| Same comparison; lighting on | About 22 → 43 FPS | Approximately 95% gain. These were user-read overlays, not frame-time distributions. |
| Lighting on versus off after affinity correction | About 43 versus 59.2–59.7 FPS | Lighting is a major quality-dependent cost in that scene. Disabling it was roughly a 39% FPS improvement. |
| Candidate 231b07 dirty-copy A/B, 45 seconds each | 2,497 → 2,566 frames; average publish 7.707 → 5.989 ms | 1.718 ms less publication time, but only 2.8% more frames. Dirty copy is already the launcher default. |
| Later candidate 959c31 long profile | 57.9691 Hz over 70.641 seconds; average publish 5.433 ms; zero recorded transport drops | Near-60 averages do not prove sustained 60 Hz. Publication remains material. |
| Same candidate, CPU pacing disabled | Accepted cadence about 58.9 Hz; 1,973 backpressure drops | Removing the limiter is not the demonstrated remedy. |
| Shared-aperture copy microbenchmark | libc memcpy about 93.52 MiB/s; explicit NEON about 80.81 MiB/s | A full 307,200-byte frame takes about 3.13 ms of raw copy time under that benchmark. Handwritten NEON was slower. |
| FPGA command-scene prototype | Historical short timedemos around 10.8–12.1 FPS | Proof of command execution, not evidence of acceleration over the current default. Different historical conditions prevent a direct current-candidate comparison. |

Sources: [prior FPS audit](../reports/fps-audit-2026-09-09/AUDIT.md), [FPS results](../reports/fps-audit-2026-09-09/results.json), [dirty-copy receipt](../.mister/evidence/receipts/20260910T-arm-pacing-dirty-copy-active-smoke.json), [pacer A/B](../.mister/evidence/receipts/20260910T-arm-pacing-dirty-copy-no-cpu-ab.json), [progress evidence](../PROGRESS.md), [copy benchmark](../.mister/evidence/arm-shared-ddr-copy-benchmark-20260907.json), [command experiment](../.mister/evidence/arm-command-scene-optimization-20260907.json).

These measurements belong to different dated candidates and scenarios. They are not one additive profile of today's working tree. The working tree also contains existing uncommitted frontend, launcher, build and package changes; the board's current running identity was not checked for this report.

## Ranked improvements: largest potential first

| Rank | Implement or select | Potential and confidence | Cost / qualification |
|---|---|---|---|
| 1 | Native FPGA tile/sprite rasterizer with lighting and cached assets | Largest architectural ceiling: remove substantial ARM rendering and potentially final frame-copy work. No measured end-to-end gain yet. | Very high; new renderer and transport integration. |
| 2 | Per-pixel lighting OFF, keeping full 640×480 view | Largest demonstrated remaining quality tradeoff: about 43 → 59.7 FPS in the recorded scene. Already the documented default, so no gain if already off. | Immediate setting; changes lighting appearance. |
| 3 | Qualify staged ARM lighting fast paths and cache | Best next engineering investment for retaining quality. Targets the measured lighting penalty; actual savings unknown. | Moderate; source already staged, opt-in OFF. |
| 4 | DMA / properly managed shared render buffers | Removes or overlaps part of the measured 5.4–6 ms publication stage. Raw full-copy component was about 3.13 ms in an earlier benchmark. | High; memory allocation, coherency, ownership and RTL/driver work. |
| 5 | Improve adaptive dirty transfer and checksum traversal | Incremental improvement within publication; strongest in sparse-change scenes, less during scrolling. | Low–moderate; build on existing dirty-copy implementation. |
| 6 | Use the second ARM core selectively | Potentially meaningful if independent CPU work dominates; no evidence for a twofold gain. | Moderate–high; CPU 1 already serves MiSTer. |
| 7 | Improve presentation handoff / DDR service where measured | Likely small average-FPS benefit near 58 Hz, potentially important for judder and worst-frame latency. | Moderate; inspect actual missed commits before changing RTL. |
| 8 | Profile-guided builds and targeted hot-loop optimization | Secondary gains after removing unnecessary work. No measured prediction. | Low–moderate; representative profiles and image checks. |
| 9 | Audio decode/resampling and asset-I/O optimization | Usually improves spikes, audio reliability or loading; average-FPS benefit requires a demonstrated hotspot. | Variable; FPGA audio mixing is a later option. |

Ranks 2 and 3 are alternative ways to address lighting. Ranks 1, 3, 4 and 5 overlap. Rank 1 is the greatest potential redesign, not the recommended first experiment.

### 1. Build a native FPGA renderer, not a finished-frame compressor

Today, the ARM engine produces a complete indexed SDL surface. The optional command path then compares that finished image with a shadow and converts changed same-colour runs into FillRect commands. **The ARM has already paid for drawing and lighting every affected pixel.** Command reconstruction adds another scan, command construction, submission and completion handling.

The existing FPGA consumer supports FillRect, CopyRect and End. FillRect already uses packed 64-bit writes and bounded bursts; CopyRect remains byte-granular. This is useful infrastructure, but it is not a native Diablo sprite accelerator.

Implement:

1. Hook engine tile/sprite drawing before pixel loops execute. Emit ordered draw descriptors and skip the corresponding ARM rasterization.
2. Keep frequently used sprite/tile data resident in a bounded FPGA-accessible DDR asset cache. Upload on asset or level changes, not once per draw.
3. Start with common opaque and lit spans: clipping, source/destination pitch, transparency masks and palette-index output. Add native CLX/RLE decoding only where it beats predecoded cached spans.
4. Put light translation tables in BRAM and reproduce exact translation/transparency order. Per-pixel lighting also needs the correct lightmap or equivalent exact lighting computation; a constant palette lookup alone does not reproduce it.
5. Batch reads and writes through line buffers. Blend/masked writes may require destination reads; budget these explicitly.
6. Submit whole passes or frames asynchronously, with bounded queues and frame-level fences. Avoid waiting for every sprite.
7. Preserve ordering for walls, entities, effects, cursor and UI. Use a clean whole-pass/frame fallback; mixed CPU/FPGA writers must never race over the same slot.

**Expected outcome:** the strongest route to substantially faster lighting-on gameplay and more headroom in busy scenes. It can eliminate work rather than merely move an already-rendered picture. A guaranteed 2× FPS claim would be unsupported until the renderer's share of frame time and accelerator throughput are measured.

**FPGA feasibility:** the 11 September fitter summary reports 27% ALMs, 16% block-memory bits and 33% DSP use. There is resource headroom, but not unlimited local storage: about 592,800 block-memory bytes remain by arithmetic, less than two 640×480 indexed frames (614,400 bytes), before allocation overhead. Keep full frames/assets primarily in DDR and use BRAM for tables, FIFOs and line caches. The tight reported setup slack also argues for pipelining rather than simply raising clocks.

Sources: [SDL adapter](../support/reference/mister_transport_sdl.hpp), [changed-run builder](../support/reference/mister_command_scene.hpp), [command consumer](../rtl/diablo_command_consumer.sv), [fitter report](../output_files/Diablo.fit.summary), [timing summary](../output_files/Diablo.sta.summary).

### 2. Use per-pixel lighting OFF as the immediate performance preset

Keep the full 640×480 view and disable per-pixel lighting if performance takes priority over its appearance. The recorded 43 → 59.7 FPS comparison is stronger evidence than any speculative optimization estimate.

This is already the documented default. Treat it as a reliable performance mode and fallback, not as a new improvement for a user already running it.

Do not recommend zoom as the main solution: the previous audit records that the user rejected the reduced view despite reaching 60 FPS. A lower HDMI output resolution does not automatically reduce the engine's internal rasterization. The current adapter expects at least a fixed 640×480 indexed surface; a smaller internal render target would require explicit implementation and UI/viewport validation.

Source: [recorded settings and user observations](../reports/fps-audit-2026-09-09/AUDIT.md).

### 3. Finish the staged lighting optimization before commissioning a large renderer rewrite

The repository already contains three implementations behind **DIABLO_MISTER_LIGHTING_OPTIMIZATIONS**, default OFF:

- **Equal-pitch address shortcut:** avoid quotient/remainder work when output and lightmap pitches match and the offset is nonnegative. Preserve the original negative-offset and different-pitch wall-bleed behavior.
- **Uniform-light fast paths:** use a constant translation table, or a verified identity copy, where generated lightmap pixels are uniform. Include clipping/borders; do not assume a room is uniformly lit from one tile.
- **Exact-input lightmap cache:** reuse lighting output only when all relevant inputs match. The staged design compares input state; measure comparison cost and hit rate while walking and in combat.

The status receipt says these were prepared but not compiled, tested or deployed. The current CMake option remains OFF. Do not present them as completed performance gains.

Recommended implementation work is to review and qualify these existing changes individually, then enable the winning combination. Establish exact pixel/palette equivalence for both campaigns, walls and dark boundaries, moving lights, scrolling, transitions and UI. Stationary-town cache hits cannot justify a general gameplay FPS claim.

At 43 FPS the nominal frame interval is 23.26 ms. Reaching 60 requires saving approximately **6.59 ms/frame**. This is the target budget, not a measured duration of any one lighting function. A tiny isolated address benchmark does not establish the whole renderer's improvement.

Sources: [option/integration](../support/cmake/mister-lighting.cmake), [staging status](../reports/fps-audit-2026-09-09/lighting-implementation-status.json), [address fast path](../support/reference/lighting/engine/render/light_render.hpp), [lightmap implementation](../support/reference/lighting/engine/render/light_render.cpp).

### 4. Replace CPU writes to the shared aperture with a deliberate transfer architecture

The publication path is large enough to merit architectural work. However, DMA will not eliminate every part of its 5.4–6 ms cost.

Implement one measured prototype first:

- Keep ARM rendering in cached RAM, then DMA completed rows/blocks into an owned shared framebuffer; overlap transfer with independent work.
- Alternatively, allocate render buffers through a suitable kernel-managed DMA interface and let scanout consume completed buffers directly, eliminating the final copy where the existing memory path and addressability permit it.

Explicitly define ownership, physical/DMA addresses, pitch, cache maintenance, descriptor ordering, palette pairing, cancellation and reset. Keep metadata synchronization separate from bulk pixel storage. A coherent mapping is not automatically the fastest CPU raster target.

Cyclone V provides FPGA/HPS communication and ACP coherency facilities, but using ACP here is a design option requiring integration, not a property of the current /dev/mem path. Intel describes the relevant mechanisms in [AN 796](https://cdrdv2-public.intel.com/666598/an-cv-av-soc-ddg-683360-666598.pdf) and the [HPS–FPGA interface reference](https://www.intel.com/content/www/us/en/docs/programmable/683126/21-2/hps-fpga-memory-mapped-interfaces.html).

Do not merely remove O_SYNC or substitute a NEON copy: both were already tested without improvement. Do not render directly into the existing uncached aperture as an assumed shortcut; many small read/modify/write operations can be worse than a cached render plus bulk copy.

A 60 Hz stream of raw indexed frames is only about 17.58 MiB/s one-way. That does not include scanout, assets, lightmaps or overdraw. The practical issue is critical-path transfer cost and contention, not proof that physical DDR capacity is exhausted.

### 5. Make dirty transfer adaptive at block/frame level

Keep the existing dirty-copy default. It already keeps per-slot shadows, skips equal rows and falls back to copying a full row after more than 64 changed pixels.

Improve it by measuring changed area and transaction count, then choosing among coarse blocks, row copies and full-frame copies. Coalesce nearby changes when copying a few unchanged bytes costs less than many tiny writes. During scrolling, take the full-copy route early rather than perform an expensive fine-grained scan first.

If native dirty-region tracking is introduced, preserve the age of each of the three destination slots: a slot may be several frames behind. Camera motion, palette changes, UI restoration, reset and mixed-writer transitions require correct invalidation.

The sampled CRC routine also loops over every column and updates only every sixteenth pixel. A separate strided sampled loop is a small candidate, subject to checking generated code and measured cost. Full CRC is already opt-in; “disable full-frame CRC” is not a new default-path optimization.

Avoid spending weeks here if DMA or a native renderer will replace this path. The published 1.718 ms dirty-copy saving produced only a 2.8% frame-count gain in its particular A/B.

Source: [publisher and checksum](../support/reference/mister_transport.hpp).

### 6. Use both ARM cores only for work that can overlap safely

The large affinity fix is already implemented: the engine child is pinned to CPU 0, avoiding the MiSTer frontend on CPU 1. Do not undo it by blindly allowing all game threads onto both CPUs.

Candidates include audio decode/resampling, bounded asset preprocessing, or a worker operating on an immutable lighting snapshot. Benchmark individually. Keep gameplay simulation and ordering-sensitive renderer state under clear ownership. Respect CPU 1's frontend and input service needs.

This can reduce frame spikes, but a second worker that shares the same DDR bottleneck or delays MiSTer may reduce visible performance.

Source: [launcher CPU placement](../support/scripts/mister_launcher.py), [affinity evidence](../reports/fps-audit-2026-09-09/AUDIT.md).

### 7. Fix missed presentation deadlines, not just the FPS counter

Measure the chain from ARM frame readiness through ownership acceptance, palette preparation, vblank commit and actual displayed frame ID.

Only then change polling intervals, descriptor prefetch, arbitration or queue policy. Protect scanout and PCM deadlines while keeping command bursts bounded. More queued frames may hide producer jitter while increasing input latency; queue depth is not a free FPS improvement.

The current evidence puts the no-pacer accepted cadence around 58.9 Hz. It does not prove whether every remaining missed display opportunity is due to CPU work, polling, preparation or handoff. Do not blame a particular RTL block without timestamps.

Retain one pacing authority. Preserve fixed simulation timing and interpolation; changing game speed is not a rendering optimization.

### 8. Tune generated ARM code after the larger costs

The toolchain already selects Cortex-A9, NEON and hard-float. Verify actual release flags and linked hot objects, then evaluate LTO and profile-guided optimization using representative gameplay.

Prioritize measured tile/sprite loops, lightmap work and cached-memory comparisons. Avoid unsafe math/aliasing changes and indiscriminate SIMD rewrites. The existing NEON copy result is a concrete warning that more explicit vector instructions do not guarantee faster device-memory access.

### 9. Optimize audio and I/O when their traces justify it

FPGA PCM playback already exists; audio mixing/decoding still occurs on ARM. First measure codec, resampler and mixing time. Predecode frequently reused short sounds and avoid redundant format conversion where memory permits.

A future FPGA voice mixer could accept per-voice sample descriptors, gains and rates, but it needs more asset/control transport and deterministic service. It ranks below rendering and frame transfer on current evidence.

Asset prefetch and selective caching can reduce loading or first-use stalls. Faster storage, lower audio quality or disabling music should not be sold as major average-FPS fixes without a matched gameplay measurement.

## What to implement first

1. **Record a current matched baseline**, with lighting on/off, fixed full view and the same save/camera. Confirm the deployed identity and existing affinity/dirty-copy settings.
2. **Qualify the staged lighting changes separately.** They target a demonstrated quality-dependent deficit and already have source prepared.
3. **Split publication timing into comparison, copy, checksum, metadata and wait.** Improve the dominant part; prototype DMA if bulk transfer remains expensive.
4. **Proceed to the native FPGA blitter if worst-case lighting-on gameplay still misses budget.** Start with the highest-cost primitive mix, not an entire game-logic rewrite.
5. **Retain only improvements that survive scrolling/combat with correct images, healthy audio and responsive input.**

Do not move AI, pathfinding, inventory logic, networking or the entire engine into FPGA first. There is no evidence these dominate the measured deficit, and their irregular control flow makes them much larger projects than accelerating pixel operations.

## How to interpret prospective gains

These are arithmetic examples using the historical 43 FPS case, not predictions:

| Net critical-path saving | Implied uncapped rate | In a 60 Hz presentation path |
|---|---:|---|
| 2 ms/frame | 47.0 FPS | Still below target |
| 4 ms/frame | 51.9 FPS | Still below target |
| 6.59 ms/frame | 60.0 FPS | Reaches target with little margin |
| 8 ms/frame | 65.5 FPS | About 60 displayed FPS plus headroom |

Use net time saved after command building, cache maintenance, synchronization and fallback. Gains cannot be summed when they remove the same work or move the bottleneck.

Acceptance should include warmed stationary town, continuous scrolling, a dark dungeon with moving lights, dense combat/effects, and both campaigns. Record CPU stage times and p95/p99 frame intervals alongside unique displayed frames, repeat/stall counts, input latency and PCM health. Compare exact indexed output/palettes for visual-preserving changes. Repeat matched runs rather than treating a title screen, a short FPS overlay or a transport-accepted frame count as final proof.

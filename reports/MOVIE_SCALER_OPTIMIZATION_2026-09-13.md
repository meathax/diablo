# Movie scaler coordinate cache

Implemented persistent fixed-size X/Y coordinate tables in IndexedFrameAdapter. Tables use the original 64-bit center-of-pixel formula, refreshing only when source or destination dimensions change. The pixel loop now uses table lookups. The native 640×480 bypass, palette handling, border clearing and locking remain intact; direct oversized calls keep the original mapping fallback. Tables occupy approximately 4.5 KB per adapter and allocate no heap memory.

## Measured result

Three paired MiSTer ARM runs, 60 calls per implementation per pair, pinned to CPU 0, CLOCK_THREAD_CPUTIME_ID timing. Same indexed 320×156 source scaled into the centered 640×480 destination.

- Original average CPU time: 49.537 ms/frame.
- Cached average CPU time: 3.637 ms/frame.
- Speedup: 13.62×; CPU cost reduction: 92.66%.
- Full output buffers were byte-identical.

These are scaling-stage CPU measurements, not whole-game frame time or a promised gameplay FPS gain. Warm cache was measured; the first frame still builds the tables. The initial wall-clock benchmark was noisy due to scheduling, so CPU time was used for the reported comparison.

## Validation and artifact

The cinematic regression compiled with warnings as errors and passed, including full-frame checks across 10 source geometries/repeats, source-dimension changes at the same aspect ratio, portrait and odd dimensions, palette/letterbox behavior, transport backpressure, and the generated cinematic hook. git diff --check passed.

The game executable was rebuilt by compiling the affected cinematic translation unit and linking against the existing matching engine objects, retaining an unstripped companion. An existing external fmt-header warning was emitted in the engine build.

Built binary: [devilutionx](../.work/build/movie-coordinate-cache/devilutionx). It has not replaced the installed game. No full-game playback qualification was performed for this candidate.

[Measurements and binary SHA-256](movie-coordinate-cache-2026-09-13.json).

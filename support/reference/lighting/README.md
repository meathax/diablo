# MiSTer lighting overlay

Status: implemented source; the focused differential suite passes in normal and ASan builds. Full target/gameplay validation remains pending.

These three files derive from the pinned DevilutionX renderer (engine license: support/licenses/devilutionx-LICENSE.md). upstream.json binds their original source bytes. The engine checkout is unchanged. CMake rejects a changed upstream and supplies this header directory to every engine consumer so class layouts agree.

The MiSTer transport recipe enables this overlay by default when the pinned renderer provides all three inputs. Older checkouts without the per-pixel renderer skip it with a configure STATUS message. Override with -DDIABLO_MISTER_LIGHTING_OPTIMIZATIONS=OFF when needed. Do not deploy this source as fully validated until the full gameplay checks pass.

Implemented:
1. getLightingAt returns the offset directly for nonnegative equal-pitch inputs; original negative and different-pitch behavior remains.
2. Generated lightmaps are classified for uniform lighting after reconstruction. Uniform blits use one translation table; byte copies and identity-table blended copies use direct paths only after the table is verified to be identity. Wall-light copying is skipped only for a globally uniform lightmap. Blend lookup operand order is preserved.
3. Reuse the generated lightmap when all geometry inputs and the entire tile-light array are unchanged. A small exact comparison avoids missed invalidations from any light producer; LUTs/output addresses do not affect generated light levels and are rebound each call. Cached uniformity is also reused. No per-frame allocator growth after warm-up.

Focused verification:
- support/tests/run_lighting_optimization_test.py --engine .work/sources/lighting-test-source --allow-build passes under WSL, including cache hits/invalidations, generated lighting, clipping/bleed, table changes, direct and blended pixels.
- The same command with --sanitize also passes under WSL.

Pending full verification:
- Build the ARM game with the option ON, using the agreed audio baseline.
- Compare full frames/palettes while stationary, walking, changing lights, using menus, and transitioning between levels in Diablo/Hellfire.
- Measure full-view 640x480 lighting-on FPS against 43 FPS and ensure CPU affinity remains on CPU 0.

No claimed FPS improvement until measured in the complete engine.

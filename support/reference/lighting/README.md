# MiSTer lighting overlay

Status: implemented source, NOT compiled or tested yet. The user explicitly paused all builds pending further authorization.

These three files derive from the pinned DevilutionX renderer (engine license: support/licenses/devilutionx-LICENSE.md). upstream.json binds their original source bytes. The engine checkout is unchanged. CMake rejects a changed upstream and supplies this header directory to every engine consumer so class layouts agree.

Enable explicitly with -DDIABLO_MISTER_LIGHTING_OPTIMIZATIONS=ON only after build authorization. The default is OFF, including the other task's audio build. Do not deploy this source as validated until the differential tests and full gameplay checks pass.

Implemented:
1. getLightingAt returns the offset directly for nonnegative equal-pitch inputs; original negative and different-pitch behavior remains.
2. Generated lightmaps are classified for uniform lighting after reconstruction. Uniform blits use one translation table; byte copies are used only after the table is verified to be identity. Wall-light copying is skipped only for a globally uniform lightmap. Blend lookup operand order is preserved.
3. Reuse the generated lightmap when all geometry inputs and the entire tile-light array are unchanged. A small exact comparison avoids missed invalidations from any light producer; LUTs/output addresses do not affect generated light levels and are rebound each call. Cached uniformity is also reused. No per-frame allocator growth after warm-up.

Pending verification after authorization:
- Run support/tests/run_lighting_optimization_test.py --allow-build under Linux/WSL. It compiles original and optimized renderers into the same differential test and checks cache hits/invalidations, generated lighting, clipping/bleed, table changes, direct and blended pixels.
- Build the ARM game with the option ON, using the agreed audio baseline.
- Compare full frames/palettes while stationary, walking, changing lights, using menus, and transitioning between levels in Diablo/Hellfire.
- Measure full-view 640x480 lighting-on FPS against 43 FPS and ensure CPU affinity remains on CPU 0.

No claimed FPS improvement until measured in the complete engine.

# Windows host reference

Native-resolution validation without Computer Use is implemented by
`python support/scripts/scenario_host.py diablo` and the equivalent `hellfire`
command. Each run owns a fresh ignored runtime directory. The explicit
`DIABLO_NATIVE_SCENARIO=town-v1` host hook calls the engine's hero creation API,
uses a fixed seed, and runs 512 replay ticks at 640×480. Inventory and character
panels use normal replay events. The ending check requires a live town player,
then writes a full save through the engine. SDL dummy drivers keep engine drawing
enabled; timedemo and capture disk writes make these runs unsuitable for FPS claims.

Compare two successful runs of the same campaign with
`python support/scripts/compare_frames.py <first-run>/frames <second-run>/frames`.
The comparator checks frame/tick metadata, every supplied pixel index, and all
RGB888 palette entries. Captures sample every 128 draws. A passing town scenario
does not establish dungeon coverage, campaign completion, physical audio/display
behavior, or MiSTer performance. Generated host overlays preserve the pinned
engine checkout; ordinary runs leave the scenario hook dormant.

Hellfire launchers stage the build's bundled `mods/hf` beneath the isolated save
directory, where this engine's mod loader looks when `--data-dir` points at the
private MPQs. The `--hellfire` flag and expansion MPQs alone can otherwise leave
the engine in Diablo mode. Scenario acceptance checks the engine's actual campaign
flag. The ordinary launcher preserves existing mod files and refuses conflicting
contents; neither launcher changes `game/`.

Run `python support/scripts/diablo.py build-host --jobs 8` from the project root.
`--configure-only` stops after CMake generation. The recipe is
`support/host-reference.json`; outputs and fetched dependencies are confined to
`.work/build/reference-host`. Private data is not copied or used during compilation.

The first implementation uses the installed UCRT64 GCC toolchain and MinGW Makefiles.
The build applies the recorded `support/patches/host-dependency-fixes.json` after
configuration. The miniupnpc Windows timeout patch preserves networking and the
Unix timeout path; exact original/patched file hashes reject unexpected source.
Applied fixes are recorded in the build directory's `dependency-fixes.json`.
It requests the upstream pinned SDL2 dependency, retains audio/network/replay
features and configures upstream tests. Building the `devilutionx` target does not
execute those tests or establish successful gameplay.

The build records source identity, tool hashes, recipe hash and upstream dependency
declaration file hashes in `build-inputs.json`. Reusing the directory with different
recorded inputs is refused. `--reconfigure` admits a recipe/integration-only change
while preserving the old input record; source and tool changes still require a
separate directory. Do not delete another build to bypass this check.
Configure/build logs stay in the build directory, and the CLI writes its normal
operation receipt. A failed configure can resume with identical inputs.

For the clean-rebuild check, select a new directory explicitly:
`python support/scripts/diablo.py build-host --build-dir .work/build/reference-host-clean --jobs 8`.
The path must remain beneath `.work/build`; existing build directories are preserved.
Do this after the reference recipe is validated. An incremental rebuild of an
existing directory does not establish the clean-rebuild requirement.

`.mister/host-dependency-inventory.json` lists upstream fetch declarations, including
conditional dependencies. It is not yet a complete dependency lock. Downloaded
trees, system-library selections and runtime dependencies still need inventory
before step 1 is complete. The host compiler does not establish ARM compatibility.

The project-owned CMake include `support/cmake/host-reference.cmake` supplies
MinGW's gettext link dependency exposed by the engine language header. It leaves
the pinned engine checkout unchanged. `python support/scripts/host_dependencies.py`
snapshots fetched source trees and records the exact CMake/link inputs; runtime DLL
and complete sysroot identities still require separate validation.
The include also confines SDL's Windows entry-point library to the game executable,
so upstream console tests and benchmarks can use their own `main`. Test targets
receive `SDL_MAIN_HANDLED` and the gettext dependency explicitly.

Two hash-checked engine fixes are generated into `host-engine-overlay` during
configuration: Windows absolute asset paths and a null check before PNG loading.
`host-engine-fixes.txt` records original/generated hashes. The pinned checkout
stays clean, but the resulting reference executable contains these recorded fixes.
No golden images are changed. Build the full upstream tests and benchmarks with
`cmake --build .work/build/reference-host --parallel 8 --target diablo_host_tests`,
then run `ctest --test-dir .work/build/reference-host --output-on-failure`.
Both commands need the recipe toolchain's `bin` directory first on `PATH`.
Asset-dependent tests also need the private MPQs beside the test executables.
This Windows machine cannot create unprivileged symlinks, so the current test
build uses copies under the ignored `.work/build/reference-host` directory.
Their hashes match `game/`; provenance is recorded in
`.mister/evidence/host-test-mpq-copies.json`. Never include these copies in a release.

`.mister/evidence/host-loaded-modules.json` records DLL paths and hashes observed
at the Diablo menu. It does not cover optional libraries loaded later in gameplay.

After a successful build, run `python support/scripts/run_host.py diablo` or
`python support/scripts/run_host.py hellfire`. Each uses its own `.work/runtime`
configuration, save and log directories. The first configuration requests a
640×480 window with desktop fitting disabled. Closing the game completes the
runner and records its exit code. A running process or exit code alone does not
establish rendered gameplay or correctness.

For gameplay regression without Computer Use, run
`python support/scripts/replay_host.py --offscreen --timedemo`.
This copies the pinned upstream `WarriorLevel1to2` fixture to a new private runtime
directory, enables engine drawing with SDL dummy video/audio, and checks the
engine's final-state comparison. It covers a shareware-mode Diablo replay only.
Omit `--timedemo` for normal replay pacing; accelerated mode draws at game ticks
and its reported FPS is not a presentation-rate or MiSTer performance result.
Neither mode establishes physical display/audio quality or full-frame equality.

After rebuilding with the capture integration, add `--capture-frames` to save one
complete indexed gameplay frame in every 128 draws. Each `.d8f` contains a 32-byte
little-endian header (magic, dimensions, draw ID, simulated milliseconds), all
256 RGB888 palette entries, and 640×480 pixel indices without row padding.
Compare two replay `frames` directories with
`python support/scripts/compare_frames.py <first-frames-directory> <second-frames-directory>`.
The comparison rejects missing/partial captures and reports the first pixel,
palette or timestamp mismatch. Capture writes affect timing; use separate runs
for performance measurement. Capture correctness is not accepted until real
repeated replay outputs have been compared.

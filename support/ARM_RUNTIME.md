# ARM runtime bring-up

The [detailed closure plan](../reports/audit-2026-09-07/PROPOSED_PLAN.md) is
the current acceptance authority. This guide preserves runtime facts and exact
setup contracts, but historical build observations do not promote a candidate.

Step 3 remains unaccepted until the probe and engine execute on the actual MiSTer.
The available WSL Ubuntu cross-compiler is ARM hard-float GCC 15.2.0. Its default
sysroot has not been matched to the board.

The historical target observations below do not validate the current audit-fixed
tree. Before any new physical mapping, create a new immutable candidate manifest,
rebuild matching ARM/RBF artifacts and follow the detailed audit closure plan.

Build the standalone probe from the project root:

```powershell
wsl -d Ubuntu -- arm-linux-gnueabihf-g++ -std=c++23 -O2 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -pthread /mnt/d/Arcade/AI/aCORES/Diablo/support/reference/arm_runtime_probe.cpp -o /mnt/d/Arcade/AI/aCORES/Diablo/.work/build/arm-runtime-probe/probe
```

The current executable is ELF32 little-endian ARM EABI5, uses hard-float calling
conventions, and contains NEON arithmetic. It requests `/lib/ld-linux-armhf.so.3`
and requires GLIBC 2.34 and GLIBCXX 3.4.31. These requirements are observations of
this build, not proof the MiSTer provides them. Do not replace system libraries
to satisfy this probe. Select a matching sysroot or an isolated runtime after
collecting the board's loader, library versions, kernel and memory map.

On the identified board, first record `uname -a`, `/proc/cpuinfo`, `/proc/meminfo`,
`/proc/iomem`, `getconf GNU_LIBC_VERSION` if available, and loader/library paths.
Missing utilities are evidence to record, not a reason to modify the system.
The memory map must be reviewed separately before any shared-memory access.

`support/scripts/inspect_arm_runtime.sh` collects these facts, runtime file hashes
and ELF version information when the utilities are installed. Run it with `sh`
on the identified board and retain stdout in the private working directory. It
performs no writes or physical-memory mappings. Syntax validation on WSL is
complete; execution on MiSTer is pending. Redacted or unavailable memory maps
must not be treated as proof of a reserved DDR region.

After resolving runtime compatibility, execute the probe in a writable project
directory. Require exit zero and its PASS report; it checks C++23 formatting,
NEON arithmetic, thread creation and atomic publication. Repeat with an argument
to change the arithmetic input. It neither benchmarks FPS nor proves dual-core
scaling. Build and exercise the real engine dependencies next, before accepting
the toolchain or making performance claims.

Engine cross-build preparation uses `support/cmake/arm-linux-gnueabihf.cmake`.
The first configuration in `.work/build/arm-engine-preparation` was stopped:
Debian cross GCC's default header search included host `/usr/include`, causing
SDL to detect `samplerate.h` without an ARM library. That cache is rejected.
The replacement build is `/home/meath/.cache/diablo-arm-engine-isolated` inside
WSL, with commands and logs in `.work/build/arm-engine-isolated`. The toolchain selects Cortex-A9/NEON
hard-float flags and restricts library/header/package discovery to ARM paths;
host programs such as CMake and Ninja remain native. It also clears host
pkg-config search paths. An explicit compile-only sysroot removes the compiler's
host header fallback; link searches retain the Debian cross runtime layout.
The pinned engine source remains unchanged.

The exact configure invocation is recorded in that build directory's
`configure-command.json`, with output in `configure.log`. It retains SDL2,
audio, TCP networking and replay support and builds the selected dependencies
from source. Upstream tests are disabled for this cross-compilation preparation;
the accepted host test results are separate evidence. This build is not a
MiSTer runtime acceptance or a substitute for the custom presentation, audio
and input integration in later steps.

The isolated configuration and all 1,038 build tasks completed successfully.
`.mister/evidence/arm-engine-first-build.json` records the executable hash,
architecture, dynamic dependencies and selected SDL drivers. The executable is
ARMv7 EABI5 hard-float with NEON attributes. The source checkout remains clean.

This first engine binary requires GLIBC 2.43, unlike the smaller initial probe.
It therefore must not be assumed compatible with MiSTer. Its SDL video drivers
are dummy and offscreen; audio drivers are disk, dummy and OSS. These are build
preparation capabilities, not the required MiSTer transport. Gettext host tools
were absent, so translated assets were not generated. No ARM execution or
gameplay test has been performed. Preserve this artifact as compilation evidence
while resolving the target sysroot and custom platform integration.

An older-runtime candidate is now under evaluation: the ARMv7/NEON GCC 15.2
archive from [tttapa/toolchains release 1.3.1](https://github.com/tttapa/toolchains/releases/tag/1.3.1).
Its published SHA-256 was verified before extraction. The release configuration
uses GLIBC 2.27 and Linux 4.15 headers. The existing C++23/thread/NEON probe
cross-compiles with static C++ and GCC runtimes, requiring GLIBC symbols only
through 2.25. This is not proof of execution or board compatibility.

`support/cmake/arm-portable.cmake` obtains the compiler's own sysroot and confines
package/header/library discovery to it. The fresh engine configuration runs in
WSL at `/home/meath/.cache/diablo-arm-engine-portable`; commands and logs are in
`.work/build/arm-engine-portable`. Keep it separate from the successful Ubuntu
GLIBC 2.43 build. The full engine's symbol requirements must be checked again;
the smaller probe cannot establish them.

The portable engine has now configured, compiled and linked successfully.
Its ELF symbol requirements reach GLIBC 2.27, and its dynamic dependencies are
the loader, libc, libm, libpthread and libdl. The recorded artifact is in
`.mister/evidence/arm-engine-portable-build.json`. It still uses the preparation
SDL drivers and has no MiSTer transport. The runtime remains unaccepted on hardware.

Run the pinned shareware gameplay regression under the private ARM emulator:

```powershell
python support/scripts/replay_arm.py
```

The launcher uses a new private save/config directory, preserves the fixture's
recorded resolution, leaves engine drawing enabled, and requires the engine's
final-state comparison to match. It uses an accelerated timedemo; neither its
reported frame rate nor elapsed duration is a MiSTer performance measurement.
The first emulated engine replay passed all 4,853 frames and the engine's final
state comparison. Evidence: `.mister/evidence/arm-gameplay-replay-pass.json`.

Optional `arm-reference.cmake` instrumentation also builds successfully. The
native640 scenario runner requires an explicit build directory and a successful
`diablo-arm-build-receipt-v1` record. The retained reference record is an adapter
derived from the recorded successful capture, matching run, CMake command/logs,
source-lock revision and generated overlay manifest; it is regenerated only by
`record_arm_reference_provenance.py` after those inputs and the surviving ELF
hash agree. Its role comes from the recorded CMake include
`support/cmake/arm-reference.cmake`, not from a caller-supplied JSON role. The
optional `--build-role` only cross-checks that derived role. For the retained
reference artifact, this usable command verifies the exact path and hash before
QEMU starts:

```powershell
python support/scripts/scenario_arm.py diablo `
  --build-dir /home/meath/.cache/diablo-arm-engine-portable `
  --build-receipt .mister/evidence/receipts/arm-reference-portable-build-20260908.json `
  --build-role arm-reference
```

The same command with `hellfire` completes the second campaign scenario. The
deployable `arm-transport` binary intentionally has no native scenario hooks;
use `replay_arm.py --build-dir <arm-transport-build-dir>` for its timedemo
replay. An arbitrary `{ "build_role", "binary_sha256" }` object, a failed typed
record, a changed recipe, or a selected path other than the receipt artifact is
rejected before QEMU. This provenance is a local reproducibility binding to the
retained evidence and ELF, not a signed supply-chain attestation. The initial cursor mismatch is preserved in
`.mister/evidence/arm-native-capture-mismatch.json`.

The loading trace confirmed that a live SDL mouse-motion event overwrites the
recorded cursor `(320, 180)` with `(0, 0)` inside `HandleProgressBarUpdate`.
`replay-loading.cmake` now filters live mouse motion/button events during replay
in that loop, retaining recorded input and loading/window events. Both reference
integrations use the same patch; the pinned engine checkout stays unchanged.
The corrected ARM build passes both scenarios and exact comparison of all ten
sampled frames with the accepted clean PC references, including all pixel indices,
RGB888 palette entries and metadata. No regions are masked or cropped. Evidence:
`.mister/evidence/arm-replay-loading-cursor.json` and
`.mister/evidence/arm-native-capture-pass.json`. This covers the town/panel/cursor
scenarios, not full renderer coverage or hardware qualification. The PC reference
rebuild with the shared fix is pending validation.

The portable probe now passes twice under QEMU 10.2.1 user-mode emulation with
`-cpu cortex-a9` and the candidate sysroot supplied through `-L`. Different
arguments produce the expected NEON results (11 and 12). The package digest and
commands are recorded in `.mister/evidence/arm-runtime-probe-emulated.json`.
The emulator was extracted into a private WSL cache without installing system
packages or registering binary handlers. This checks ARM instructions and the
candidate loader/libraries while using WSL kernel services. Kernel version,
online CPU count and timing from this run do not describe the MiSTer. It does
not accept step 3 or establish FPS, hardware access or dual-core scaling.

## Transport-aware engine overlay

The isolated ARM transport build is configured at
`/home/meath/.cache/diablo-arm-engine-transport` with
`support/cmake/arm-portable.cmake` and the deferred overlay module
`support/cmake/arm-transport.cmake`. It builds all 1,038 tasks successfully for
the Cortex-A9 hard-float target. The pinned DevilutionX checkout is unchanged;
the generated overlay replaces only `engine/dx.cpp` and `main.cpp` in the build
tree. The executable and source hashes are recorded in
`.mister/evidence/arm-engine-transport-build-20260906.json`.

When using the complete release package, invoke the bundled target launcher from
the package root. It verifies package/deployment v2 and every asset hash, checks
the supplied private campaign data, creates a current-boot admission, loads the
exact RBF and passes the locked lease descriptor to the ARM child:

```sh
python3 diablo_launcher.py \
  --data-root /media/fat/tmp_esc/diablo-data \
  --save-root /media/fat/games/Diablo/saves \
  --config-root /media/fat/games/Diablo/config \
  --runtime-root /media/fat/tmp_esc/diablo-runtime \
  --campaign diablo
```

Repeat with --campaign hellfire only when all Hellfire archives are present.
The launcher must be the foreground owner of the session; do not hand-create an
admission file or map the aperture from a second process. When --timedemo is
passed as an engine argument, the target overlay enables a bounded 60 Hz pacing
deadline so the benchmark cannot flood the finite frame ring. Timedemo stability,
video identity and physical audio still require candidate-bound board evidence.

When the engine runs on MiSTer, enable the path explicitly:

```sh
export DIABLO_MISTER_TRANSPORT=1
export DIABLO_MISTER_SHARED_PHYS=0x3fe00000
export DIABLO_MISTER_CANDIDATE_ID=<64-lowercase-hex-candidate-id>
export DIABLO_MISTER_ADMISSION_FILE=<launcher-created-current-boot-record>
export DIABLO_MISTER_TRANSPORT_LOCK=<runtime-owned-writable-lock-path>
export DIABLO_MISTER_SESSION_EPOCH=0x<fresh-nonzero-value>
./devilutionx
```

The physical base is supplied by a current-boot reservation proof and is not baked
into the reusable runtime. The runtime rejects a malformed aperture, an admission
record whose boot/base/bytes/candidate do not match, or a conflicting writer lease
before mapping /dev/mem. `support/scripts/diablo_launch.py` now supplies the
project-owned preflight and supervision contract: it verifies the immutable
candidate and the selected RBF/engine pair, checks campaign-owned data and writable
saves, creates one current-boot admission record, waits for an explicit loader-ready
candidate token, and passes a non-deleting lease path to the runtime. The runtime,
not the launcher, owns the `flock` lease for its mapped lifetime. The bundled launcher now binds the exact RBF process and current-boot record; the final MiSTer
menu/profile integration and physical acceptance remain C16 target work. Do not hand-create an admission record
to bypass its loader readiness and cleanup path. The wrapper keeps SDL surface creation available while
the adapter publishes the native indexed surface and palette into the bounded
three-slot transport. The generated target overlay also replaces the pinned
sound unit and Aulib callback in the build tree; the ARM mix stays at 22.05 kHz
and a stateful linear publisher supplies the FPGA's fixed 48 kHz stereo PCM ring.
Device mappings use an ARM barrier rather than a per-frame
`msync`; file-backed mappings retain `msync` for QEMU fixtures. The publisher uses
sampled CRC by default (`DIABLO_MISTER_FULL_CRC=1` enables the full diagnostic
checksum) and a fast epoch/state ownership path after one-time ABI validation. The
adapter waits once for FPGA readiness, then makes only two 1 ms backpressure retries
before returning to SDL pacing; this bounds CPU stalls while preserving the rule that
an occupied slot is never overwritten. A missing mapping or invalid surface is
reported and falls back to normal SDL presentation, so a successful process start
alone does not prove FPGA scanout.

For a file-backed or QEMU run, set `DIABLO_MISTER_SHARED_PATH` instead of
`DIABLO_MISTER_SHARED_PHYS` and still provide `DIABLO_MISTER_TRANSPORT_LOCK`.
`TransportRuntime::Open` acquires the same exclusive lease before opening the
shared file, so a standalone probe cannot map it concurrently with the engine.
The ARM/QEMU ABI probe creates a dedicated lock path and records this check in
`.mister/evidence/transport-abi-layout-test.json`; the lock is a runtime
requirement for file-backed test sessions as well as physical sessions.

The current target receipts prove executable loading, MPQ discovery, sustained frame
publication and FPGA ownership with no transport fault. The latest fresh-RBF
90-second dummy-SDL timedemo reached 2,650 frames in 89.08 seconds (29.7 FPS), had
no startup wait expiry and logged 24 rate-limited fallback notices. The earlier
blocking implementation measured 14.3 FPS; the same-board transport-disabled
reference is 33.2 FPS. The bounded fallback therefore removes the worst publish
stall but does not yet demonstrate the approximately 60 FPS real-vblank target.
The FPGA control reader also revalidates a changed session while attached; two
successive ARM sessions reached `fpga=ready` without a second RBF load.
The final display-acknowledgement RBF was then loaded on the board. A 15-second
headless session reached `arm=1`, `fpga=1`, `fault=0`, `display_epoch=0x9e` and
`last_presented_frame_id=159`; all three slots contained nonzero display epochs.
Physical input edges, live audio, HDMI image inspection, deterministic timedemo
equality and long-duration gameplay are separate hardware qualification gates; see
`.mister/evidence/transport-display-ack-hardware-20260906.json` and
`.mister/evidence/arm-engine-transport-timedemo-20260906.json`.

The input-enabled rebuild was remeasured after the bridge was added: a fresh-RBF
90-second dummy-SDL timedemo reached 2,635 frames in 89.04 seconds (29.6 FPS), with
24 rate-limited fallback notices and no transport fault. This remains a bounded
transport measurement, not a real-vblank or 60 FPS qualification; see
`.mister/evidence/arm-engine-transport-input-timedemo-20260907.json`.

The ARM SDL input bridge is now built into the transport overlay. Keyboard PS/2
make/break codes, mouse motion/buttons/wheel, joystick button/analog snapshots and
focus changes are reduced into SDL events during the same bounded frame-present
path. The MiSTer joystick button map is enabled through DevilutionX's keyboard
controller path so menu and gameplay actions use the same SDL key state as a
keyboard. A fresh-RBF board run with the real ARM DevilutionX binary and a
deterministic `/dev/mem` ring injector logged all three event classes while the
transport state remained `arm=1`, `fpga=1`, `fault=0`; the receipt is
`.mister/evidence/arm-input-sdl-bridge-20260907.json`.

That receipt validates the ARM-to-SDL ABI path, not a physical peripheral. A
257-record synthetic full-ring injection now reaches the real adapter, logs
`input overflow recovered`, and leaves the ARM producer and consumer cursors
equal; physical keyboard/mouse/controller edges, OSD focus and
disconnect/reconnect behavior remain open. Evidence:
`.mister/evidence/arm-input-overflow-recovery-20260907.json`.

The audio overlay is now built into the same ARM target. A fresh-RBF smoke with
the real ARM process logged Aulib sampleRate=22050 channels=2, then published
4,457-4,458 resampled frames per callback into the fixed 48 kHz ring with no PCM
backpressure; the transport stayed at `arm=1`, `fpga=1`, `fault=0`. The current
FPGA image widens the local PCM FIFO to 1,024 stereo samples and is timing-clean
(minimum setup/hold slack 0.188/0.114 ns). Loading that exact image on MiSTer
caused the expected stale epoch during reload, then the ARM process reattached
on a fresh epoch with zero transport fault. Active dummy-SDL samples kept
`pcm_resyncs=0` but still accumulated nonzero underruns. The board SDL build
does not expose an ALSA target, so the probe stopped at `Audio target 'alsa' not
available`; physical speaker output and zero-underrun qualification remain open.
Evidence: `.mister/evidence/fpga-pcm-fifo1024-build-20260907.json`,
`.mister/evidence/arm-fpga-pcm-fifo1024-hardware-20260907.json`,
`.mister/evidence/arm-audio-driver-probe-20260907.json`,
`.mister/evidence/arm-audio-pcm-transport-20260907.json` and
`.mister/evidence/arm-pcm-health-20260907.json`.

`TransportRuntime` now detects an FPGA fault caused by a live core reload,
clears the shared control page, rebinds the ARM session to a generated epoch
and lets the existing SDL process continue. A concurrent board timedemo
survived an RBF reload, logged `transport recovered after FPGA reset`, and
returned to `fpga=1`, `fault=0` at 29.8 FPS. Evidence:
`.mister/evidence/arm-fpga-reset-recovery-20260907.json` and
`.mister/evidence/arm-engine-transport-recovery-build-20260907.json`.

The current profile-enabled overlay caches unchanged palettes in the shared
mapping and records bounded present duration when `DIABLO_MISTER_PROFILE=1` is
set. With the timing-clean immediate-retirement RBF, two real Diablo timedemos
ended with `arm=1`, `fpga=1`, `fault=0`; the runs measured 29.2 and 28.3 FPS and
published 926/1033 and 908/1001 present calls. The FPGA now retires the former
displayed slot at the activation vblank, and the control reader allows its
nonzero display epoch while preserving the ARM producer epoch. These runs use
dummy SDL video/audio and leave physical I/O, real-vblank pacing, zero-underrun
audio and the approximately 60 FPS target open. Evidence:
`.mister/evidence/arm-engine-transport-present-profile-build-20260907.json`,
`.mister/evidence/fpga-frame-retire-immediate-build-20260907.json` and
`.mister/evidence/arm-engine-transport-present-profile-20260907.json`.

The admitted shared-DDR aperture was benchmarked on the target: libc `memcpy`
measured about 94 MiB/s, while explicit scalar64 and NEON loops were slower and
the cached-open mapping showed no gain. A 640x480 indexed frame therefore costs
about 3.1 ms of raw ARM writes before ownership and contention overhead. The
measurement is recorded in `.mister/evidence/arm-shared-ddr-copy-benchmark-20260907.json`;
it does not close the rendering-acceleration or 60 FPS gates.

The follow-up profile splits `Present()` into publish attempts and the shared
memory flush. It measured 1,235 publish attempts at 4,882 microseconds average,
while 1,013 flushes averaged 1 microsecond and peaked at 20 microseconds; the
timedemo reached 28.6 FPS with `arm=1`, `fpga=1`, `fault=0`. The barrier is not
the frame-time bottleneck, so the next performance work belongs in publish/copy
overlap, command rendering or a direct render target. Evidence:
`.mister/evidence/arm-engine-transport-present-profile-breakdown-build-20260907.json`
and `.mister/evidence/arm-engine-transport-present-profile-breakdown-20260907.json`.

`DIABLO_MISTER_DIRTY_COPY=1` enables a measured experimental path that caches
one source shadow per slot, writes changed runs and falls back to whole-row
writes for busy rows. The paired board timedemo reduced publish time from 4.413
ms to 3.432 ms and measured 29.3 FPS versus 28.3 FPS with the option unset;
both runs were fault-free. Keep it opt-in until broader scene and real-vblank
qualification is complete. Evidence: `.mister/evidence/arm-dirty-copy-ab-20260907.json`.

`DIABLO_MISTER_NO_CPU_PACING=1` is a diagnostic switch that removes the normal
SDL frame-rate limiter. A same-binary board A/B reached 27.4 FPS without the
limiter and 30.3 FPS with it enabled; both sessions ended with `arm=1`, `fpga=1`
and `fault=0`. The paced path remains the default because unpaced submission
increased occupied-ring pressure rather than improving throughput. Evidence:
`.mister/evidence/arm-cpu-pacing-ab-20260907.json`.

The software command-renderer foundation now defines bounded 32-byte records for
ordered clipped fills and overlap-safe copies against a persistent indexed
target. Its host test covers clipping, overlap, unsupported commands and buffer
capacity. The FPGA consumer accepts target slots 0–2 using the ABI's 311,296-byte
stride. Evidence:
`.mister/evidence/software-command-renderer-test-20260907.json`.

The matching ARM command publisher now handles epoch validation, bounded record
and payload occupancy, ring wrap and release ordering. Its host fixture passes
both ring boundaries and full-ring rejection. The new FPGA consumer validates
the same ring identity and executes bounded indexed fills/copies with overlap
ordering, consumer acknowledgements and fence publication under randomized DDR
backpressure. It is instantiated behind the top-level DDR arbiter with
scanout/audio/input priority; the final Quartus RBF builds with positive timing
slack at all corners. Live DevilutionX command submission now passes on the exact
image, while full-scene byte equality and physical display qualification remain
open. Evidence:
`.mister/evidence/software-command-transport-test-20260907.json`,
`.mister/evidence/fpga-command-consumer-test-20260907.json`,
`.mister/evidence/fpga-command-consumer-faultclear-build-20260907.json` and
`.mister/evidence/arm-command-scene-live-hardware-20260907.json`.

## Candidate38 runtime evidence — 8 September 2026

Candidate38 was a historical development checkpoint. Its ARM transport executable
is `.work/build/arm-engine-candidate38-pcm-telemetry/devilutionx`, SHA-256
`ead7cc2ac6417ce88833a66e7fcf400d85058061964a96f43a44658fb3bee87c`; the matching
FPGA RBF SHA-256 is
`7b5eb62411233b96adc244d87fe3ee96b16da13b271fa608d9a70cafd4917b10`. The ARM
overlay configures and builds all 742 targets, and the candidate38 package and
deployment manifests verify without a source checkout.

The full Python suite passes 132 tests with one declared Windows privilege skip.
Host timedemo replay passes, and ARM/QEMU timedemo replay passes with the
documented 600-second bound; the run records
`replay_outcome_matches=true` at
`.work/runtime/arm-replays/742d6ace2dd84dea88b391094bf84e9b/run.json`.
The 600-second bound is intentional: the current QEMU environment completes the
timedemo at roughly 16 FPS, so a 90-second ad hoc timeout reports a false
timeout before comparison. The scripted default remains the accepted bound.

On MiSTer, the candidate38 launcher proves current-boot admission, exact requested
RBF process matching, FPGA operating state, frame publication and controlled
termination. The normal60 observation records local FIFO occupancy 7,257, startup
underruns 6,766, no resync and no additional underrun/resync delta after priming.
This is not physical audio acceptance: HDMI capture is black/stale, the observer
reports AO486, and active campaign, controls, speakers, performance and lifecycle
workflows remain open. User-owned MPQs must be supplied through an explicit data
root; they are intentionally excluded from the runtime package.

## Candidate40 update — local fix and board-run disposition

Candidate40 follows a real local regression fix: the integrated DDR testbench now
matches the production PCM queue width and its final response accounting handles
one in-flight request. Candidate-bound local verification passes all 20 registered
checks, and the full Python suite passes 132 tests with one declared skip.

The historical manifest was
`.mister/evidence/candidates/fpga-candidate-20260908-40-integrated-tb.json`
(candidate `56860713d38990ae28f1846e5f22850ed68b9ee228f6178c11e53fcb0f2d8a9b`,
source `13b93de9eb32d9fc72701886c164853622bc744c18cddec1b660f127ffc70c7d`).
Package40 preflight passes. A clean five-second launcher smoke passes admission,
exact RBF matching, FPGA operating state and controlled exit. The longer target
attempt is blocked by a concurrent NFS_SE install/rollback process and records
active PCM underrun growth and dropped chunks, so it is not physical acceptance.
Obtain an exclusive, quiescent board window before the next ARM/audio/video/input
run; keep user-owned MPQs outside the package and provide them through the
explicit target data root.


## Candidate49 historical development identity — 8 September 2026

Candidate49 was the historical artifact-bound development identity after the
candidate43 source-policy build; C34/P01-P06 source commits now supersede it: candidate
`d95d4cfd03154bd659343c5a77a1230bcd4efc7c45d81d4f2299a0d754128611`, source
`59d9a616708db186946cab362d6c66627a99d9a21a18b4bf6f97cb70a3e9eda0`, manifest
`.mister/evidence/candidates/fpga-candidate-20260908-49-final-local.json` (SHA
`f420873962a21317c8a9bdc9ff1ad07db02d9ad4299c2b9b5ff2e1abae802c4b`). It binds
the ARM transport executable SHA `ead7cc2ac6417ce88833a66e7fcf400d85058061964a96f43a44658fb3bee87c`,
fresh SOF SHA `ae7f6bbc69f6d52f00f9e3bb7637de35b8495dac7f72aadc8a2794889dce98e7`
and raw/compressed RBF SHA
`7b5eb62411233b96adc244d87fe3ee96b16da13b271fa608d9a70cafd4917b10`. Direct
Quartus compile, compression and four-corner timing pass in
`.mister/evidence/fpga-build-candidate43.json` (SHA
`f825d7ab8eaaccfd2f03699bb775c329b759d1bee5eebba648354334317fe2e2`).
Candidate-bound local/ARM-QEMU and both role-aware scene-oracle receipts pass.
Package49 contains 192 files/184 assets plus `NOTICE.txt` and `SETUP.md`, verifies
locally, and is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate49FinalLocal`; its passing
read-only target preflight is `.mister/evidence/receipts/20260908T-candidate49-preflight.json`
(SHA `64d827d9d29953396c55be9314ae19fde04aa63820370573fab9de3d594a1b78`). The
local deployment lifecycle receipt
`.mister/evidence/receipts/20260908T-candidate49-deployment-lifecycle.json`
(SHA `324d8ad330f940de78d52d77f372b8c04cbf7dce10eeb3278e899410dee14c01`)
passes install, interrupted update, update, rollback, save preservation and
final manifest verification.

Candidate49 remains development-only. The target is owned by an external MAME
core, so no RBF activation or physical observation was attempted. HDMI/direct-
RGB/analog gameplay, active stereo audio, controls, campaign/save/multiplayer,
performance, menu activation and clean-target install/update/rollback remain open.

## Candidate41 historical development identity — 8 September 2026

Candidate41 was the prior documentation-synchronized development identity: candidate `a5f2b83c0191d56e44a7b1babd5988e3fc0530a9f973f6e6bb739b13479ab989`, source `7901cdc0d54c3d8d3a527a85445c78d4d1ad5330e1b223f426a3ed15dc914d0d`, manifest `.mister/evidence/candidates/fpga-candidate-20260908-41-doc-sync.json` (SHA `c87c3b7dc214f23c4dc299c9010cbf2e8e031c2962a1a05604d59fa7452b0579`). The ARM transport executable and FPGA RBF are unchanged from candidate40 (SHA-256 `ead7cc2ac6417ce88833a66e7fcf400d85058061964a96f43a44658fb3bee87c` and `7b5eb62411233b96adc244d87fe3ee96b16da13b271fa608d9a70cafd4917b10`). Package41 has 190 files including 184 assets, target preflight passes (`.mister/evidence/receipts/20260908T-candidate41-preflight.json`, SHA `d917dafcefb058d51f4de183543ca6e36d7cbc3c98645eb5a5b15e835befcacf`) and candidate-bound local verification passes all 20 checks (`.mister/evidence/receipts/20260907T221825Z-1b8d996d-61dc-41d2-b5bd-e72fc2e178a4.json`, SHA `e28aaedf6096ed519ecf792a8736284cb3b288300a73f9bd3c669b95e5eec74e`). The prior five-second launcher smoke remains same-artifact development evidence. The longer target run is blocked by concurrent NFS_SE installer/rollback ownership and active PCM underrun/drop growth (`.mister/evidence/receipts/20260908T-physical-launch-candidate40-attempt.json`, SHA `9ce81ad97fddeaf01ce178d3453d1096a7c5e623dfde04318508869195f8bdae`). Acquire an exclusive board window before physical video/audio/input/campaign/performance/install qualification.


## Candidate41 physical run disposition — 8 September 2026

Candidate41 completed a quiescent-board Diablo normal-session launcher run. The
exact RBF process and FPGA `operating` state matched, the launcher exited 0, and
the transport trace showed no PCM drops/resyncs or steady underrun delta after the
startup sample. The observer remained black/stale and startup underruns were 6,732;
the candidate-bound board receipt is therefore blocked rather than accepted:
`.mister/evidence/receipts/20260908T-physical-launch-candidate41-normal60.json`
(SHA-256 `3a1f7e97d3be5429000b27e9d3c1319dd42cf1291f02cba52e505651b5f845fb`).
Physical video identity, speaker output, controls, campaign/save, performance and
install/update/rollback still require a passing target qualification matrix.


## Candidate41 timedemo target blocker — 8 September 2026

A separate Diablo demo/timedemo launch was not accepted because a concurrent
MAME core owned MiSTer while the launcher waited for the exact candidate RBF. The
background launcher was cleaned up without changing the candidate artifacts. The
blocked diagnostic receipt is
`.mister/evidence/receipts/20260908T-physical-timedemo-candidate41-blocked.json`
(SHA-256 `028404ad383e53cfc8ff545f0ca5682afc11046d4799fba67debabae40731758`).
The next target window must exclude MiSTer, MAME and installer processes before
timedemo or campaign qualification.

# Diablo MiSTer core — completion guide

This is the execution order for bringing the Diablo/Hellfire core to a release
that is correct, responsive and repeatable on a DE10-Nano. Keep the current
result and the next exact action in `.mister/state.json`. A step is complete only
when its listed host, RTL and board checks have evidence.

The detailed closure authority is reports/audit-2026-09-07/PROPOSED_PLAN.md.
This guide preserves historical milestones. If it disagrees with that plan or
.mister/state.json about a current candidate, the audit plan and state control;
older build and board receipts do not validate later source changes.

The performance target is native 640×480 with a stable presentation deadline of
about 16.67 ms. ARM simulation, asset work and submission should overlap FPGA
scanout, command execution and audio/input service. Higher utilization alone is
not a pass: measure frame-time tails, deadline misses, input latency and service
starvation while preserving game timing and pixels.

## Rules

- Use the pinned source identities in `.mister/source-lock.json`; keep `game/`
  and the Blood checkout read-only.
- Use Quartus from `D:/Q17`. The retired custom workflow runner is not required.
- Keep engine sources, build outputs, board artifacts and evidence separate.
- Do not hide a fault by dropping drawing work or reusing an owned buffer.
- Use the real MiSTer for hardware claims. Host, RTL, emulation and dummy SDL
  are preparation or bounded evidence, not physical HDMI/audio/input acceptance.
- Rebuild the RBF after every functional RTL change and record its SHA-256.

## Step 1 — accept the host reference

1. Build the pinned DevilutionX reference with SDL2, audio, networking and replay.
2. Record the compiler, dependencies, private MPQs and build options.
3. Run upstream tests and both Diablo and Hellfire with isolated saves/configs.
4. Capture repeated native 640×480 indexed frames including the complete palette.

Pass criteria: clean rebuild, playable scenes for both campaigns and identical
repeat captures. The accepted evidence is
`.mister/evidence/step-1-host-reference-acceptance.json`.

## Step 2 — establish the FPGA video shell

1. Preserve the MiSTer system wrapper and clocks; replace only the demo logic.
2. Validate 640×480 progressive geometry, borders, color bars and palette paths.
3. Constrain all active clocks and inspect inferred RAM, DSP and PLL resources.
4. Run `quartus_sh --flow compile Diablo` from `D:/Q17`; retain all timing corners.
5. Load the exact compressed RBF on the board and inspect HDMI and analog output.

Pass criteria: clean synthesis/fitting/assembly/timing and observed board pixels.
The current RBF is timing-clean, but physical HDMI/analog inspection is still a
release gate.

## Step 3 — bring up the ARM target

1. Record the MiSTer kernel, board paths, reserved RAM and storage locations.
2. Use the ARMv7 hard-float Cortex-A9/NEON toolchain with an isolated sysroot.
3. Run the ABI/runtime probe on the board, then build the transport overlay.
4. Use both ARM cores only for independent work that reduces the critical path;
   preserve deterministic simulation and avoid cache/DDR contention.

Pass criteria: the target executable loads, finds DIABDAT/Hellfire data and all
dynamic dependencies resolve on the board. The ARM overlay currently passes.

## Step 4 — define and prove the shared transport

1. Prove the reserved 2 MiB DDR aperture before mapping it (`0x3fe00000`).
2. Keep the generated C++/RTL ABI in `support/transport/transport_abi.json` and
   `support/reference/transport_abi.hpp`/`rtl/diablo_transport_abi.svh`.
3. Validate identity, epochs, frame ownership, command fences, PCM and input
   rings, release ordering and bounded fault recovery.
4. Test bounds, wrap, stale epochs, malformed descriptors and delayed DDR reads.

Pass criteria: host, RTL and target agree on layout and ownership, and invalid
requests fault without corrupting the ARM half of the header. The current ABI,
frame, audio and input checks pass.

## Step 5 — integrate video, audio and input

1. Publish indexed 640×480 frames with RGB888 palettes and vblank ownership.
2. Feed stereo 48 kHz PCM with priming, bounded queues and underrun counters.
3. Capture keyboard, mouse and controller edges, cumulative motion and focus.
4. Give scanout and audio deterministic arbitration priority; keep input bounded.
5. Stress all three services under DDR pressure, reset and relaunch.

Pass criteria: no tearing or service starvation in board checks, reliable input
edges, and zero-underrun physical audio in a qualification run. Current board
evidence proves frame acknowledgement, ARM PCM publication and synthetic input
conversion. Physical peripherals, speaker output, zero underruns and combined
stress remain open.

## Step 6 — launch the real game

1. Launch Diablo and Hellfire from the MiSTer menu through the dedicated wrapper.
2. Keep one pacing authority and expose startup, OSD, save/config and shutdown
   errors clearly.
3. Exercise town, dungeon, combat, cinematics, menus, save/load, quit, reset,
   core switching and relaunch on the board.

Pass criteria: both campaigns are playable with physical display, sound and
controls. ARM timedemo bring-up currently passes for both campaigns under dummy
SDL; physical gameplay workflows remain open.

## Step 7 — qualify controls and multiplayer

1. Test keyboard/mouse and controller-only naming, menus, inventory and spells.
2. Test disconnect/reconnect, OSD focus, stuck-input recovery and mixed devices.
3. Test TCP host/join with campaign compatibility and network delay while the
   transport remains responsive.

Pass criteria: every required action works on the target and multiplayer survives
normal input, audio and video load. No physical control or multiplayer acceptance
has been recorded yet.

## Step 8 — measure correctness and frame time

1. Capture deterministic town, dungeon, combat, automap, UI and Hellfire scenes.
2. Measure simulation, draw, copy, command, DDR, fence, audio and input stages.
3. Record p50/p95/p99/p99.9 frame times, missed deadlines and input-to-visible
   latency; separate loading/transition stalls from steady state.
4. Fix the measured bottleneck with bounded allocation, caching, prefetch or
   asynchronous work, then rerun the same scene and compare tail latency.

The present-path profile shows the full indexed publish/copy path, not the flush,
dominates time. The command path is now measured on real DevilutionX; its next
optimization target is reducing the high fallback/record count without changing
scene order.

## Step 9 — validate the software command renderer

1. Keep fixed 32-byte records with ordered clipping, persistent indexed targets
   and overlap-safe copies.
2. Bound command capacity and publish an explicit completion fence.
3. Compare every supported command stream against the independent software
   renderer, including UI, cursor restoration and lighting cases.

Host renderer and ring tests pass. The command consumer also passes randomized
DDR-backpressure RTL tests and accepts target slots 0–2.

## Step 10 — execute commands in the FPGA

1. Fetch and validate command/layout/epoch words behind the DDR arbiter.
2. Execute clipped `FillRect`, overlap-safe `CopyRect` and `End` fences.
3. Keep audio/input/scanout service ahead of command traffic and preserve the
   last complete frame on a fault.
4. Add measured batching, caching and direct-target work only after profiling.
5. Compare full ARM scenes byte-for-byte, then compare displayed frames and tail
   frame times against the software path.

The current packed-fill RBF (`4142126272d5b8613b990e6ecc5c25687e9c4c54d8a2c9d37fe7508bae4a77f5`,
2,598,008 bytes) compiled with 0 errors and 82 warnings; all four timing corners
are positive (minimum setup 0.190 ns, hold 0.100 ns). FillRect rows use aligned
64-bit byte-enable writes, while CopyRect remains byte-granular and overlap-safe.
The arbiter gives audio, input and scanout priority over commands, and the
control reader accepts valid frame descriptors during relaunch and clears stale
fault metadata.

The exact RBF was loaded on the physical MiSTer with the final ARM binary
(`29d0870b3f98ec3f33aee29c719fc88c185f5fbd36c63776b3a0d16c4717919e`). In the
fresh 12-second dummy-SDL timedemo, 162 presents produced 157 published frames,
93 command batches and 61 bounded full-copy fallbacks; command building averaged
4.899 ms and fence waits 4.631 ms, with 140 frames rendered in 11.56 seconds
(12.1 FPS). A no-reload relaunch produced 149 presents, 145 published frames,
94 batches and 48 fallbacks; building averaged 5.799 ms and fence waits 4.316 ms,
with 127 frames in 11.47 seconds (11.1 FPS). Both runs ended with equal command
producer/consumer cursors, a completed fence, `arm=1 fpga=1 fault=0` and valid
display acknowledgements. These runs prove real ARM DevilutionX command
execution and FPGA frame ownership on the board under dummy SDL; physical HDMI,
vblank pacing, speakers, controllers, deterministic full-scene equality and a
60 FPS qualification remain open.

## Step 11 — qualify the complete core

1. Repeat both campaigns and all workflows on physical HDMI, audio and controls.
2. Run long idle/gameplay stress, reset/core-switch/relaunch and storage errors.
3. Compare software-only and accelerated builds on identical deterministic scenes.
4. Require stable frame-time tails, bounded input latency, no queue faults and a
   measured improvement toward the 60 FPS deadline before calling acceleration a
   pass.

Open gates are physical HDMI inspection, physical speaker and controller tests,
zero-underrun audio, deterministic gameplay/frame equality, multiplayer, reset/
DDR stress and real-vblank pacing.

## Step 12 — package and install

1. Package the matching RBF, ARM executable, wrapper, ABI manifest and required
   redistributable assets; include hashes and source identities.
2. Exclude private MPQs, saves, captures and donor artifacts.
3. Install on a clean supported MiSTer and repeat launch, play, quit, reset,
   core-switch and relaunch for both campaigns.

Only after Steps 1–12 have target evidence should the core be called fully working.

## Next exact sequence

1. Keep `/media/fat/_Other/Diablo_command_consumer_rectmerge64_20260907.rbf`
   loaded and repeat the fresh/no-reload profiles when a real display is
   connected, retaining state dumps and command counters.
2. Qualify physical HDMI/vblank pacing, speakers with zero-underrun audio and
   keyboard/mouse/joystick input using
   `/media/fat/linux/devilutionx-command-scene-mergefast`.
3. Compare complete deterministic ARM scenes and displayed frames against the
   software renderer; investigate the remaining 48–61 full-copy fallbacks and
   tail frame times before claiming the 60 FPS target.
4. Close campaign workflows, long idle/gameplay stress, reset/core-switch and
   DDR stress, multiplayer, and clean-install packaging on a second launch.

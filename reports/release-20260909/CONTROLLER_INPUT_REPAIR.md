# Controller and keyboard/mouse repair — in progress

User acceptance: Xbox One-layout dual-analog controllers; functional menu
navigation and character movement; independent right-stick cursor; full physical
keyboard/mouse support with a visible cursor. Applies to full Diablo and Hellfire.

## Final candidate validation — 9 September 2026

- Local verification receipt `20260909T033525Z-91c3d493-89e3-4a00-9a71-5d76c28033e4` passes all 23/23 steps with a stable writable temp directory. The earlier failed receipt was an Icarus temp-path failure; the only real follow-up was corrected in the Windows test harness by setting the process environment directly instead of using SDL's environment view.
- Candidate `161d601561b3383805bebe5f70163f9783f19b3f24506c62038eaa1bda30eb0a` packages source `8c888990df5fee2eac6adfc560231aedd319c470f5c1c77929649a4a374fd4a2`, seed-3 RBF `474fd8950f665dc4fdf078c8b542360cbcb38f994b3f3ff40819a4754ce05085`, and ARM engine `aa28f7cda491dccea5c16c411e7f62247626a482432d81671e074dbd2c3cfffa`. Candidate manifest and package self-verification pass.
- The package is installed and verified on MiSTer at `/media/fat/_CodexDiabloCandidateControlsFinal`; the active release is immutable and prior candidates remain available. The launcher is running Hellfire directly, without `--spawn`, using `/media/fat/games/Diablo` as the user data root.
- Target log confirms `DIABDAT.MPQ` and `hellfire.mpq` are found, software rendering is created, hardware cursor capability is overridden for transport, and only `MiSTer Diablo Xbox-layout controller` is admitted. Its mapping shows independent left/right axes, triggers, D-pad, shoulders, stick clicks, View, Menu and Guide slots.
- Physical acceptance is still open: automated evidence cannot press the user's controller, move the user's mouse or observe the HDMI cursor. The exact target runtime is intentionally left running for that check.

## Confirmed evidence

- Read-only live engine log confirms SDL also opens physical joystick 0,
  `8BitDo Ultimate 2C Wireless Controller`, with its own analog/button mapping.
  The transport repair must suppress this duplicate engine controller path,
  including initial enumeration and hotplug (not merely drop motion events).
- Live INI already has all eight `Move*`/`Mouse*` pad actions empty; stale
  directional action overrides are not present in this configuration.
- Live INI has `Hardware Cursor=1`; the transport-only capability override is
  needed even with existing saved settings, not only as a new default.

- Target enumerates an 8BitDo Ultimate 2C Wireless Controller (js0/event10),
  its keyboard/mouse interfaces, and a Telink keyboard/mouse receiver.
- `support/reference/mister_transport_input.hpp::PushJoystick` merges both
  stick axes into bits 0–3 of the digital mask, then emits keyboard scancodes.
  It does not preserve independent left/right SDL controller axes.
- `Diablo.sv` advertises left-stick movement and right-stick cursor operation.
  Its current configuration string has no explicit `J` button-name mapping.
  The actual MiSTer digital-bit contract still needs validation before changing it.
- Upstream `Source/controls/devices/game_controller.cpp` already handles separate
  SDL gamepad left/right axes and opens registered SDL game controllers.

## Required next work

1. Establish the MiSTer button-bit contract and inspect existing engine controller
   initialization; avoid duplicate physical and transport controller delivery.
2. Replace keyboard emulation with registered SDL controller state, preserving
   independent axes, button edges, focus loss, overflow recovery and releases.
3. Verify physical keyboard events/text and mouse motion/buttons/wheel, and
   software-cursor rendering in the actual transport display path.
4. Add focused regressions, rebuild ARM artifact (RTL only if required), package
   and deploy with rollback preserved; warn before interrupting the live game.
5. Validate on target in both full Diablo and Hellfire. Unit tests alone do not
   close physical controller/cursor acceptance.

## Local implementation and verification

- Exhaustive SDL button test caught a real descriptor-index defect: omitting
  Guide from the valid-button mask packs subsequent SDL mappings down one slot.
  Preserving the neutral Guide slot fixes it; all 16 transport bits, both
  triggers, focus and overflow checks now pass with `-Wall -Wextra -Werror`.
- ARM build reporting timed out, but direct process inspection confirmed cmake
  PID 30947 and ninja PID 30948 still compiling; no duplicate build started.
  Guide-mask correction occurred during compilation: a subsequent incremental
  build is required before accepting the resulting artifact.
- Compiler command exposed `HAS_KBCTRL=1` and keyboard controller aliases in
  the ARM configuration. Removed these definitions from `arm-transport.cmake`
  so physical keyboard arrows and modifiers retain native keyboard behavior.
  This configuration edit also requires regeneration/rebuild after the current
  build finishes; no intermediate artifact should be packaged.

- Added `mister_gamepad_state.hpp`: independent signed stick expansion and
  explicit Xbox-layout button/trigger decoding; compile-time isolation tests pass.
- Added `mister_virtual_gamepad.hpp`: registered SDL virtual game controller,
  polled state and generated events share SDL state; explicit detach lifecycle.
- Input reconciler now sends controller state instead of keyboard aliases;
  neutralizes controller output while unfocused and axes after discontinuity.
- Added explicit `J` button order to `Diablo.sv`. A matching RBF rebuild is
  therefore required before validating this contract on the target.
- Native SDL runtime test passes device registration, independent axes, A
  press/release, neutral trigger, neutral axis release and detach.
- Transport entry point permits background joystick delivery because the dummy
  SDL window is not the physical display. OSD focus remains enforced by the
  reconciler's tested neutral/repress policy; desktop focus cannot suppress
  controller input independently.
- Updated legacy shared-Alt regression to require controller/keyboard isolation.
  Recompiled input reconciliation executable passes. Expected filtered-event
  diagnostics occur; profiler trace-open warning still appears in this harness.

The standard input runner now includes all three input/controller executables
and passed. The latest virtual-controller test additionally creates a hidden
SDL dummy window and passes complete mapping/admission/focus/overflow checks.
Generated ARM build rules contain neither `HAS_KBCTRL` nor `KBCTRL_BUTTON`.

Still required: complete the final ARM regeneration including admission overlays
and headless entry-point hint; finish FPGA timing/build checks; verify reconnect,
cursor and all physical keyboard/mouse paths; package/deploy and obtain physical
acceptance. SDL virtual driver support is enabled in the target cache, but local
tests do not prove on-target behavior.

Mouse motion audit resolved in source: MiSTer's sender stores ninth-bit signs
in status bits 4/5 and negates screen Y when forming PS/2 packets. Corrected
`diablo_input_capture.sv` to use those signs and restore screen Y. Regression
against the previous frozen snapshot fails at `positive PS2 ninth-bit motion
decode failed`; identical test with corrected RTL passes (5 events, overflow
and dropped-event checks preserved). Physical mouse acceptance remains open.
Sender reference: https://github.com/MiSTer-devel/Main_MiSTer/blob/master/user_io.cpp

The obsolete controller-only FPGA build was deliberately cancelled during fit.
Its source/logs remain at `.work/goal-fpga-controller-20260909`; do not package it.
The replacement snapshot `.work/goal-fpga-controller-mouse-20260909` includes the
mouse correction and explicit controller button contract; compilation is active.

ARM intermediate build completed with recorded exit 0 in
`/tmp/diablo-controls-final-build.exit`; its log records executable linking.
Started the required admission/headless-hint incremental pass with separate
`/tmp/diablo-controls-admission-build.log` and `.exit` evidence. Accept only the
output after this pass succeeds and generated overlays are verified.

Latest ARM modifier pass also completed with exit 0. Generated main matches
`mister_main.cpp` exactly; build rules compile both admission overlays. Retained
engine: `.work/build/arm-controls-mouse-20260909/devilutionx.arm`, 8727440 bytes,
SHA256 `aa28f7cda491dccea5c16c411e7f62247626a482432d81671e074dbd2c3cfffa`.

Seed-2 FPGA compile/compression succeeded but four-corner timing rejected it:
three scaler setup paths fail in one slow corner, worst -0.254 ns from
`ascal|o_hacc[0]` to `ascal|o_dir[0][10]`. RBF SHA256
`f9190b74f8d81c6265e28ee405818a1cf8ba5d67f1b81908730831c062c13de8`
is NOT deployable. Started placement seed 3 in
`.work/goal-fpga-controller-mouse-seed3-20260909`; RTL and SDC unchanged.

Seed 3 passed compile/compression and all four-corner timing checks: 148 numeric
summary entries, none negative; minimum setup 0.176 ns, hold 0.087 ns. Detailed
setup report contains no violated paths. Compressed RBF: 2776932 bytes, SHA256
`474fd8950f665dc4fdf078c8b542360cbcb38f994b3f3ff40819a4754ce05085`.
This supersedes rejected seed 2; candidate packaging/deployment remains pending.

Broad local verification attempt was terminated by the outer 240-second timeout
without a receipt. Verified no surviving task child before rerunning with a
persistent log at `.work/local-controls-verification-20260909.log`; await the
runner's own receipt. This timeout is not a passing or failing test result.

The final controls candidate is deployed and running for user testing. After the pre-existing frontend disappeared, a direct launcher-owned core remained stable for at least 45 seconds: launcher PID 1406, MiSTer RBF PID 1323 and engine PID 1411, with FPGA state `operating`. Runtime evidence is retained locally under `.work/target-controls-final-20260909/` and on target at `/tmp/diablo-controls-final-runtime/engine.log`. Remaining work is physical input/cursor observation plus the broader plan's performance, menu, campaign, save/relaunch, multiplayer, endurance and release-closure gates.

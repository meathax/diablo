# Diablo MiSTer core — focused completion plan

Updated 9 September 2026. This is the active plan; detailed historical audit material and receipts remain under `reports/` and `.mister/evidence/`.

## Working rule

- Iterate with focused host/RTL simulation first. Build Quartus/RBF only for a real RTL change; use MiSTer only for physical acceptance.
- Do not repeat broad audit matrices or long verification runs unless a focused check or hardware observation finds a regression.
- Multiplayer stays disabled and is out of scope for this release.

## Already working

- Core boots and runs the supplied Diablo/Hellfire data from `game/Diablo` / `/media/fat/games/Diablo`.
- Cinematic, menus, gameplay path and presentation are working.
- Xbox One-style dual-analog mapping is implemented: independent sticks, D-pad, buttons, triggers and guide/menu controls.
- Keyboard and mouse input are implemented, including visible mouse behaviour shared with controller UI use.
- OSD accept mapping is repaired; debug/test OSD rows and the cancelled mouse-toggle option are removed.
- C34 ownership cleanup is closed. Icarus RTL, WSL Verilator and host SDL/transport checks pass.
- Single-player ARM package is built, verified on MiSTer and activated with rollback retained; networking and the Multi Player menu entry are removed.

## Only remaining work

1. Physical smoke test on the current candidate:
   - Ensure the attached 8BitDo controller is paired/active first; the latest target inventory sees two `2dc8:301c` receivers in `IDLE` state with HID raw nodes but no gamepad event node.
   - Launch Diablo and Hellfire.
   - Confirm menu navigation, character movement, both sticks, D-pad/buttons, keyboard, mouse, cinematic and OSD selection.

2. Short real gameplay/audio check:
   - 60 FPS pacing, lighting-off default and unused SDL blit removal are deployed. Confirm reported walking judder improved in a short walking session; only pursue measured remaining bottlenecks.
   - Play enough of each campaign to catch visible frame problems or audible dropouts.
   - If stable, keep the current PCM diagnostic fix; do not pursue artificial endurance tuning.

3. Release closeout:
   - Single-player build, final package verification and the candidate-specific deployment lifecycle are complete; keep the recorded rollback release.
   - The exact active candidate now has an automated relaunch/save-load pass; retain the physical relaunch observation in the hands-on smoke gate.
   - Keep the prior release for rollback, verify the final package/hash, and update `PROGRESS.md`.

## Exit condition

Both campaigns launch and are playable with the required controller, keyboard and mouse controls; video/cinematics/audio are stable in a short real session; relaunch and save/load work; final package and rollback are retained. Multiplayer remains disabled.

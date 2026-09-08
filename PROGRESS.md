# Diablo MiSTer — current progress

This file is the concise status handoff. The authoritative implementation and acceptance plan is [PLAN.md](PLAN.md), which retains every C01–C34 and R01–R13 procedure. Scheduling and historical plan narrative moved to [the archived plan history](reports/audit-2026-09-07/archive/PLAN_HISTORY.md); the former long-form guide is preserved at [the archived historical guide](reports/audit-2026-09-07/archive/HISTORICAL_COMPLETION_GUIDE.md). Immutable receipts remain in their original locations.

## Status — 8 September 2026

- The workspace is implementation-active. No accepted release or current accepted candidate exists.
- The HDMI output is the required physical scope. CRT/direct-video paths remain implemented but explicitly untested and unqualified; their source and mux safety checks remain required.
- The local verification packet, endpoint-aligned ARM replay, cinematic repair, and PCM underflow-event diagnostic implementation are recorded. PCM commit `9bf880a` is diagnostic-only: the 48-byte snapshot tail at ABI offset 424 has independent player, long-queue, arbiter, integrated, host ABI and state-dump checks, but it does not prove physical sound quality or close C15.
- The reproducible `9bf880a` FPGA build packet now has a source-bound compile, timing and compressed-artifact receipt. Independent review, MiSTer deployment, active-load PCM attribution/endurance, controller and multiplayer workflows, and the remaining C01–C34/R01–R13 integrated, physical and release evidence remain open.
- The user reports that gameplay and audio are good for the observed session. That observation is retained separately from counter-based diagnostic evidence and does not close endurance, stereo or release gates.

## Next actions

1. Independently review the reproducible FPGA compile, timing and compressed artifact for PCM commit `9bf880a` in `.work/goal-pcm-fpga-9bf880a`; preserve source identity, timing-corner evidence, warnings, inference changes and hashes before any target deployment.
2. Use the accepted diagnostic artifact for a candidate-bound integrated trace. Record event snapshots with queue/fetch/producer/player/DDR-arbiter state and split startup, reset and steady phases; do not infer audible quality from counters alone.
3. Implement the exact custom Xbox preset in [PLAN.md](PLAN.md#controller-mapping-contract--custom-xbox-preset). Complete the C10/C11 focus and modifier checks, C12 cursor/mouse-mask checks, and C24 controller-only/multiplayer workflows with candidate-bound receipts. Preserve RT quick-spell, panel-priority, safe carried-item cancellation, precision cursor, Guide/OSD and usability requirements exactly.
4. Continue the HDMI, campaign/save/relaunch, performance/latency, lifecycle, C25 external timing/configuration and remaining R01–R13 closure work. Keep missing measurements blocked and do not promote development artifacts to release evidence.

## Evidence rules

Reuse an artifact only when its complete relevant source, tool, configuration and identity inputs match. Keep implementation completion separate from hardware and release acceptance. Update this handoff when a bounded receipt lands; do not rewrite historical receipts or convert an observation into a gate pass.

## FPGA build receipt — `9bf880a`

- Snapshot: `.work/goal-pcm-fpga-9bf880a`; source admission found no tracked or untracked changes in its 11 source inputs. Its 85-file manifest rechecked with zero mismatches after compression: [build-packet-validation.json](.work/goal-pcm-fpga-9bf880a/build-packet-validation.json), manifest SHA-256 `2B5BE1E0DEC4A37610696D3C636BE7DBDC74D4539F5CDF4134749092A2763309`.
- Exact staged commands were:

  ```powershell
  & 'D:\Arcade\AI\aCORES\Diablo\support\scripts\compile_fpga_snapshot.ps1' -SourceDirectory 'D:\Arcade\AI\aCORES\Diablo\.work\goal-pcm-fpga-9bf880a' -Action sync     -RepositoryDirectory 'D:\Arcade\AI\aCORES\Diablo' -QuartusRoot 'D:\q17\quartus'
  & 'D:\Arcade\AI\aCORES\Diablo\support\scripts\compile_fpga_snapshot.ps1' -SourceDirectory 'D:\Arcade\AI\aCORES\Diablo\.work\goal-pcm-fpga-9bf880a' -Action compile  -RepositoryDirectory 'D:\Arcade\AI\aCORES\Diablo' -QuartusRoot 'D:\q17\quartus'
  & 'D:\Arcade\AI\aCORES\Diablo\support\scripts\compile_fpga_snapshot.ps1' -SourceDirectory 'D:\Arcade\AI\aCORES\Diablo\.work\goal-pcm-fpga-9bf880a' -Action timing   -RepositoryDirectory 'D:\Arcade\AI\aCORES\Diablo' -QuartusRoot 'D:\q17\quartus'
  & 'D:\Arcade\AI\aCORES\Diablo\support\scripts\compile_fpga_snapshot.ps1' -SourceDirectory 'D:\Arcade\AI\aCORES\Diablo\.work\goal-pcm-fpga-9bf880a' -Action compress -RepositoryDirectory 'D:\Arcade\AI\aCORES\Diablo' -QuartusRoot 'D:\q17\quartus'
  ```

  The durable PowerShell 7 runner results are recorded in the receipt.
- Compile retry: Quartus full compilation succeeded with 0 errors and 127 warnings. Dedicated timing succeeded with 0 violated setup paths; four timing-corner WNS values were `0.210`, `0.188`, `0.529`, and `0.526` ns. The compile log still reports that the broader design is not fully constrained for setup and hold.
- Output: `output_files/Diablo.compressed.rbf` and `Diablo.rbf` are each 2,738,092 bytes with SHA-256 `1D87BA18A012D15813B8E5F83AA32A4DD531537292082FA3B888CD5059E77FE7`; `Diablo.sof` SHA-256 is `83F34FB625B0741283915EA8CFA74EFF5826724517C04A9FED8799FE4201C2D9`. Fitter use is 28% ALMs, 16% memory bits, 21% RAM blocks, 33% DSPs and 50% PLLs. Timing, fitter, log and artifact paths/hashes are in the receipt.
- The initial direct compile attempt was interrupted during Fitter execution. Its log and generated directories were preserved under `.work/goal-pcm-fpga-9bf880a/attempts/` before the clean durable retry; no target was deployed.

## Root review — diagnostic FPGA

- Root took ownership under the user instruction to handle difficult/failed work directly. Compared map/fitter warnings against `.work/c26-fpga-0232f7`: no new normalized warnings; unconstrained external endpoints unchanged.
- Checked all 16 four-corner setup/hold/recovery/removal summaries: positive slack (minimum 0.106 ns), zero negative TNS. Verified all 18 recorded artifact hashes. Accepted only for diagnostic development deployment; C25 external timing and release acceptance remain open.
- Evidence: `.work/goal-pcm-fpga-9bf880a/root-development-review.json`. No target deployment yet. Next: prepare an identity-bound diagnostic package and safely obtain the underflow event; root also owns the failed scene-capture work.

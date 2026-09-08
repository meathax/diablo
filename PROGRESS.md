# Diablo MiSTer — current progress

This file is the concise status handoff. The authoritative implementation and acceptance plan is [PLAN.md](PLAN.md), which retains every C01–C34 and R01–R13 procedure. Scheduling and historical plan narrative moved to [the archived plan history](reports/audit-2026-09-07/archive/PLAN_HISTORY.md); the former long-form guide is preserved at [the archived historical guide](reports/audit-2026-09-07/archive/HISTORICAL_COMPLETION_GUIDE.md). Immutable receipts remain in their original locations.

## Status — 8 September 2026

- The workspace is implementation-active. No accepted release or current accepted candidate exists.
- The HDMI output is the required physical scope. CRT/direct-video paths remain implemented but explicitly untested and unqualified; their source and mux safety checks remain required.
- The local verification packet, endpoint-aligned ARM replay, cinematic repair, and PCM underflow-event diagnostic implementation are recorded. PCM commit `9bf880a` is diagnostic-only: the 48-byte snapshot tail at ABI offset 424 has independent player, long-queue, arbiter, integrated, host ABI and state-dump checks, but it does not prove physical sound quality or close C15.
- Candidate-bound FPGA qualification for `9bf880a`, active-load PCM attribution/endurance, the remaining controller and multiplayer workflows, and the other C01–C34/R01–R13 integrated, physical and release evidence remain open.
- The user reports that gameplay and audio are good for the observed session. That observation is retained separately from counter-based diagnostic evidence and does not close endurance, stereo or release gates.

## Next actions

1. Finish and independently review the reproducible FPGA compile, timing and compressed artifact for PCM commit `9bf880a` in `.work/goal-pcm-fpga-9bf880a`; preserve source identity, timing-corner evidence, warnings, inference changes and hashes.
2. Use the accepted diagnostic artifact for a candidate-bound integrated trace. Record event snapshots with queue/fetch/producer/player/DDR-arbiter state and split startup, reset and steady phases; do not infer audible quality from counters alone.
3. Implement the exact custom Xbox preset in [PLAN.md](PLAN.md#controller-mapping-contract--custom-xbox-preset). Complete the C10/C11 focus and modifier checks, C12 cursor/mouse-mask checks, and C24 controller-only/multiplayer workflows with candidate-bound receipts. Preserve RT quick-spell, panel-priority, safe carried-item cancellation, precision cursor, Guide/OSD and usability requirements exactly.
4. Continue the HDMI, campaign/save/relaunch, performance/latency, lifecycle, C25 external timing/configuration and remaining R01–R13 closure work. Keep missing measurements blocked and do not promote development artifacts to release evidence.

## Evidence rules

Reuse an artifact only when its complete relevant source, tool, configuration and identity inputs match. Keep implementation completion separate from hardware and release acceptance. Update this handoff when a bounded receipt lands; do not rewrite historical receipts or convert an observation into a gate pass.

# Completion audit refresh — 7 September 2026

## Verdict and scope

The project is an implemented ARM/FPGA prototype with useful local regressions,
not an accepted complete MiSTer release. The original F01–F18 audit is historical:
many fixes have since been implemented. Preserve its reproductions and the
C01–C34 work packages; do not rediscover or rewrite those fixes without a failing
current regression. No physical qualification is inferred from dummy SDL,
QEMU, a successful compiler, a frame acknowledgement, or a sampled checksum.

This refresh inventories 1,134 Git-visible tracked/untracked paths, including
151 candidate source inputs and all four recorded candidate artifacts. It
examines current transport/rendering changes, RTL/integration coverage, launcher,
candidate/evidence validation, tests, planning and qualification contracts.
The inventory includes generated evidence; this is not 1,134 independently
reviewed implementation files. Upstream engine/framework internals are covered
at integration boundaries and by existing tests, not a line-by-line proof of
every vendor file. Ignored commercial MPQs and build caches were not exhaustively
read. No board was changed, no new FPGA/ARM build was performed, and no gameplay,
timing or physical performance acceptance was granted.

Evidence: [inventory](refresh-evidence/inventory.json),
[inventory helper](refresh_audit.cjs). Existing staged/unstaged work was preserved.
The Git index changed during review; treat the receipts below as bounded local
observations, not as a frozen release-candidate endorsement.

## New findings and required fixes

| ID | Priority / classification | Evidence and effect | Required fix and acceptance | Work packages |
| --- | --- | --- | --- | --- |
| R01 | P1, reproduced candidate/provenance blocker | Candidate `a1fc74f…` retains matching artifact hashes, but nine source inputs differ. Candidate-bound verification fails before running tests. The plan/state still direct work toward that candidate as current. | Preserve the old manifest/receipts as historical. Freeze current implementation, run matching local/ARM checks, rebuild changed ARM and FPGA inputs, close timing, generate a new immutable manifest, and verify it before loading. Never relabel the old RBF with new RTL hashes. | C18/C25/C27/C29/C30 |
| R02 | P1, reproduced false-positive release gate | `closure_gates.py:168–202,205–266` checks receipt envelope labels and file hashes, but does not check artifact meaning, required per-test results/log integrity, candidate validity or measured thresholds. Synthetic evidence with failed checks, 1 FPS, 9999 ms p99 and no candidate ID returns `eligible: true`. | Add typed evidence schemas/validators, mandatory current candidate identity for release, required result IDs with pass/no-skip rules, transitive log verification, and numeric/coverage evaluation against the matrix. Treat missing/NaN measurements, wrong candidate, failed/skipped steps and arbitrary hash-valid JSON as failures. Reject duplicate evidence IDs. Keep approved scope exceptions separate from an unqualified full-completion claim. | C18/C21/C25/C29/C31/C32 |
| R03 | P1, reproduced receipt/source race | `verification.py:293–347` snapshots inputs before tests, then publishes without checking them again. A passing step that changes its input yields a passing receipt bound to the old bytes. | Prefer tests against an immutable source snapshot and isolated outputs. Also recompute source/dependency and candidate/artifact identities immediately before publication; mark any drift invalid, retain before/after hashes, and block promotion. A pre/post comparison alone does not prevent change-and-revert races; snapshot isolation is the final solution. Test source, header, test, ABI, artifact and Git-identity mutation during execution. | C18/C27/C28/C29 |
| R04 | P1, code-confirmed clean-install blocker | `diablo_launch.py:243–259` calls development `candidate_manifest.verify_manifest`; that verifier (`candidate_manifest.py:197–224`) walks build source inputs and recomputes Git identity. The intended runtime-only package cannot satisfy that development-checkout contract by simply copying ARM/RBF files. | Keep strict development verification. Add a separate immutable deployment manifest binding release/build provenance, installed relative files, ARM/RBF/ABI hashes, supported board profile and dependencies. Runtime admission validates that deployment contract without a developer checkout or Git. Test relocated clean media with no `.git`, `.work`, compiler or donor tree; reject swapped/missing artifacts and wrong ABI. Prove the selected launcher language/dependencies exist on the supported MiSTer image. | C16/C18/C26/C32 |
| R05 | P1, missing implementation / qualification blocker | `verification.py:245–246` always returns board `not_run`; supplying a board configuration does not implement a board runner. The launcher is a generic loader/ready-file supervisor, not a proven MiSTer menu integration. | Implement a project-owned target adapter and concrete loader/menu profile. Bind board identity, current boot, reserved DDR proof, loaded artifact identity and installed engine hashes before a run. Capture required machine counters plus physical observer/capture evidence. Fail incomplete observations; return to a known-safe state on timeout. Add fake-target protocol tests, then the real-board matrix. | C16/C17/C23/C24/C28/C29/C32 |

R02 does not imply historical hardware evidence was fabricated. It proves the
current evaluator cannot establish the semantic claim its `eligible` field makes.
R03 likewise establishes an admission defect, not proof that every old receipt
was affected.

### Exact reproductions

- [Closure semantics reproduction](repro_closure_semantics.py) creates only
  temporary synthetic evidence; [result](refresh-evidence/closure-semantics.json)
  records `eligible: true` when false is required.
- [Source-mutation reproduction](repro_verification_mutation.py) uses the real
  receipt runner with a temporary input and narrowed step selection;
  [result](refresh-evidence/verification-mutation.json) records exit 0/pass with
  different pre-run and post-run source IDs.
- [Candidate rejection receipt](../../.mister/evidence/receipts/20260907T073141Z-92034273-fd47-4c57-b1f8-ef57d73279bb.json)
  records the R01 failure. The four artifact files still match their old manifest;
  this is source drift, not evidence that those binaries were modified.

The nine changed inputs are `rtl/diablo_command_consumer.sv`,
`rtl/diablo_input_capture.sv`, `rtl/diablo_pcm_player.sv`,
`rtl/diablo_transport_ddram_arbiter.sv`,
`support/reference/mister_command_scene.hpp`,
`support/reference/mister_transport.hpp`,
`support/reference/mister_transport_sdl.hpp`,
`support/scripts/candidate_manifest.py`, and
`support/transport/transport_header_probe.cpp`.

## Current implementation and open acceptance

| Area | Current evidence / implementation | Remaining acceptance |
| --- | --- | --- |
| Changed-run renderer, cache coherence and clipping | Sentinel/bounds checks and mixed-writer invalidation exist; renderer regressions pass. Original F01/F02/F17 are not blindly relisted as unfixed. | Exact complete indexed pixels, palette, metadata and displayed RGB for both campaigns across command, dirty and full-copy transitions. |
| Scanout, ownership, palette | Preparation/reclamation and guarded palette/base handoff exist; scanout fixture passes. | Scaler-integrated RGB atomicity, missed/deferred blanking commits, sustained cadence and reset under DDR pressure on the actual candidate. |
| Command, PCM, input and reset | Asynchronous submission ownership, recovery coordination, focus/input translation and integrated DDR fixture exist. | Late fence/fault/reset interleavings; physical OSD, text, reconnect and held-key release; audible output with zero steady-play underruns. |
| Video-mode policy | Gameplay/diagnostic source policy exists. | Enumerate HDMI, analog-through-scaler and any required native/direct-video path separately. A test pattern or forced scaler does not prove a promised bypass mode. Implement missing required paths before closure. |
| Build/reproducibility | Build scripts, manifests, timing contracts and staged implementation are present. | Final source freeze, clean checkout rebuild, exact all-corner timing/inference/endpoints, deployment contract and clean install. The original untracked-source count is historical; staging alone is not clean-clone acceptance. |
| Performance/gameplay | Historical board runs establish bring-up, not this candidate's acceptance. | Real deterministic scenes, frame-time tails and input latency, campaign progression/endings, controller-only play, multiplayer, storage/recovery and endurance. |

## Fresh local checks

[Local receipt](../../.mister/evidence/receipts/20260907T073534Z-3ef5ef4b-24f6-4468-9bc7-9c50d4a775db.json):
104 Python tests ran, one symlink-creation test skipped for Windows privilege;
four registered host checks and thirteen RTL fixtures passed. The overall runner
correctly returned **incomplete**, because host PNG and SDL input paths were not
configured. It was run without a candidate manifest and cannot promote a target
candidate. The skipped symlink test must run on a capable environment before
admission qualification.

Both optional checks subsequently passed (exit 0) using the previously recorded
explicit local paths: two host PNG cases and the SDL transport input fixture.
Their commands/results live in
[optional-checks.json](refresh-evidence/optional-checks.json). These supplemental
checks do not retroactively change the immutable incomplete receipt. Plan/state
consistency, gate-matrix structure and local Markdown links also pass; `git diff
--check` returns 0. Structural gate validation does not fix R02. The first
unbound local verification invocation exceeded the Capsule call window and
returned no receipt at inspection; the retained completed invocation is the one
cited above. Context Mode repeatedly failed on its metrics-file rename, so
bounded Capsule execution and file-backed evidence were used.

## Planning disposition

No production RTL, engine or runtime fix is claimed by this planning update.
R01–R05 are mandatory additions to the existing C packages, not a competing
renumbered backlog. The [root execution guide](../../CORE_COMPLETION_AUDIT.md)
gives the critical path; [PROPOSED_PLAN.md](PROPOSED_PLAN.md) retains detailed
implementation and closure procedures. Only a fresh immutable candidate with
all required physical, correctness, performance and install evidence may be
described as complete.

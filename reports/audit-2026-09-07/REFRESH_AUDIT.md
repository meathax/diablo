# Completion audit refresh — 7 September 2026

## Verdict and scope

The project is an implemented ARM/FPGA prototype with useful local regressions,
not an accepted complete MiSTer release. The original F01–F18 audit is historical:
many fixes have since been implemented. Preserve its reproductions and the
C01–C34 work packages; do not rediscover or rewrite those fixes without a failing
current regression. No physical qualification is inferred from dummy SDL,
QEMU, a successful compiler, a frame acknowledgement, or a sampled checksum.

This refresh inventories the current transport/rendering changes, RTL/integration
coverage, launcher, candidate/evidence validation, tests, planning and
qualification contracts. Candidate27 now contains 194 source inputs and five
recorded candidate artifacts; historical inventory counts remain in the earlier
audit evidence.
The inventory includes generated evidence; this is not 1,134 independently
reviewed implementation files. Upstream engine/framework internals are covered
at integration boundaries and by existing tests, not a line-by-line proof of
every vendor file. Ignored commercial MPQs and build caches were not exhaustively
read. Candidate27's FPGA bytes were rebuilt directly from the clean snapshot
and its ARM transport artifact was rebuilt from the pinned ARM checkout with
the portable toolchain. The separate ARM-reference artifact remains the
software-scene role. No core was activated and no existing board artifact was
overwritten; no gameplay or physical performance acceptance was granted.

Evidence: [inventory](refresh-evidence/inventory.json),
[inventory helper](refresh_audit.cjs). Existing staged/unstaged work was preserved.
The Git index changed during review; treat the receipts below as bounded local
observations, not as a frozen release-candidate endorsement. A real MiSTer SD
share was read and a unique candidate package directory was staged for hash
verification; no RBF was activated and no existing core or user data was
overwritten.

## New findings and required fixes

| ID | Priority / classification | Evidence and effect | Required fix and acceptance | Work packages |
| --- | --- | --- | --- | --- |
| R01 | P1, reproduced candidate/provenance blocker | Candidate `a1fc74f…` retains matching artifact hashes, but nine source inputs differ. Candidate-bound verification fails before running tests. The plan/state still direct work toward that candidate as current. | Preserve the old manifest/receipts as historical. Freeze current implementation, run matching local/ARM checks, rebuild changed ARM and FPGA inputs, close timing, generate a new immutable manifest, and verify it before loading. Never relabel the old RBF with new RTL hashes. | C18/C25/C27/C29/C30 |
| R02 | P1, reproduced false-positive release gate | `closure_gates.py:168–202,205–266` checks receipt envelope labels and file hashes, but does not check artifact meaning, required per-test results/log integrity, candidate validity or measured thresholds. Synthetic evidence with failed checks, 1 FPS, 9999 ms p99 and no candidate ID returns `eligible: true`. | Add typed evidence schemas/validators, mandatory current candidate identity for release, required result IDs with pass/no-skip rules, transitive log verification, and numeric/coverage evaluation against the matrix. Treat missing/NaN measurements, wrong candidate, failed/skipped steps and arbitrary hash-valid JSON as failures. Reject duplicate evidence IDs. Keep approved scope exceptions separate from an unqualified full-completion claim. | C18/C21/C25/C29/C31/C32 |
| R03 | P1, reproduced receipt/source race | `verification.py:293–347` snapshots inputs before tests, then publishes without checking them again. A passing step that changes its input yields a passing receipt bound to the old bytes. | Prefer tests against an immutable source snapshot and isolated outputs. Also recompute source/dependency and candidate/artifact identities immediately before publication; mark any drift invalid, retain before/after hashes, and block promotion. A pre/post comparison alone does not prevent change-and-revert races; snapshot isolation is the final solution. Test source, header, test, ABI, artifact and Git-identity mutation during execution. | C18/C27/C28/C29 |
| R04 | P1, code-confirmed clean-install blocker | `diablo_launch.py:243–259` calls development `candidate_manifest.verify_manifest`; that verifier (`candidate_manifest.py:197–224`) walks build source inputs and recomputes Git identity. The intended runtime-only package cannot satisfy that development-checkout contract by simply copying ARM/RBF files. | Keep strict development verification. Add a separate immutable deployment manifest binding release/build provenance, installed relative files, ARM/RBF/ABI hashes, supported board profile and dependencies. Runtime admission validates that deployment contract without a developer checkout or Git. Test relocated clean media with no `.git`, `.work`, compiler or donor tree; reject swapped/missing artifacts and wrong ABI. Prove the selected launcher language/dependencies exist on the supported MiSTer image. | C16/C18/C26/C32 |
| R05 | P1, missing implementation / qualification blocker | `verification.py:245–246` always returns board `not_run`; supplying a board configuration does not implement a board runner. The launcher is a generic loader/ready-file supervisor, not a proven MiSTer menu integration. | Implement a project-owned target adapter and concrete loader/menu profile. Bind board identity, current boot, reserved DDR proof, loaded artifact identity and installed engine hashes before a run. Capture required machine counters plus physical observer/capture evidence. Fail incomplete observations; return to a known-safe state on timeout. Add fake-target protocol tests, then the real-board matrix. | C16/C17/C23/C24/C28/C29/C32 |
| R06 | P1, reproduced candidate identity parser defect | `candidate_manifest.py` used `str.strip()` on Git porcelain output, which removed the first line's leading status column and could make a fresh manifest fail its own verification when the first changed path was worktree-only. | Trim only CR/LF terminators, add a leading-space regression, regenerate the candidate and rerun all candidate-bound receipts. Keep the MiSTer layout probe rooted at the actual target (`MiSTer.ini` is at SD-card root) and test the read-only deployment preflight against the staged package. | C18/C26/C28/C29/C32 |
| R07 | P2, preflight metadata-integrity gap | `mister_preflight.verify_remote_package` checked the four files listed by the local package manifest but did not compare the remote `package-manifest.json` itself. A swapped metadata file could therefore pass the automated preflight while the runtime files still matched. | Hash/size-check the remote package manifest before consuming its records, reject missing or tampered metadata, add a regression test, regenerate the candidate and rerun the staged preflight. | C28/C29/C32 |
| R08 | P1, clean-checkout reproducibility fixture dependency | A detached checkout with the intended source overlay failed 13 tests because the FPGA snapshot test assumed `.work/build` existed and launcher tests assumed ignored generated `build_id.v` existed. The implementation was correct, but the verification entry point was not self-contained from a clean checkout. | Bootstrap a temporary build directory and deterministic `build_id.v` inside the affected tests, remove both in teardown, and retain a clean-checkout receipt. Keep clean Quartus/ARM rebuild and source review/commit as separate acceptance gates. | C26/C27/C28/C29 |
| R09 | P1, Quartus generated-input mutation | `sys/build_id.tcl` rewrites `build_id.v` during the Quartus pre-flow stage. The first clean snapshot compile therefore made the following compression/timing actions reject their own manifest. | Back up and restore generated snapshot inputs around every native Quartus action, add a regression, and prove direct compile/compression/timing from the same clean snapshot with all reported setup corners passing. | C18/C26/C27/C28/C29 |
| R10 | P1, output-mode timing and physical qualification | The former `sys/scandoubler.v:20` VSync TODO is replaced by an explicit progressive 31 kHz disposition: VSync/VBlank use the same input-hsync pipeline and Hq2x colour mode is deterministic. Candidate43 has fresh four-corner Quartus setup evidence, but no connector capture or sync/geometry observation exists yet. | Keep the exact HDMI framebuffer/scaler, direct RGB and analog/scandoubler rows separate. Add/retain mode-matrix RTL checks and capture gameplay, sync, geometry and RGB order on every advertised connector using candidate43. Reopen C25/C31 on any mismatch; keep diagnostic pattern evidence separate from gameplay evidence. | C13/C25/C31 |
| R11 | P1, ARM role/evidence mismatch | The clean deployable `arm-transport.cmake` binary is intentionally built without the `arm-reference.cmake` native-scenario hooks. Running the clean transport binary with `DIABLO_NATIVE_SCENARIO` timed out with no captures, while the separately identified reference build passes the scene oracle. Treating those binaries as interchangeable would either hide a real packaging problem or falsely bind scene evidence to the deployment artifact. | Add an explicit `build_role`/recipe/hash record to scene and candidate evidence. Use ARM-reference only for host-vs-ARM software equality, ARM-transport for ABI/QEMU and board qualification, and reject role/hash mismatches. Candidate27's clean ARM receipt documents the split; the next implementation should add schema and regression coverage before release. | C18/C19/C26/C28/C29 |
| R12 | P2, stale diagnostic | `support/scripts/verification.py:315` still says a board adapter is intentionally not implemented, even though the configured board branch calls `board_runner.run_configuration` and the board package exists. The stale reason can mislead operators and hides the distinction between missing configuration and a configured runner result. | Replace the fallback reason with the actual unsupported-suite/configuration explanation, add a regression for missing versus configured board setup, and rerun candidate-bound verification receipts. | C28/C29 |

The target preflight also caught a separate layout assumption before any release
claim: the observed MiSTer stores `MiSTer.ini` at the SD-card root, not under
`config/`. `mister_preflight.py` now probes the real layout and candidate27's
preflight proves the corrected path. This was fixed before the current candidate
was regenerated; it remains a deployment-probe regression risk if a future
target profile changes its filesystem assumptions.

R02 does not imply historical hardware evidence was fabricated. It proves the
current evaluator cannot establish the semantic claim its `eligible` field makes.
R03 likewise establishes an admission defect, not proof that every old receipt
was affected.

## Implementation update

The mandatory local fixes from this refresh are now implemented and covered by
regressions:

- R02: `closure_gates.py` requires typed artifact schemas, a current non-null
  candidate/source identity, pass-only receipt results, unique evidence IDs,
  verified result logs, physical coverage, timing completeness and numeric
  performance thresholds. The synthetic failing-evidence reproduction now stays
  ineligible for the semantic reasons under test.
- R03: `verification.py` copies the declared dependency inputs to an isolated
  snapshot, runs host/RTL tests there, checks the snapshot and original checkout
  before publication, and revalidates a candidate manifest. The mutation
  regression now fails with a `source-integrity` result while leaving the source
  checkout unchanged.
- R04: `deployment_manifest.py` defines a runtime-only, hash-bound manifest for
  the ARM binary, RBF, ABI and board profile. `diablo_launch.py` accepts it and
  validates a package without a Git checkout; mutation/private-data tests pass.
- R05: `board_runner.py` provides the project-owned no-shell target adapter. It
  rejects missing/mismatched candidates, failed commands and missing physical
  observations, and records bounded immutable logs. `mister_preflight.py` adds a
  read-only SMB/package hash check and target probe; real board configuration and
  observations are still required for a board pass.
- C32: `package_release.py` now builds a runtime-only package containing exactly
  the engine, RBF, ABI and two manifests; it refuses overwrite, symlinks,
  private-data-looking files and hash drift. Clean-image install, update,
  rollback and second-launch observations remain hardware/release gates.
- R07: `mister_preflight.py` now verifies the remote `package-manifest.json`
  itself by size/SHA-256 before trusting its listed files; the missing/tampered
  metadata regression passes. Candidate27's preflight binds all five package
  files, while physical installation and launch evidence remain open.
- R08: `test_compile_fpga_snapshot.py` now creates/removes its temporary
  `.work/build`, and `test_diablo_launch.py` now creates/removes deterministic
  temporary `build_id.v`. A detached clean-checkout overlay passes 129 tests
  with one declared skip; receipt
  `../../.mister/evidence/receipts/20260908T-clean-checkout-candidate26.json`
  has SHA-256 `382496e1f7ac129b208bc8ae4926506c6d622c580093feaff11eb62925ae54b7`.
- R09: `compile_fpga_snapshot.ps1` now restores `build_id.v` after each native
  Quartus action. Candidate26's clean FPGA receipt
  `../../.mister/evidence/receipts/20260908T-clean-fpga-build-candidate26.json`
  has SHA-256 `a93a9c9573ef838ccd703a1fa54a56989b4ae72fdcdf26ad741a5ce709f00842`;
  direct compile, compression and timing all exit 0, with zero setup violations
  in four reported corners and 0.014 ns minimum positive slack.
- R11: candidate27 includes a clean ARM transport build receipt
  `../../.mister/evidence/receipts/20260908T-clean-arm-build-candidate27.json`
  with SHA-256 `2355fd68ed569464d7ee604ab0405ed83fda3f3638db09dec670414658fa644b`.
  The attempted native-scene invocation of that transport role produced no
  captures by design; the scene oracle therefore records the separately built
  ARM-reference role and must keep the two hashes/recipes distinct.
- R12: the generic board fallback diagnostic now explains that --board-configuration is required and points to board_runner.py; test_verification.py covers it. Candidate33-bound receipts still need regeneration.

These changes invalidate the earlier candidate manifests because the source
identity includes the verification, launcher, packaging, build-helper and
verification-test inputs. Candidate33 was a historical development candidate after the C33
root-artifact cleanup rules, the R06 Git-status parser fix, the R07 package-
manifest preflight binding, the MiSTer root configuration probe fix and the
independent scene-oracle manifest-verification hardening. Its candidate-bound
local receipt covers foundation, host, RTL and integrated checks, the ARM/QEMU
receipt passes, both Diablo/Hellfire town scene-oracle receipts pass, and the
read-only deployment preflight matches all five staged package files on the
reachable target. The candidate identity is
`95eaf3535aaf52d55b63f85b9bc566178c8e24b0d6f00d1e29d28a54021bcaf8`, the
manifest SHA-256 is
`e83b4d6a3142ab930419bf04caf9f273df4d628619010906e51e7f0fd16a0f13`, and its
source identity is
`29e74b2685e333470ee383d40a977aa8b5a6da87a1a3d5106025890f1e9a42f4`.
The current receipts are recorded below; physical activation, gameplay and
performance receipts remain open and cannot be replaced by SMB staging.

### Exact reproductions

- [Closure semantics reproduction](repro_closure_semantics.py) creates only
  temporary synthetic evidence; [result](refresh-evidence/closure-semantics.json)
  records `eligible: false` because failed result semantics are rejected.
- [Source-mutation reproduction](repro_verification_mutation.py) uses the real
  receipt runner with a temporary input and narrowed step selection;
  [result](refresh-evidence/verification-mutation.json) records exit 1 with
  `isolated_snapshot_changed: true` while the original checkout stays unchanged.
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

## Historical implementation update (candidate33, 8 September 2026)

The v2 deployment/package contract is implemented. deployment_manifest.py binds
four fixed runtime roles (devilutionx, Diablo.rbf, transport_abi.hex,
diablo_launcher.py) and the complete asset tree; package_release.py verifies all
190 installed files, excludes private-looking paths and refuses symlinks. The
target launcher verifies that contract without a checkout, creates a current-boot
admission, passes the POSIX lease FD to the child and requires the MiSTer process
to carry the exact requested RBF path.

Candidate33 was a historical development snapshot: candidate ID
125520ca20750c1b8c67cc4e8448c433f2b837ebcacd8492a1150adb333d50a7, source ID
d46e14ca37d9aa2d9a244dd742d6ef3ecb29111617f4a75ccf0111f867da1929, manifest
SHA-256 f0ab6bee4630014486c48c7f4b252dc40f118489af6d3337926b26f646cfd15c.
The rebuilt ARM transport ELF is
b6a0b29676523bb91d3f5f55effe87fda8884b622423c6be81720a3eb33ae174; package33
and target preflight receipt ../../.mister/evidence/receipts/20260908T-preflight-candidate33b.json pass.
The current Python suite passes 131 tests with one declared Windows privilege skip.

The target normal launcher smoke is recorded in
../../.mister/evidence/receipts/20260908T-physical-launch-candidate31b.json:
package verification, current-boot admission, exact RBF process matching, FPGA
operating state and live frame publication pass. It deliberately does not close
video/audio/input/gameplay/performance. A candidate29/31 unpaced timedemo reboot
is preserved as a failure; candidate32 added 60 Hz transport pacing for --timedemo
and its first six seconds survived, but a complete pass receipt is still required.
Candidate33 carries the paced engine with the refreshed plan/source/package identity.
Physical capture/identity, PCM underrun, campaign, I/O, mode, performance and
clean-install gates remain open.

## Current implementation and open acceptance

| Area | Current evidence / implementation | Remaining acceptance |
| --- | --- | --- |
| Changed-run renderer, cache coherence and clipping | Sentinel/bounds checks and mixed-writer invalidation exist; renderer regressions pass. Original F01/F02/F17 are not blindly relisted as unfixed. | Exact complete indexed pixels, palette, metadata and displayed RGB for both campaigns across command, dirty and full-copy transitions. |
| Scanout, ownership, palette | Preparation/reclamation and guarded palette/base handoff exist; scanout fixture passes. | Scaler-integrated RGB atomicity, missed/deferred blanking commits, sustained cadence and reset under DDR pressure on the actual candidate. |
| Command, PCM, input and reset | Asynchronous submission ownership, recovery coordination, focus/input translation and integrated DDR fixture exist. | Late fence/fault/reset interleavings; physical OSD, text, reconnect and held-key release; audible output with zero steady-play underruns. |
| Video-mode policy | Gameplay/diagnostic source policy exists. | Enumerate HDMI, analog-through-scaler and any required native/direct-video path separately. A test pattern or forced scaler does not prove a promised bypass mode. Implement missing required paths before closure. |
| Build/reproducibility | Build scripts, manifests, timing contracts, runtime-only deployment validation, the atomic `package_release.py` builder and candidate-bound scene oracle are present; candidate27 package creation/verification, clean ARM transport build, clean direct Quartus compile/compression/timing and five-file read-only target preflight pass, and the Python foundation suite is self-contained from a clean checkout overlay. | Final source freeze/commit, role-aware scene schema, exact endpoint review beyond the reported setup corners, clean MiSTer install/update/rollback and second-launch evidence. Local package preflight is not physical target acceptance. |
| Performance/gameplay | Historical board runs establish bring-up, not this candidate's acceptance. | Real deterministic scenes, frame-time tails and input latency, campaign progression/endings, controller-only play, multiplayer, storage/recovery and endurance. |

## Fresh local checks

Historical candidate27 receipts:

- Local verification: [receipt](../../.mister/evidence/receipts/20260907T163914Z-2ac2bd6a-bae2-4739-938c-ed10ed28b557.json), SHA-256 `2b6238cdc2037f136d09ef6480575c445d1219457ca34dec4be0deb0e368e0d4`; 20 registered checks pass, including 129 foundation tests with one Windows privilege skip.
- ARM/QEMU transport-ABI verification: [receipt](../../.mister/evidence/receipts/20260907T163836Z-341002e5-50d2-4999-bae0-a83a5fe8351c.json), SHA-256 `7733003b414f9530481a630c9587714bb7e8f250c26b69aef6da7e8e8d6cc0e8`; the candidate manifest and source identity match candidate27.
- Clean ARM transport build: [receipt](../../.mister/evidence/receipts/20260908T-clean-arm-build-candidate27.json), SHA-256 `2355fd68ed569464d7ee604ab0405ed83fda3f3638db09dec670414658fa644b`; 8,518,704-byte ARMv7 ELF reproduced with the pinned portable toolchain.
- Diablo town oracle: [receipt](../../.mister/evidence/receipts/20260908T-scene-oracle-diablo-candidate27.json), SHA-256 `86af2b4e5d74bee51786d485a58c6b7350c17e46cb35a860107b0cfd49be3c30`; five native640 frames and all 256 RGB888 palette entries match exactly using the ARM-reference role.
- Hellfire town oracle: [receipt](../../.mister/evidence/receipts/20260908T-scene-oracle-hellfire-candidate27.json), SHA-256 `945c4b226a9cd62093fd2fc035a953d107309ff3f8cbc887602f3478e4a1b764`; five native640 frames and all 256 RGB888 palette entries match exactly using the ARM-reference role.
- Clean-checkout foundation: [receipt](../../.mister/evidence/receipts/20260908T-clean-checkout-candidate26.json), SHA-256 `382496e1f7ac129b208bc8ae4926506c6d622c580093feaff11eb62925ae54b7`; 129 tests pass with one declared skip after deterministic fixture bootstrap and teardown.
- Clean FPGA build: [receipt](../../.mister/evidence/receipts/20260908T-clean-fpga-build-candidate26.json), SHA-256 `a93a9c9573ef838ccd703a1fa54a56989b4ae72fdcdf26ad741a5ce709f00842`; direct compile, compression and timing pass with 0.014 ns minimum positive setup slack.
- Read-only target preflight: [receipt](../../.mister/evidence/receipts/20260908T-preflight-candidate27.json), SHA-256 `35372a252ce650e025f8fc10e4c1ae25a4ddf999743bdbd90543bc6d21143117`; all five staged package files and four baseline probes match on `\\192.168.0.69\sdcard\_CodexDiabloCandidate27`.

These receipts bind candidate `95eaf3535aaf52d55b63f85b9bc566178c8e24b0d6f00d1e29d28a54021bcaf8`, manifest SHA-256 `e83b4d6a3142ab930419bf04caf9f273df4d628619010906e51e7f0fd16a0f13` and source identity `29e74b2685e333470ee383d40a977aa8b5a6da87a1a3d5106025890f1e9a42f4`. They remain local/software/deployment-copy evidence; target activation, physical I/O, complete campaign coverage, measured performance and clean install/update/rollback remain open.

Historical candidate25 receipts:

- Local verification: [receipt](../../.mister/evidence/receipts/20260907T145145Z-9fdcba94-f5fe-48d6-80f1-722ae3c33d27.json), SHA-256 `235db6e6c2765ff7f4d9d4e82c3350c149b14ed61c09b760255f03a34372d8f4`; 20 registered checks pass, including 128 foundation tests with one Windows privilege skip.
- ARM/QEMU transport-ABI verification: [receipt](../../.mister/evidence/receipts/20260907T145928Z-8a3731f0-66b4-445f-8fc9-869a5f8b190f.json), SHA-256 `ef781dec13313daa1cc2ef90aba7703d08a2a6fee1707c567eb8191c2f58654a`; the candidate manifest and source identity match candidate25.
- Diablo town oracle: [receipt](../../.mister/evidence/receipts/20260908T-scene-oracle-diablo-candidate25.json), SHA-256 `e2af407063e98aad9346dbde7b461f00b1f44115b9c4c36fac8fcde416014abc`; five native640 frames and all 256 RGB888 palette entries match exactly.
- Hellfire town oracle: [receipt](../../.mister/evidence/receipts/20260908T-scene-oracle-hellfire-candidate25.json), SHA-256 `88d3c4f6300bdb8d516e3ded545219e37c9eb8224706f621e0b36f6c267597e3`; five native640 frames and all 256 RGB888 palette entries match exactly.
- Clean-checkout foundation: [receipt](../../.mister/evidence/receipts/20260908T-clean-checkout-candidate25.json), SHA-256 `4cb22e3a6f81c2f31d611d5a4d79285ae2d6333ca126356969fe87980c9c4262`; 128 tests pass with one declared skip after deterministic fixture bootstrap and teardown.
- Read-only target preflight: [receipt](../../.mister/evidence/receipts/20260908T-preflight-candidate25.json), SHA-256 `e2d8078a334fad539e08d37d06d148881289a6e2b635ceab64697b9c7aacd7dd`; all five staged package files and four baseline probes match on `\\192.168.0.69\sdcard\_CodexDiabloCandidate25`.

These receipts bind candidate `14eaf763fab2f4ced58d72dc095a03d65293f4609631a098a0f0eb5b5d162bdf`, manifest SHA-256 `27c4d2b04c0d00bab6aa3f3df04a33327f6107cc8b73dfd5baed37c631237416` and source identity `4ae4640bfc0888e7899eeac37e337f8a703e517ffff6a326b8e40a304c305797`. They remain local/software/deployment-copy evidence; target activation, physical I/O, complete campaign coverage, measured performance and clean install/update/rollback remain open.

[Historical candidate-24 local receipt](../../.mister/evidence/receipts/20260907T140421Z-4617cc3e-557c-4747-80d0-fc313b52982d.json):
the candidate-24 local suite passed all 20 registered foundation, host, SDL,
DDR, framebuffer, input, audio, integrated transport and RTL checks from its
isolated source snapshot. The receipt SHA-256 is
`98d36f13b240f8f2312150ae5d2a51521883eeb4aebece831724eb40f859d7b9`; its
foundation log records 125 Python tests with one Windows privilege skip. It
establishes local correctness for candidate-24; current target boot, physical
I/O, campaign coverage, measured board performance and clean install remain
open. Plan/state consistency, gate-matrix structure and Markdown links must be
rerun after every plan edit.

Historical candidate-24 ARM/QEMU tier passes at
`../../.mister/evidence/receipts/20260907T140805Z-52fffaf7-e6b5-4c6b-84bb-fdd92b507e8f.json`
(SHA-256 `b0d4c40b13d9d489061752d97113a218df3f8a997e0952d306e443379341c273`).
It binds candidate `01eda1749ecb4d747b9dba7e914a36939c66e05a3f61a617dda85569702c019c`,
manifest source identity
`d50f7c4f19ae8cb5156b09a22b2e95ebe39f7bbc8518a791486a7af293d3202f` and
receipt source snapshot `765764590737f77ad860753cadfb3973554ab782799c3aed8827aa3825e15110`;
the receipt proves the transport ABI under Cortex-A9 QEMU, not shared-DDR
reservation, target boot, physical I/O or gameplay acceptance.

Historical candidate-24 board-suite receipt is intentionally incomplete at
`../../.mister/evidence/receipts/20260907T140958Z-0abba2b0-e961-4e94-9400-03654860b94e.json`
(SHA-256 `38cbb9648b86f413f4a6220b80a3061ebdb12cdbf3f09ca4d32568e70fb69a7d`):
no physical board configuration was supplied, so `board-configuration` is
`not_run`. The separate read-only deployment preflight passes at
`../../.mister/evidence/receipts/20260907T-preflight-candidate24.json`
(SHA-256 `eeff62649f8a0c83f656bdbab56de546d68d7a1a41bacf0c3c8f291a0c9a38d6`):
the package files, including `package-manifest.json`, match on
`\\192.168.0.69\sdcard\_CodexDiabloCandidate24`, and `MiSTer`, `menu.rbf`, root
`MiSTer.ini` and `config/cores_recent.cfg` exist.
This proves deployment-copy integrity only; it cannot replace a loaded-core,
physical-observer or campaign receipt.

Historical candidate-24 scene oracle passes for both maintained town scenarios:
Diablo at `../../.mister/evidence/receipts/20260907T-scene-oracle-diablo-candidate24.json`
(SHA-256 `01a8c4682c8ebfe0e75e7c42e970bded823c64960f133f3cc1ee411ea14029f1`) and
Hellfire at `../../.mister/evidence/receipts/20260907T-scene-oracle-hellfire-candidate24.json`
(SHA-256 `dca0dd919dcd5d87bc853db20f5cd2f962c2b47123b55e2a48f7ac1aff7f94ed`).
They prove exact host-versus-ARM indexed/palette equality for five town frames
per campaign; FPGA readback and physical displayed-frame equality remain open.

## Planning disposition

R02–R09 now have project-owned local implementations and regression coverage;
R01 is represented by the current immutable candidate43 refresh. R10's local
disposition, exact output rows and fresh candidate43 timing evidence are now
recorded, but connector-level sync/geometry and gameplay captures remain open.
The candidate43 record also carries the MiSTer-root probe, bounded dot-path
fixes, package-manifest preflight binding, independent scene oracle, clean-
checkout fixture bootstrap and generated-input restoration. R11 documents the
intentional ARM transport/reference role split, and R12 remains implemented.
Neither changes the open physical acceptance gates.
These are
mandatory additions to the existing C packages, not a competing renumbered
backlog. The [root execution guide](../../CORE_COMPLETION_AUDIT.md) gives the
critical path; [PROPOSED_PLAN.md](PROPOSED_PLAN.md) retains detailed
implementation and closure procedures. Only a fresh immutable candidate with
all required physical, correctness, performance and install evidence may be
described as complete.

## Candidate38 historical continuation — 8 September 2026

Candidate38 was a historical development checkpoint after the PCM starvation and
packaging work. Its immutable candidate manifest is
`../../.mister/evidence/candidates/fpga-candidate-20260908-38-pcm-telemetry.json`
(SHA-256 `72bb8f0b456f026bdf3594a48f610e029cb0e6927fce7278d2fd64ee730e7d4`),
candidate ID
`8e7a07cb78693ccbb60e813e56c0af018e2b947e0326a0ada5d3dd839cb6e2fb`, source ID
`ff4184d9d0f5532cfacfe1990416f5d2dcd5a33da7683d2943e1b519609869f3`, ARM ELF
SHA-256 `ead7cc2ac6417ce88833a66e7fcf400d85058061964a96f43a44658fb3bee87c`,
and RBF SHA-256
`7b5eb62411233b96adc244d87fe3ee96b16da13b271fa608d9a70cafd4917b10`.

The current local suite passes 132 Python tests with one declared Windows
privilege skip. ABI generation, transport-control/PCM long-queue checks, candidate
manifest verification and package verification pass. Host timedemo replay passes;
ARM/QEMU timedemo replay passes with the documented 600-second bound at
`../../.work/runtime/arm-replays/742d6ace2dd84dea88b391094bf84e9b/run.json`
(SHA-256 `14aca7fd2d1af4faaba56815314d1206abb3eeecba0652e7a3f14505b155d385`).

The candidate38 package is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate38`; its 190 files comprise the four
runtime roles and 184 redistributable assets. Target preflight passes at
`../../.mister/evidence/receipts/20260908T-candidate38-preflight.json` (SHA-256
`01fe2ca6d599c41bbed92b4974ced77c5dc696ee61855792a183e0cf1f7260a2`). The
physical normal60 receipt is
`../../.mister/evidence/receipts/20260908T-physical-launch-candidate38-normal60.json`
(SHA-256 `a1d73353347f08e70d92e64c8f2fc45c58d461437784c7e776e42e07646ba9bb`).
It proves package/admission/loader/FPGA/frame lifecycle and records local PCM
queue 7257, startup underrun 6766 and steady underrun/resync delta zero over the
observed interval. It does not close active 30-minute audio, physical video/core
identity, controls, campaign/save/multiplayer, performance or clean-install gates.

The implementation bugs found in this continuation are now recorded in the main
plan: a malformed CMake replacement, PCM parameters passed as ports, target
starvation from a 512-frame callback/small FIFO, and package role/asset drift.
The fixes are in candidate38. R10 remains open because scandoubler vertical-sync
timing is still a TODO; no output-mode or physical capture claim may inherit the
candidate38 launcher pass. User-owned MPQs remain outside the package and must be
provided through an explicit target data root during campaign qualification.

## Candidate40 historical continuation — integrated harness fix and target contention

Candidate40 was a historical development checkpoint after fixing a real local
verification regression. The integrated DDR testbench had an 11-bit PCM queue
wire while the production default client exposed 13 bits, and its final
read/response equality check raced a live in-flight request. The harness now uses
`[12:0]` and accounts for one tracked outstanding read. Candidate-bound local
verification and the complete Python suite now pass (20 registered checks, 132
tests, one declared Windows privilege skip).

Candidate40 manifest:
`../../.mister/evidence/candidates/fpga-candidate-20260908-40-integrated-tb.json`
(candidate `56860713d38990ae28f1846e5f22850ed68b9ee228f6178c11e53fcb0f2d8a9b`,
source `13b93de9eb32d9fc72701886c164853622bc744c18cddec1b660f127ffc70c7d`,
manifest SHA-256 `41bd0513171bda2f72751eecc6f8a1573086efab05f789ae24838f3990bce900`).
The package40 preflight passes at
`../../.mister/evidence/receipts/20260908T-candidate40-preflight.json` (SHA-256
`db016d77aaf5c97f5d3f2703314019d9952cb65554c9fe91220064f4a34315a3`) on the
unique target staging directory `_CodexDiabloCandidate40`.

A clean five-second candidate40 launcher smoke returned `status=pass`, exact
candidate/source IDs, FPGA operating state and the exact requested RBF process.
The longer attempt is recorded as blocked at
`../../.mister/evidence/receipts/20260908T-physical-launch-candidate40-attempt.json`
(SHA-256 `9ce81ad97fddeaf01ce178d3453d1096a7c5e623dfde04318508869195f8bdae`): an
unrelated NFS_SE install/rollback process concurrently changed MiSTer ownership,
and the trace observed underrun growth plus dropped PCM chunks. This receipt is a
blocker record, not a board pass. Physical video/core identity, active audio,
controls, campaign/save/multiplayer, performance and clean lifecycle remain open.


## Candidate41 doc-sync checkpoint — 8 September 2026

Candidate41 historically superseded candidate40 after a documentation-only synchronization; Candidate49 was a historical source-bound development identity, and C34/P01-P06 commits now supersede its source inputs. Candidate ID `a5f2b83c0191d56e44a7b1babd5988e3fc0530a9f973f6e6bb739b13479ab989`, source ID `7901cdc0d54c3d8d3a527a85445c78d4d1ad5330e1b223f426a3ed15dc914d0d`, and manifest SHA `c87c3b7dc214f23c4dc299c9010cbf2e8e031c2962a1a05604d59fa7452b0579` are recorded in `.mister/evidence/candidates/fpga-candidate-20260908-41-doc-sync.json`. The runtime ARM/RBF hashes remain `ead7cc2ac6417ce88833a66e7fcf400d85058061964a96f43a44658fb3bee87c` and `7b5eb62411233b96adc244d87fe3ee96b16da13b271fa608d9a70cafd4917b10`. Package41 contains 190 files/184 assets, verifies locally, is staged at \\192.168.0.69\sdcard\_CodexDiabloCandidate41, and target preflight passes in `.mister/evidence/receipts/20260908T-candidate41-preflight.json` (SHA `d917dafcefb058d51f4de183543ca6e36d7cbc3c98645eb5a5b15e835befcacf`). Candidate-bound local verification passes all 20 checks in `.mister/evidence/receipts/20260907T221825Z-1b8d996d-61dc-41d2-b5bd-e72fc2e178a4.json` (SHA `e28aaedf6096ed519ecf792a8736284cb3b288300a73f9bd3c669b95e5eec74e`). Candidate41's quiescent-board normal-session receipt is blocked by a black observer and startup PCM faults; candidate40's longer attempt remains blocked by concurrent NFS_SE installer/rollback ownership and PCM underrun/drop growth (`.mister/evidence/receipts/20260908T-physical-launch-candidate40-attempt.json`, SHA `9ce81ad97fddeaf01ce178d3453d1096a7c5e623dfde04318508869195f8bdae`). Physical identity, active audio, controls, campaign, performance and lifecycle gates remain open.


## Candidate41 physical normal-session receipt — 8 September 2026

The quiescent-board candidate41 Diablo normal-session run is recorded at
`../../.mister/evidence/receipts/20260908T-physical-launch-candidate41-normal60.json`
(SHA-256 `3a1f7e97d3be5429000b27e9d3c1319dd42cf1291f02cba52e505651b5f845fb`).
The launcher exited 0 after its controlled duration, matched the exact candidate
RBF process and saw FPGA `operating`; the trace reported no PCM drop/resync or
steady underrun delta after the startup sample. The observer image remained black
and startup underruns were 6,732, so the receipt is `blocked`, not physical
acceptance. Controls, speakers, campaign/save, performance and release lifecycle
remain open.


## Candidate41 timedemo target blocker — 8 September 2026

A separate Diablo demo/timedemo launch was not accepted because a concurrent
MAME core owned MiSTer while the launcher waited for the exact candidate RBF. The
background launcher was cleaned up without changing the candidate artifacts. The
blocked diagnostic receipt is
`../../.mister/evidence/receipts/20260908T-physical-timedemo-candidate41-blocked.json`
(SHA-256 `028404ad383e53cfc8ff545f0ca5682afc11046d4799fba67debabae40731758`).
The next target window must exclude MiSTer, MAME and installer processes before
timedemo or campaign qualification.

## Candidate43 source-policy and clean-build checkpoint — 8 September 2026

Candidate43 supersedes the provisional candidate42 source-policy record. Its
manifest is `../../.mister/evidence/candidates/fpga-candidate-20260908-43-video-policy.json`
(candidate `82ebd70596f62e5c3e60c00d6609a728359da1186b8ad140c1cd2e90ef6f534f`,
source `10486a2923b134085cbdb7d71e65b419545a4bce979e2fd5d6e9f73907a9c87f`,
manifest SHA `680c79298f3db7747e40dc20087861c193416aa6a0590e1820e561a17fcc2ddd`).
The direct FPGA build receipt
`../../.mister/evidence/fpga-build-candidate43.json` (SHA
`f825d7ab8eaaccfd2f03699bb775c329b759d1bee5eebba648354334317fe2e2`) records
compile, compression and four setup corners with zero violations and 0.188 ns
minimum positive slack. Candidate-bound local and ARM/QEMU verification,
Diablo/Hellfire scene-oracle, package and read-only target-preflight receipts all
pass. Package43 is staged at
`\\192.168.0.69\sdcard\_CodexDiabloCandidate43`; its package manifest SHA is
`595049590830e384a359aec6a70a080483563e151c93de2df205bafc95f10154`.

The first package preflight transiently missed root `MiSTer.ini`; the immediate
rerun passed with the corrected root probe and is the accepted preflight receipt
(`20260908T-candidate43-preflight-rerun.json`, SHA
`993ccfd3d45d22cdf911016fabd2572c1912897b639e945b4f1baa6adc8ca60b`). No RBF
activation was attempted because an external MAME core owns the target. C13/R10
local source/timing work is complete for this candidate, while connector-specific
gameplay captures, active audio, controls, performance, campaign and lifecycle
evidence remain open.

## Historical Candidate49 release-lifecycle checkpoint — 8 September 2026

Candidate49 was the development identity after the package and board-runner
implementation; C34/P01-P06 source commits now supersede its source inputs: candidate `d95d4cfd03154bd659343c5a77a1230bcd4efc7c45d81d4f2299a0d754128611`,
source `59d9a616708db186946cab362d6c66627a99d9a21a18b4bf6f97cb70a3e9eda0`, and
manifest SHA `f420873962a21317c8a9bdc9ff1ad07db02d9ad4299c2b9b5ff2e1abae802c4b`
at `../../.mister/evidence/candidates/fpga-candidate-20260908-49-final-local.json`.
The package has 192 files/184 assets plus setup/notices, verifies with package
manifest SHA `f09bd76e1b4c80d7eb6391409dc1724f573a5931d4cf644ed7092573e49e63f3`,
and is staged at `\\192.168.0.69\sdcard\_CodexDiabloCandidate49FinalLocal`.
Target preflight passes at
`../../.mister/evidence/receipts/20260908T-candidate49-preflight.json` (SHA
`64d827d9d29953396c55be9314ae19fde04aa63820370573fab9de3d594a1b78`). The local
deployment lifecycle receipt
`../../.mister/evidence/receipts/20260908T-candidate49-deployment-lifecycle.json`
(SHA `324d8ad330f940de78d52d77f372b8c04cbf7dce10eeb3278e899410dee14c01`)
passes install, interrupted update, update, rollback, save preservation and
manifest verification. `board_runner.py` now publishes immutable CLI results.
No physical activation was attempted because an external MAME core owns MiSTer;
video rows, active audio, controls, campaign/save, performance, menu activation
and clean-target acceptance remain open.

# P01 admission blocker: global Quartus runner

**Update:** A subsequent preflight now reports `workflowLease=true`,
`unregisteredProcessAdmission=true`, and `slotLifetime=explicit-workflow`.
The table below preserves the original observation. Audit integration is being
implemented; see `../evidence/runner-audit-development.md` and current state.
Capability advertisement is not a substitute for the isolated qualification tests.

Observed 2026-09-05 through the approved `quartus_flow.ps1 -Action Capabilities`.
Provenance: **KNOWN**, direct tool response; the disposition below is engineering
synthesis applying the user's mandatory build contract.

The installed runner reports:

| Capability | Actual |
|---|---|
| Global slots | 2 |
| Slot lifetime | single-stage-worker |
| Workflow lease | false |
| Unregistered-process admission | false |
| InferenceAudit | false |
| TimingAudit | false |
| Authenticated Acceptance | false |
| Persisted SeedSweep | false |
| Artifact inventory establishes acceptance | false |

The applicable skill is
`C:/Users/meath/.codex/skills/mister-rbf-build/SKILL.md`:

> Under a project contract requiring these features, report the exact tooling gap before starting; do not launch raw Quartus to bypass it.

The user's project contract requires these features, including an inference
audit after map and ownership covering the whole workflow. P01 cannot be
accepted with a prior template build, an ordinary lint run, or a raw Quartus
invocation. No HDL or synthesis inputs have been changed in this iteration.

## Smallest next experiment

After the shared runner has been qualified, run:

```text
python support/scripts/diablo.py doctor
```

Require a current receipt with every mandatory capability present. A changed
boolean alone is insufficient: the runner qualification must include isolated
tests of lease retention between stages, two-slot admission, rejection of an
unregistered active process, zero-match/stale report rejection, inference-audit
failure, and tampered/mismatched acceptance rejection. Preserve those receipts.
Do not start a compiler during runner self-tests unless the shared workflow
explicitly admits it and owns its process tree.

Then re-read the RBF skill, publish the P01 decision record, import the exact
template tree with a controlled identity rename, verify `sys/` byte identity,
and run fresh Analysis & Synthesis through the qualified runner.

## Decision record

Observation: Required runner capabilities are absent.

Evidence: The doctor receipt linked by `.mister/state.json` contains the complete
capability response and the source/tool fingerprints.

Hypotheses: A capability-advertisement defect versus a genuinely incomplete
runner. The installed skill independently describes the same legacy gaps.

Selected explanation: Treat required operations as unavailable until isolated
qualification proves their implementation; do not infer behavior from action names.

Smallest change: Foundation scripts, tests, source lock, documentation and evidence
only. Shared runner and hardware sources remain untouched.

Verification: Doctor returns blocked; negative source/data admission tests pass.

Regression scope: No functional HDL, shared framework, or donor changes.

Known unknowns: Qualified runner delivery, ARM sysroot/runtime compatibility,
target access and DDR reservation. Each has a separate later acceptance gate.

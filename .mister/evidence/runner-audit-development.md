# Runner audit implementation, 2026-09-05

Previous goal turn classification: progress. It established P00, reproducible
source/data receipts and a concrete P01 tooling gap. The full P00–P20 objective
remains active; this iteration does not replace it with tooling-only success.

## Revalidated state

The shared runner changed independently since the P00 receipt. Current capabilities
report explicit workflow leases and unregistered-process admission as present.
InferenceAudit, TimingAudit, authenticated Acceptance and SeedSweep remain absent.
Shared runner files were actively changing; this task did not overwrite them.
The new local parser is preparation for qualified integration, not a replacement
compiler launcher or an override of the global runner gate.

## New implementation

`support/scripts/quartus_audit.py` parses actual Quartus 17 report table formats:

- Inference: selected device, successful map, exact expected RAM names/sizes/modes,
  and explicit evidence-backed uninferred-memory exceptions.
- Timing: every declared corner and all five timing check types, finite slack,
  zero TNS, active clock coverage and unconstrained-path accounting.
- Fit: selected device, successful fit, ALM/block-memory/DSP capacity checks.

Unknown formats, duplicate required tables, missing checks, and non-finite numeric
fields fail closed. Repeated *detail* headings are valid in real TimeQuest reports
and do not bypass uniqueness of the required summary tables. Windows Quartus
reports can contain CP1252 degree symbols; decoding is explicit and recorded.

Every diagnostic receipt hashes its report, contract and auditor and explicitly
sets `release_acceptance=false`. These checks do not yet establish source closure,
build freshness, complete memory inventory, named unconstrained exceptions,
normalized timing endpoints, assembler compression, hardware qualification or
authenticated artifact acceptance. They must not enable `Artifacts` yet.

## Real-report evidence

Blood donor reports were read only. No donor artifact is accepted for Diablo.

- Fitter report parsed successfully and resource counts are within capacity.
- Map report rejected Critical Warning 127005: a 16-word memory versus 9-word
  initialization file. It is not silently waived merely because Blood builds.
- STA parsed all declared timing corners and then rejected nonzero unconstrained
  input ports. Named export/review is the next missing audit component.

Receipts: `audit-donor-fit-revised.json`, `audit-donor-timing-revised.json`,
`audit-donor-inference-initial.json`. Initial parser-format failures are retained
as diagnostics, not erased or promoted to accepted results.

## Next concrete work

1. Implement a normalized unconstrained endpoint/clock export tied to each STA
   report hash, preserving setup/hold domains and exact names. Reconcile exported
   counts against the raw report; reject missing and stale allowlist entries.
2. Add narrow diagnostic review records and per-entity memory/register evidence;
   do not blanket-allow critical warnings or accept an empty memory contract.
3. Bind map/fit/STA/assembler outputs to a single fresh runner build/source closure.
4. Add authenticated acceptance and negative tamper/staleness tests, then integrate
   through the approved global runner without colliding with another writer.
5. Requalify leases and audits before importing P01 hardware sources and running map.

No RTL, PLL, framework, SDC, hardware memory access, Quartus build, RBF, deployment,
or global runner modification occurred in this iteration. No hardware claim was
proven and no new global lesson was promoted.

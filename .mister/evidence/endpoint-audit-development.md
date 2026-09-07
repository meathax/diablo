# P01 endpoint accounting, 2026-09-06

Observation: The pending local timing auditor rejects every nonzero unconstrained
count; repeated raw detail headings do not establish setup/hold identity. The
foundation baseline also fails because PATH-selected Git routes alter the
HEAD^{tree} argument into HEAD^tree.

Evidence: state.json, runner-audit-development.md, and baseline receipt
test-4b8dfb68756b43a0b607ade84bd93b53.json.

Hypotheses: Infer detail domains from order, or require explicitly labelled exports.

Selected explanation: Only explicit domain-labelled exports can support exact
accounting. A report hash binds their claimed input, but does not authenticate the
exporter's origin or prove build freshness.

Smallest change: Add a strict normalized endpoint interchange and report-only
validator, exact evidence-backed reviews, CLI input hashing, negative tests, and
native Git executable selection on Windows. No raw-heading order inference.

Verification: Re-run foundation including CLI round trips and malformed, stale,
duplicate, missing-name, domain-swap and count-mismatch fixtures.

Regression scope: Project Python tooling and documentation only, within state.json
allowed_paths. Donor and private game data remain read-only.

Known unknowns: Qualified runner-side production of domain-labelled exports,
authenticated build/source binding, and remaining P01 admission conditions.

## Results

44 foundation tests pass, including 13 endpoint tests with additional malformed
input subcases and a real CLI pass/fail receipt round trip. Receipt:
test-c280b8171dab45a6a066add4749998d1.json.

Selecting git.exe alone did not fix this environment: the MSYS Git executable
also converted HEAD^{tree} to HEAD^tree, while Git for Windows preserved it in a
direct comparison. Source tree identity now uses `git show -s --format=%T HEAD`,
avoiding the problematic revision expression; clean/dirty source admission passes.
The intermediate failing test receipt is retained.

The current doctor receipt reports the configured legacy runner path absent:
doctor-901ab45fcf974dc9a250401f285d1a75.json. Searches of installed skill/plugin
directories found no quartus_flow.ps1. Historical advertised lease capabilities
are not evidence that a callable runner exists in the current environment.

This completes the local normalized interchange/validation part of the pending
endpoint task. Production of authenticated, domain-labelled exports is still
pending; no real donor exception has been waived. P01 remains incomplete.

A wider tool-directory search found `quartus-safe.ps1`, which exposes a positional
executable launcher and lane status, and archived `quartus_flow.ps1` copies under
temporary audit/upgrade directories. Those copies are not installed qualified
workflow runners. No archive was restored or executed, and the per-process
launcher was not substituted for the plan's workflow/audit requirements.

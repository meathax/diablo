# P01 memory and diagnostic audit, 2026-09-06

Observation: The inference auditor accepts an empty expected-memory contract and
does not compare port dimensions. Critical warnings are rejected without a narrow
review mechanism. These gaps are recorded in the P01 resumption state.

Evidence: support/scripts/quartus_audit.py and passing baseline receipt
test-6b49456364a24f5cbeac05721909450b.json (44 tests).

Hypotheses: A bits-only memory match can conceal the wrong port organization;
unscoped diagnostic allowances can conceal a changed warning or report.

Selected explanation: Require explicit nonempty expectations, compare declared
memory shape, and match diagnostic reviews to exact report bytes and occurrences.

Smallest change: Local auditor, synthetic regression tests, contracts and state.

Verification: Negative tests for vacuous contracts, changed shape, stale/duplicate
reviews, different diagnostic text/counts and unwaivable errors.

Regression scope: No HDL or compiler invocation. Existing user changes retained.

Known unknowns: Full per-entity memory/register inventory, review authentication,
qualified runner availability and build/source identity remain separate gates.

## Results

54 foundation tests pass: test-a125b0a8373c40b48d4b4d53649a39ed.json.
The per-entity parser also read 330 entities from the existing Blood map report;
entity-donor-parser-20260906.json binds the report and auditor hashes. The donor
top contains 18,991 inclusive registers, 1,514 local registers and 481,294 block
memory bits. These observed values test the parser only; they are not independently
derived Diablo resource expectations or artifact acceptance.

User supplied the installed Quartus location D:/Q17. Read-only preflight confirms
quartus/bin64/quartus_sh.exe and version.txt reporting 17.0.2.602, with both file
hashes recorded in doctor-040611f16b5c472495b085aec57cb552.json. The CLI now defaults
to that installation and supports --quartus-root. The installation is present;
the configured workflow runner is still absent. No compiler was executed.

Nonempty memory and entity contracts, explicit port shapes, register ceilings,
and exact hash-bound critical-warning review records are now implemented. Complete
inventory coverage, ordinary/tabular warning qualification, authenticated evidence
and fresh build/source binding remain pending. No real diagnostic was waived.

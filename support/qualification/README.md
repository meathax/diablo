# Closure gate matrix

`closure-gates.json` is the machine-readable acceptance contract for the C01–C34 work packages in the detailed audit plan. It records required scope, numeric thresholds, closure dependencies, evidence tiers, and the source changes that reopen a gate.

Validate the contract before changing a status:

```powershell
python support/scripts/closure_gates.py --check
```

A future closure record must contain every C-item, the matrix digest, its source identity, and the SHA-256 of each immutable receipt or artifact it cites. A `closed` item must satisfy all of its listed evidence requirements; `waived` requires an explicit scope-decision identifier, approver, and rationale. Evaluate a record with:

```powershell
python support/scripts/closure_gates.py --evaluate reports/audit-2026-09-07/closure-record.json --expected-candidate-id <candidate-id>
```

The evaluator deliberately blocks a release when any item is open, blocked, or in progress. It is not a substitute for the physical, campaign, timing, and packaging evidence specified in the plan.

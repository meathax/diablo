# Inference and diagnostic report contract

Inference diagnostics require nonempty `required_memories` and `required_entities`
objects. Empty historical diagnostic contracts deliberately fail; do not populate
expectations automatically from the report being judged.

Each exact RAM name maps to an explicit shape, for example:

```json
{
  "bits": 4096,
  "mode": "Simple Dual Port",
  "port_a_depth": 512,
  "port_a_width": 8,
  "port_b_depth": 512,
  "port_b_width": 8
}
```

The optional `type` field also compares exactly. Unknown expectation fields and
invalid counts fail. Total size alone is insufficient: changing 512×8 to 256×16
must fail even though the bit count is unchanged.

Each exact full hierarchy name in `required_entities` maps to:

```json
{"max_registers_inclusive": 12, "block_memory_bits": 4096}
```

The auditor reads the Quartus 17 Analysis & Synthesis Resource Utilization by
Entity table, preserving inclusive and local register counts independently.
It never sums overlapping hierarchy totals. Required entities must exist, remain
within their reviewed register ceiling, and match the expected block-memory bits.
Receipts retain all parsed entities for review. This is evidence for selected
expectations, not a claim of complete source-to-memory inventory coverage.

Optional `reviewed_diagnostics` entries have exactly these fields:

```json
{
  "message": "Critical Warning (123): exact full diagnostic including source location",
  "count": 1,
  "report_sha256": "<SHA-256 of original report bytes>",
  "evidence": "path/to/specific/review"
}
```

These are synthetic examples, not approved production exceptions. Matching uses
the complete diagnostic line with only outside whitespace removed. It requires
exact occurrence counts and the report hash. Wildcard/ID-only allowances, duplicate
reviews, missing evidence and stale reviews fail. Compiler errors cannot be waived.
Tabular critical warnings/errors remain rejected because their contextual review
format has not been implemented. Ordinary warnings are not qualified by this
mechanism. Inference, fit and timing all apply the diagnostic gate.

Evidence references are not authenticated approvals. Future runner integration
must verify their contents, applicability and origin along with source/build
freshness. Every local CLI verdict remains report-only with release acceptance
false. No real donor warning has been waived by implementing this interface.

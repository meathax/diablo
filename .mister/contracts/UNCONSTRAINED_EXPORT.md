# Normalized unconstrained endpoint interchange v1

This is a report-only diagnostic contract. Passing it never authorizes a build,
hardware import, artifact publication, or release acceptance.

The runner must obtain explicitly identified Setup and Hold domain collections.
Repeated `Unconstrained Input Ports` or `Unconstrained Output Ports` detail headings
in a text STA report do not identify domains. Never label them by occurrence order.
Runner-side export generation and authenticated origin remain pending.

The JSON object has exactly these fields:

```json
{
  "schema": "diablo-unconstrained-export-v1",
  "report_sha256": "<SHA-256 of the original STA report bytes>",
  "domains": {
    "Setup": {
      "Illegal Clocks": [],
      "Unconstrained Clocks": [],
      "Unconstrained Input Ports": [],
      "Unconstrained Output Ports": ["top|example[0]"]
    },
    "Hold": {
      "Illegal Clocks": [],
      "Unconstrained Clocks": [],
      "Unconstrained Input Ports": [],
      "Unconstrained Output Ports": []
    }
  }
}
```

The example is synthetic and must not be used to waive a real endpoint.
All eight groups are mandatory, even when empty. Names are exact, case-sensitive
strings; bus indices and hierarchy separators are preserved. Names must be unique
within a domain/category, but the same name may occur in both domains.
`normalize_unconstrained(report_bytes, groups)` validates explicit groups and sorts
names for reproducible serialization. It cannot discover or authenticate domains.

Every summary count must be a nonnegative decimal integer and exactly equal the
corresponding list length. Unknown categories, duplicate keys, omitted names,
extra names and stale report hashes fail. Without an export, only zero counts can
pass, and the review list must be empty.

The timing contract's optional `reviewed_unconstrained` list must contain exactly
one review for every exported identity:

```json
{
  "domain": "Setup",
  "property": "Unconstrained Output Ports",
  "name": "top|example[0]",
  "evidence": "path/to/the/specific/review-record"
}
```

No wildcard matching is performed. Missing evidence, duplicate reviews, extra
reviews and obsolete names fail. Evidence strings are required references, not
cryptographic proof: their contents and applicability still require runner-side
qualification and acceptance review.

Run the diagnostic with new output paths:

```text
python support/scripts/quartus_audit.py timing --report <sta.rpt> --contract <contract.json> --unconstrained-export <export.json> --output <new-receipt.json>
```

The receipt hashes the original report bytes, contract, export and auditor. The
default report encoding is CP1252; `--encoding utf-8` selects UTF-8. Newline or
encoding changes invalidate the export's report hash. Both passing and failing
receipts retain `scope=report-only` and `release_acceptance=false`.

Remaining integration requirements: complete export production without truncation,
authenticated exporter/build identity, source closure, report freshness, narrow
warning reviews, memory inventory, assembler and hardware qualification.

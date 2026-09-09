# C33 producer/output verification

## Verified after representative execution

- The completed session-monitor Quartus build writes its pin diagnostic to
  `.work/goal-fpga-session-monitor-20260909/c5_pin_model_dump.txt`, not the
  project root. Size: 4875 bytes; SHA256:
  `350037c448e63aef5ce6ec6612ed803a63e102f3415a04d22656338f01fa9364`.
  `support/scripts/compile_fpga_snapshot.ps1:210` selects the isolated
  source directory before invoking Quartus. Build receipt:
  `.mister/evidence/receipts/20260909T-candidate-8d6c-fpga-build.json`.
- The passing 3f88 suite records Icarus's explicit `-o` destination beneath
  `.work/build/verification/diablo-verify-1c415891-dc0c-4f6f-82f9-b6a23718449a-9kt_p2yw/.work/build/verification/`.
  The `transport-ddram-arbiter` step compiles and runs its named `.vvp` file;
  it does not use Icarus's default root `a.out`. Receipt:
  `.mister/evidence/receipts/20260909T011505Z-1c415891-dc0c-4f6f-82f9-b6a23718449a.json`.
- Current root contains none of `a.out`, `c5_pin_model_dump.txt`, `$null`,
  ` 2`, `;`, or `NUL`.
- All five preserved files listed in
  `reports/audit-2026-09-07/refresh-evidence/generated-root-disposition.json`
  exist at their disposition destinations and match recorded SHA256 values.
  Nothing was deleted or moved during this verification.

## Scope remaining

This supplies actual producer execution/output evidence for Quartus and the
representative simulator invocation, beyond an empty-root observation.
It does not prove every ad-hoc shell producer is corrected. Historical malformed
redirection artifacts remain preserved; complete their producer audit before
closing C33. This report does not change candidate acceptance or PLAN status.

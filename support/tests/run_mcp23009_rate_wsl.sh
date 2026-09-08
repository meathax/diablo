#!/usr/bin/env bash
set -euo pipefail

rate="${1:-375000}"
expect_pass="${2:-1}"
root="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
verilator="/home/meath/.cache/veriemu-next/src/verilator-5.050/bin/verilator"
objdir="$root/.work/build/verification/mcp23009-verilator/obj${rate}"

"$verilator" --binary --timing -Wno-fatal --top-module mcp23009_rate_tb \
  --Mdir "$objdir" -GRATE="$rate" -GEXPECT_PASS="$expect_pass" \
  "$root/support/tests/mcp23009_rate_tb.sv" \
  "$root/sys/mcp23009.sv" "$root/sys/i2c.v"
"$objdir/Vmcp23009_rate_tb"

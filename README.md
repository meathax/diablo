# Diablo for MiSTer

Source for the Diablo FPGA core and its MiSTer ARM runtime integration.
This is a development repository, not a ready-to-install release.

## Build the FPGA core

Use Quartus Prime Lite 17.0.2 for the DE10-Nano project. From the repository root,
open `Diablo.qpf` or run:

```sh
quartus_sh --flow compile Diablo
```

The RBF is generated under `output_files/`; generated Quartus output is not committed.

## Source dependencies

The pinned source revisions are recorded in `.mister/source-lock.json`. Fetch them locally with:

```sh
python support/scripts/diablo.py fetch --locked
```

This creates local checkouts under `.work/sources/`. The working source tree also
contains the RTL, MiSTer framework files, runtime integration, and build/verification scripts.

## MiSTer game data

No Diablo or Hellfire game data, compiled engine, or prebuilt RBF is included. To run
the game, provide the required game data from your own legally obtained copy on the
MiSTer SD card under `games/Diablo/`. Commercial assets and generated binaries stay
out of this repository.

## Status

The core and ARM runtime are still in development; this source tree does not claim
a complete, verified release package.

## Notices

FPGA and third-party notices are kept with the source. Review the applicable component
licenses before redistributing a built package.

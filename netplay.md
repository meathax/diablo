# Diablo MiSTer netplay

## Goal

Provide a low-latency, deterministic multiplayer path for two to four MiSTers. A player selects **Netplay -> HOST** or **JOIN** in the core OSD, enters a five-letter code, and the game starts its normal DevilutionX character-selection flow. The code is a rendezvous name, not a password or a new network protocol.

## Chosen architecture

Use DevilutionX's existing multiplayer stack and its native ZeroTier provider (`SELCONN_ZT`). This keeps the simulation, packet format, player limit, compatibility checks, and recovery behavior in one maintained implementation instead of adding a second lockstep protocol to the FPGA wrapper.

- ZeroTier is the default internet path because it avoids router port-forwarding and uses direct peer links when possible; relayed paths remain a fallback and can have higher latency.
- The existing TCP provider remains compiled for advanced LAN/manual use. It is not exposed by the short OSD flow because it needs an address and port.
- DevilutionX remains authoritative for the four-player limit and game-state synchronization.
- Character selection stays in-game after the OSD request, so the existing hero and game-compatibility checks are preserved.
- The five-letter code is deliberately public and short. It must not be treated as authentication; a future authenticated invite can be added without changing the transport.

## OSD and launcher contract

The HDL reserves non-conflicting status bits for the OSD:

| Field | Bits | Values |
| --- | --- | --- |
| Netplay action | `status[8:7]` | OFF, HOST, JOIN, LEAVE |
| Code 1-5 | `status[14:10]`, `[19:15]`, `[24:20]`, `[29:25]`, `[34:30]` | blank or A-Z |

The resident MiSTer frontend translates a complete HOST/JOIN selection into the atomic file `/tmp/diablo-netplay.command`:

```text
schema=diablo-netplay-v1
mode=host|join|off
code=abcde
```

The launcher validates the schema, mode, and exactly five alphanumeric characters, then passes only the validated request to the engine through `DIABLO_MISTER_NETPLAY_MODE` and `DIABLO_MISTER_NETPLAY_CODE`. Invalid or incomplete input is treated as OFF. The file is removed at core startup and rewritten atomically, so a stale selection cannot silently start a later boot.

The engine overlay reads that environment through `support/reference/mister_netplay.*`, selects the ZeroTier provider, and bypasses only the provider/game-name dialogs. It still enters the stock hero-selection path. HOST uses the normal game-data compatibility structure and JOIN performs the normal compatibility validation after joining.

## Implementation status

Implemented in this repository:

1. OSD action and five code fields in `Diablo.sv`, without overlapping the diagnostic-video bit.
2. Resident frontend command-file bridge in `support/mister/diablo_main.cpp`.
3. Strict command parsing and process restart handling in `support/scripts/mister_launcher.py`.
4. Re-enabled upstream TCP and ZeroTier transport in `support/cmake/arm-transport.cmake`.
5. Minimal engine overlays for the validated OSD request in `support/reference/mister_netplay.*` and the existing DevilutionX multi/selection sources.
6. Reproducible build/package inputs through the existing ARM transport build and ready-directory pipeline.

## Verification plan

Run gates in this order; MiSTer is the final gate.

### 1. Static and unit checks (host)

- Parse valid, incomplete, stale-schema, invalid-mode, and invalid-code command files.
- Verify environment mapping and that no secret or unvalidated text reaches the engine.
- Verify all OSD fields are unique and do not overlap `status[1]` (DOS framerate), `status[6]` (diagnostic video), or aspect bits `[122:121]`.
- Run `python -m py_compile support/scripts/mister_launcher.py` and `git diff --check`.

### 2. Simulator/build checks (before hardware)

- Configure/build the ARM DevilutionX transport tree with `NONET=OFF`, `DISABLE_TCP=OFF`, and `DISABLE_ZERO_TIER=OFF`.
- Run the repository's Verilator HDL tests, including transport/OSD status tests where available.
- Exercise launcher lifecycle tests: OFF startup, HOST/JOIN request changes, core reset, child exit, and malformed command files.
- Confirm the produced ELF links the ZeroTier and TCP objects and that the generated ready manifest contains the matching hashes.

### 3. Final MiSTer checks

Copy the generated `ready` tree to the MiSTer root and run both `Diablo.rbf` and `Diablo Hellfire.rbf` from `_Other`. On one MiSTer select HOST and a code; on one to three other MiSTers select JOIN with the same code. Confirm:

- OSD launch works without manually opening the in-game multiplayer menu.
- Character selection remains available on every machine.
- Two-, three-, and four-player sessions enter the same game and remain synchronized for at least ten minutes.
- Repeated joins/leaves, reset, and returning to the launcher do not leave a stale command or orphaned runtime.
- A relayed ZeroTier path is reported as higher-latency but remains playable; no frame-pacing work is performed in the network layer.

## Performance and stability rules

- Do not add polling or networking to the FPGA pixel path. The bridge performs one small status read per frontend loop and one atomic file update only when the request changes.
- Keep DevilutionX's packet cadence and `TCP_NODELAY` settings intact. Avoid compression, encryption, or a custom relay in the core process.
- Keep the network request one-shot per engine launch. A failed HOST/JOIN returns to the launcher instead of retrying indefinitely or silently falling back to offline mode.
- Treat the code as a selector only. If authentication or private sessions become necessary, add it as a separate credential field and protocol version rather than overloading the five-letter code.

## Remaining acceptance work

The host command tests, ARM transport link, Verilator integrated transport simulation, and Quartus OSD build have passed (Quartus completed with zero errors). The remaining acceptance gate is a real two to four MiSTer session over ZeroTier, including a relayed-path check and reset/rejoin lifecycle. Record those results beside the release commit rather than claiming network quality from compilation alone.

# DevilutionX 1.5.5 multiplayer verification

Updated: 2026-09-14

Status: **ZeroTier and TCP transport acceptance passed for the 1.5.5 two-peer fixture**.

## Implemented

- MiSTer explicitly enables networking, TCP/IP, ZeroTier, and packet encryption.
- ZeroTier startup is guarded and checks all libzt initialization results. Readiness accepts cached, authorized networks as soon as IPv6, transport, and network status are usable, even when the asynchronous NODE_ONLINE callback is late.
- IPv6 multicast membership is retried after libzt installs the lwIP interface, and discovery replies are sent through both the discovered unicast endpoint and the multicast group.
- ZeroTier discovery now allows 15 seconds for the transport and peer path to settle. TCP peer connects are nonblocking and correctly retain queued frames until the socket becomes writable.
- Both ARM and Windows reference builds apply a guarded 1.5.5 TCP fix. Each socket now completes one composed asynchronous write before starting the next frame. Active buffers survive cancellation.
- TCP server disconnect handling ignores duplicate callbacks and callbacks for a player slot that has since been reused.
- The upstream checkout and wire format remain unchanged. Generated source/header overlays are applied through `support/cmake/netplay.cmake` and `support/netplay_overlay.py`.
- Added a provider executable test linked against the real engine objects, with passworded messages, payload/order validation, and synchronized turns.

## Evidence

| Check | Result |
| --- | --- |
| ARM and Windows builds: NONET OFF, DISABLE_TCP OFF, DISABLE_ZERO_TIER OFF, PACKET_ENCRYPTION ON | Confirmed |
| ARM ZeroTier dependency revision | `1a9d83b8c4c2bdcd7ea6d8ab1dd2771b16eb4e13` |
| Unmodified TCP, two ARM processes, 128 frames of 60,000 bytes | Failed: incorrect packet size and exchange timeout |
| Fixed TCP, two ARM processes, same burst | Both peers passed all 128 frames |
| Fixed TCP, Windows host/client loopback | Both peers passed 7,680,000 bytes each and 32 synchronized turns |
| Fixed TCP, physical MiSTer host and native Windows client | Both peers passed 7,680,000 bytes each and 32 synchronized turns |
| Native TCP client/host exchange after the queue fix | Local Windows fixture passed; physical MiSTer-host/Windows-client run also passed |
| ZeroTier controller connection and IPv6 readiness, ARM and Windows | Confirmed |
| Authenticated MiSTer and Windows peer path | Confirmed: IPv6 discovery, TCP handshake, and bidirectional payload traffic |
| ZeroTier complete join and exchange, cleaned binaries | Both peers passed 7,680,000 bytes each and 32 synchronized turns |
| Two physical MiSTers; four-player sessions; full in-game campaign synchronization | Not verified |
| Existing netplay contract tests | 5 passed |

The burst deliberately uses valid frames near the provider's 65,535-byte framing limit to force partial writes. It is a transport stress test, not a claim that normal game messages are this large. Normal provider capabilities advertise 512-byte messages.

The successful authenticated run passed the parent config root (the helper appends `zerotier/`), so both peers reused their intended identities. Both peers reached IPv6 network readiness, discovered each other, completed the TCP handshake, and exchanged the complete stress burst. A few unrelated three-byte packets from other ZeroTier nodes still produce the existing `Incorrect package size` log; they are rejected and do not affect the validated peer exchange.

## Scope limits

Windows currently has enabled inbound **Allow** rules for:

`D:\Arcade\AI\aCORES\Diablo\.work\build\reference-host-1.5.5-zerotier\netplay-peer.exe`

The rules apply to the rebuilt netplay-peer.exe for the Public profile. The authenticated MiSTer-to-Windows route is now established and the end-to-end fixture passes.

A second physical MiSTer, four-player sessions, and real in-game campaign synchronization are still outside this two-peer transport fixture.

## Reproduction

Build the engine first, then run:

```text
python support/tests/build_netplay_peer.py <engine-build-directory>
```

The helper supports the existing Windows MinGW and Linux Ninja build layouts. It reuses the engine's compile definitions and link dependencies; it does not contain an alternate network implementation.

On the host and client respectively, using separate existing configuration directories:

```text
netplay-peer tcp host 0.0.0.0 <host-config-directory/>
netplay-peer tcp join <host-LAN-IP> <client-config-directory/>
```

For ZeroTier, use `zt` for a passworded test or `zt-public` for an unpassworded test, and replace the address with the same five-character game ID on both peers. Pass the parent config root; the helper appends `zerotier/` when loading libzt storage. The fixture uses distinct ZeroTier UDP ports for its host and client so two nodes can be tested on one machine.

Both processes must print PASS and exit successfully. Each validates 128 ordered message payloads and 32 turns from both players. This fixture supports two peers; it is not a four-player acceptance test.

## Artifacts and deployment

The stripped ARM engine is staged locally at `.work/netplay-release/devilutionx`.

SHA-256: `727ac1927713b73479fc7f20bc832273b0346726e2c8f03d6d8cfc124feb3743`

The final ARM and Windows engine builds include the guarded overlay and the provider fixture passes against them. The installed package was **not replaced**; its manifest-based integrity checks require a complete package rebuild and validation before deployment. Only the temporary provider test executable was copied to the MiSTer. Unrelated ready-tree changes were preserved. No commit was made.

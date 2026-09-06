# P00 source and component inventory

The source lock distinguishes directly inspected sources from secondary reference
identities supplied by the approved plan. A pinned commit is not an import license.

| Component | Present state | Notice / disposition |
|---|---|---|
| DevilutionX | Separate clean local checkout at locked commit | `LICENSE.md`, Sustainable Use License; retained upstream, modification and redistribution conditions apply |
| Blood | Read-only primary donor, clean locked HEAD | Root `LICENSE` plus per-file notices; no runtime implementation imported |
| Template_MiSTer | Read-only cached exact template, clean locked HEAD | Root `LICENSE`; no framework imported before synthesis gate |
| SDL2 | Version, URL and SHA-256 recorded from selected engine dependency file | Not downloaded or linked by this implementation yet |
| Frontier | Locked architecture reference | No code imported; daemon launcher excluded |
| openfpgaOS/Duke3D | Locked batching reference | No code imported; foreign runtime and work-dropping recovery excluded |
| Historical Duke3D / DeViL | Locked deployment references | No code imported or acceleration claim inferred |
| OpenBOR / Main ancestor | URLs and identities confirmed in pinned Blood `versions.lock` | Verify file-level ancestry and notices before import |
| Foundation Python and tests | New project code | No third-party runtime implementation copied; aggregate release licensing remains unresolved |
| Commercial game MPQs | User supplied, ignored private directory | Hashes and bounds in ignored private manifest; no redistribution |

The successful fetch receipt records commit, Git tree identity, origin and actual
license-file hashes for DevilutionX, Blood and Template. It does not prove the
complete transitive dependency closure. P02 must lock all fetched dependencies,
toolchain and target sysroot before an accepted engine build.

Before each import, inventory every file with its upstream URL, immutable commit,
path, hash, notice and destination. Keep copied GPL wrapper code out of the
DevilutionX process until composition requirements are resolved. A protocol
boundary does not automatically resolve licensing.

## Shared lessons applied

The canonical shared lessons were read/searched before work. Relevant entries
guide these future falsification tests:

- MiSTer Main's exclusive input grab: first prove input through Main → `hps_io`
  → host transport; do not introduce a competing engine evdev reader.
- Cross-language field packing: use distinct nonzero walking-bit fixtures at the
  real producer and consumer; prove corruption is detected before ABI adoption.
- Frame ownership: test displayed/in-flight buffer protection before optimizing
  copies or using timeouts for recovery.
- Frame cadence: measure FPGA completion/display feedback before changing the
  engine limiter; preserve one pacing authority.
- Memory inference: inspect fresh Quartus map evidence instead of trusting RAM
  attributes. This iteration stops before HDL because that audit route is absent.

No new cross-core hardware lesson was proven in P00; no global lesson entry was
added. This record does not turn planned hardware tests into measured results.

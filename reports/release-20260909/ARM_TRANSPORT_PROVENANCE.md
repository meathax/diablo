# Retained ARM transport build provenance

Observed 9 September 2026. This identifies retained evidence; it does not
certify a clean rebuild or complete the source lock.

The actual cache is `/home/meath/.cache/diablo-arm-engine-transport` in
Ubuntu WSL. Its `devilutionx` exactly matches the ARM executable packaged in
candidate fa95 (and 3f88): 8723344 bytes, SHA256
`f444ce3fce534b43c1157540adf1a40fd596e7de43382b2d1619baa71ee77c6d`.

Retained configuration/build records in that same cache:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| CMakeCache.txt | 70281 | 3f846b7d532bcf105db2d1e18d1b426b6571ec5b7e2e4d3af43ae1a77503d24b |
| build.ninja | 2330919 | 9cb05f8adab33bf3d7e9b4a780f6bf030c0e5e9bb2af02bb3793d2396d80d61f |

The cache records Release mode, Speex as default resampler, static SDL2,
SDL_audiolib, SDL_image, Lua, libsodium, libpng and other dependency choices.
These records anchor the dependency-notice investigation in the build whose
output bytes match the shipped executable.

Do not run `support/scripts/record_arm_reference_provenance.py` as evidence
for this executable. Its constants select `arm-engine-portable`,
`arm-reference.cmake` and a historical reference scenario. That evidence is
useful for its own role, not interchangeable with the transport engine.

Remaining: reconcile exact recipe/overlay/dependency inputs, compiler and
sysroot identities, and original build evidence into the release provenance
contract. A matching retained executable does not establish that the current
mutable cache is a complete reproducible source snapshot.

## Compiler and overlay follow-up

`CMakeFiles/4.2.3/CMakeCXXCompiler.cmake` records GNU 15.2.0, architecture
`armv7`, and compiler
`/home/meath/.cache/diablo-toolchain-1.3.1/x-tools/armv7-neon-linux-gnueabihf/bin/armv7-neon-linux-gnueabihf-g++`.
Read-only execution of that compiler returned exit 0 with empty stderr:

- `-dumpmachine`: `armv7-neon-linux-gnueabihf`.
- `-print-sysroot`: `/home/meath/.cache/diablo-toolchain-1.3.1/x-tools/armv7-neon-linux-gnueabihf/bin/../armv7-neon-linux-gnueabihf/sysroot`.

This identifies the reported location, not a content hash of the entire sysroot.

The cache selects `support/cmake/arm-portable.cmake` as its toolchain;
Ninja's regeneration inputs also name `arm-transport.cmake` and
`mister-controller.cmake`. Source root is the retained DevilutionX checkout.
`compile_commands.json` points to the three `mister-controller-overlay`
sources; all three current files match the after-hashes in
`mister-controller-fixes.txt` (441 bytes, SHA256
`12c03b506b6df3df5e9206abf35cba79c5d1d6fe0f24988f95ed2c2383456696`).
It also points to five `mister-engine-overlay` sources. Their retained
`mister-transport-fixes.txt` is 794 bytes, SHA256
`5a444a6418c3688ded0576108d8bd6af44ee290908eb4319118e5ce90ad5e5f2`;
All five transport-overlay files now match their recorded after-hashes, and
each exact path occurs in the retained compile database:
`engine/dx.cpp`, `storm_svid.cpp`, `engine/sound.cpp`, `aulib.cpp`, and
`main.cpp` beneath `mister-engine-overlay`. Together with the three controller
files this verifies all eight listed overlays against their retained markers.
It does not prove the marker files capture every possible build input.

## Selected retained toolchain file identities

The compiler driver is 2189904 bytes, SHA256
`0aac4dc4b3291e3eb4a8550932b7ebb7468d35edf1837f417f3f3e04abedc790`.
Read-only `sha256sum` through Ubuntu WSL identifies these files under the
reported sysroot's `lib/` directory:

| File | SHA256 |
| --- | --- |
| libc.so.6 | 22d201530b83e8b8764178dce249539d17d551e82011b49951a4e77ebdf7f458 |
| ld-linux-armhf.so.3 | c7c871a6299af1ba955d4ac8ec2dfde6db649d0c18778eac48035cc246105b5d |
| libstdc++.a | 37c7932e8bcd89e57d7ee054ad485512f97d027c0aa418773397c883de51b41c |

Linux resolves the library symlinks correctly; initial Windows UNC reads of
the two runtime symlinks returned ENOENT and were not treated as missing Linux
files. These selected hashes are not a whole-sysroot identity, evidence of
the original link inputs' immutability, or hashes of the target board's runtime.

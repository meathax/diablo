# Runtime notice inventory — 9 September 2026

This is a discovery record, not a licensing-compliance or release-acceptance claim.
The ARM executable in candidate `8d6cfe273d92fcb2ef95b5acf53fb599085d3159351c3875b28377a45319f78c`
has SHA-256 `f444ce3fce534b43c1157540adf1a40fd596e7de43382b2d1619baa71ee77c6d`.
Its bytes exactly match `devilutionx` in the original `diablo-arm-engine-transport`
build cache. The paths below are relative to that cache's `_deps` directory.

## Located notices

The build's `devilutionx` link rule lists SDL2, Asio, libsodium, libzt,
libsmackerdec, Lua, SDL_audiolib, mpqfs, BZip2, SheenBidi, SDL_image,
libpng and zlib. Include paths also name magic_enum, unordered_dense and sol2.

| Component | Located notice file |
| --- | --- |
| SDL2 | `sdl2-src/LICENSE.txt` |
| Asio | `asio-src/asio/LICENSE_1_0.txt`, `asio-src/asio/COPYING` |
| libsodium | `libsodium-src/LICENSE` |
| libzt | `libzt-src/LICENSE.txt` |
| libsmackerdec | `libsmackerdec-src/COPYING` |
| Lua | `lua-src/lua-5.4.7/doc/readme.html` preserved whole, including its license notice |
| SDL_audiolib | `sdl_audiolib-src/COPYING`, `sdl_audiolib-src/COPYING.LESSER` |
| mpqfs | `mpqfs-src/LICENSE` |
| BZip2 | `bzip2-src/LICENSE` |
| SheenBidi | `sheenbidi-src/LICENSE` |
| SDL_image | `sdl_image-src/COPYING.txt` |
| libpng | `libpng-src/LICENSE` |
| zlib | `zlib-src/LICENSE` |
| magic_enum | `magic_enum-src/LICENSE` |
| unordered_dense | `unordered_dense-src/LICENSE` |
| sol2 | `sol2-src/LICENSE.txt` |
| fmt within SDL_audiolib | `sdl_audiolib-src/3rdparty/fmt/LICENSE.rst` |
| concurrentqueue within libzt | `libzt-src/ext/concurrentqueue/LICENSE.md` |
| ZeroTierOne within libzt | `libzt-src/ext/ZeroTierOne/LICENSE.txt`, `libzt-src/ext/ZeroTierOne/COPYING` |
| lwIP within libzt | `libzt-src/ext/lwip/COPYING` |

## Remaining release work

Actual-cache build follow-up confirms both `dr_mp3.c.o` and `dr_wav.c.o`
are archived into SDL_audiolib (`build.ninja:7228,7250,7412`). The same build
declares four libnatpmp and 26 miniupnpc object rules beneath ZeroTierOne's
`ext` directory. Their bundled LICENSE files are now preserved byte-for-byte
as `libnatpmp.txt` and `miniupnpc.txt`. These and `dr-libs.txt` postdate staged
candidate 3f88 and must be included in a subsequent package, not relabeled
as already-deployed content. Object rules establish build participation,
not complete final-link reachability or distribution compliance.

Speex follow-up: `speex-resampler.txt` exactly preserves the opening comment
of the matching cache's `sdl_audiolib-src/3rdparty/speex_resampler/resample.c`.
The build rules compile its object and include it in `libSDL_audiolib.a`.
Use the source's three-condition notice, not just the shorter bundled README.
This and the two asset notices are included in local candidate `3f88`.

Working-tree follow-up: upstream CC-BY and OFL texts are now preserved as
`support/licenses/third-party/assets-CC-BY.txt` and `assets-OFL.txt`, with
byte-for-byte copy hashes checked. These additions postdate package 60fc;
that immutable package has not been rewritten. Sixteen Linux package/deploy
tests pass with the expanded notice directory. Asset-level attribution and
distribution conditions remain unresolved.

- Completed preservation: candidate `60fce530c7584e70ed84d1329f9319103e28ad19348faeaace9076225abeafde` includes 26 dependency/compiler notice files plus `INDEX.md` under `licenses/`, copied from `support/licenses/third-party/`. Source and package manifests hash these files; package tests cover exact copying and tamper rejection. This candidate reuses the same ARM bytes identified above.
- Resolve nested dependency coverage from actual compiled objects; discovery of a file alone does not establish that its component was linked.
- Asset-notice lead: pinned upstream `Packaging/nix/LinuxReleasePackaging.sh:37-38` explicitly copies `Packaging/resources/LICENSE.CC-BY.txt` and `LICENSE.OFL.txt` into its Linux release. These texts are not yet in our 26-file notice set. Trace their applicability to our 184 packaged assets and preserve applicable attribution before closing this gate; the upstream packaging command alone does not identify individual asset ownership.
- Review SDL_audiolib's Speex resampler, libzt's nested components, and redistributable game assets/fonts. GCC GPL3, runtime exception and libstdc++ PSTL notices are now preserved from the matching GCC 15.2.0 toolchain; applicability and remaining obligations still need review. The link rule uses `-static-libgcc` and `-static-libstdc++`.
- Complete the distribution-composition review required by the source lock and plan. Copying license texts alone does not prove that all distribution conditions are met.
- Keep this inventory separate from hardware acceptance. The new candidate remains local; MiSTer was running I, Robot at the last process check.

The FPGA GPL text and the pinned engine Sustainable Use License are already
included in candidate `8d6c` as `LICENSE.fpga` and `LICENSE.engine.md`.

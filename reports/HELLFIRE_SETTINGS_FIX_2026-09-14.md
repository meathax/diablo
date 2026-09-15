# Hellfire Settings missing palette

Selecting Settings in the Hellfire main menu reproduced a fatal asset error on
the installed MiSTer runtime. The engine log reported:

```text
Failed to open file:
ui_art\hellfire.pal
```

The 1.5.5 `UiSettingsMenu` calls `UiLoadBlackBackground`, which calls
`UiLoadDefaultPalette`. The latter selects `ui_art/hellfire.pal` in Hellfire and
`ui_art/diablo.pal` in Diablo. The release contained the Diablo palette but omitted
the Hellfire palette. Main-menu artwork still loaded, so reaching the main menu
did not expose the incomplete asset set.

Restored the 768-byte Hellfire palette from the matching 1.5.5 ARM build. SHA-256:
`3b6a6806f100a85a5328e3b9dc196ba3efb29553d67eb9a9de14969ec6e69478`.
Added a release-building guard and regression test for missing or truncated
campaign Settings palettes. Regenerated the package manifests, runtime archive,
downloader database, and ready-tree hashes.

Renamed only the Hellfire RBF to `Hellfire.rbf` in the ready tree and on MiSTer;
the builder now preserves that filename. Its bytes were not changed.

Copied the palette and updated manifests to the installed runtime, verified their
hashes, and preserved the previous manifests outside the runtime directory.
The engine, launcher, and FPGA executable contents were not changed.

The repaired package passes full local package verification. All 26 focused
tests passed under Linux; Windows also passed with two platform-specific skips. A post-fix in-game
retest is pending: the user instructed that MiSTer must not be launched again
until requested.

# Diablo startup performance

Installed candidate: `33828f22e2b4cbd4cf0429f966689558c2b583996f556c671c468bb2efeda4ae`.

The slow first launch was reproduced on MiSTer. A cold-cache RBF reload took
35.732 seconds to the first frame recorded by the FPGA transport. Most of the
prelaunch work occurred before the ARM engine process started.

The managed-package fast path still recursively inspected every asset directory
and resolved hundreds of paths. Consolidating that scan improved repeat launches
but did not fix the cold launch. The final change removes the recursive scan
from normal managed launches and uses the fully verified installation receipt.
Package/deployment manifest hashes, identities, runtime entrypoint paths and
sizes, and agreement between asset manifests are checked before launch.

| Measurement on MiSTer | Before | Final change |
| --- | ---: | ---: |
| Cold-cache managed-package identity check | 18.832 s | 1.126 s |

This is a 94% reduction in the measured check, not an end-to-end loading-time
claim. Full file hashing and asset verification still run during installation.
Unmanaged packages still receive full launch verification; set
`DIABLO_MISTER_VERIFY_FULL=1` to explicitly request it for a managed installation.
Normal managed launches no longer audit individual asset-file changes made
after installation. Reinstall modified packages or use full verification when
diagnosing damaged assets.

Validation: 32 package/launcher tests passed, including regression checks for
avoiding a recursive launch scan, altered runtime size, explicit full
verification, and symlink rejection by the full verifier. The final package
passed local and on-device verification and was installed transactionally.
Existing saves and game data were preserved. The ARM engine and RBF were not
changed by this startup fix.

The MiSTer rebooted into DOSBox Pure during the first final-package transfer.
The transfer was repeated successfully without changing the running core.
An end-to-end cold launch of the final candidate remains pending permission
to switch away from that other workload. No instant-loading claim is made.

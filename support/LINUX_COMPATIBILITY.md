# MiSTer Linux compatibility

Reviewed 8 September 2026 against [Zaparoo frontend PR #430](https://github.com/ZaparooProject/zaparoo-frontend/pull/430) and its [final change](https://github.com/ZaparooProject/zaparoo-frontend/pull/430/files).

That PR fixes Zaparoo's startup after the MiSTer 6.18 update: fbdev mapping can return `ENODEV` when the driver lacks `fb_mmap`. Its fallback obtains the framebuffer range by ioctl and maps `/dev/mem`. It offers direct or staged copies and retains shared mappings until their last borrower releases them. It changes the frontend, not FPGA logic.

## Diablo impact and changes

| Area | Finding / disposition |
| --- | --- |
| Gameplay and movies | The target launcher sets SDL dummy video/audio. The transport writes indexed frames and PCM to shared DDR through `/dev/mem`. No active target code opens `/dev/fb0`; the reported fbdev failure does not require a replacement renderer or HDL change. |
| Memory ownership after updates | Added a live `/proc/iomem` check before loading the RBF or issuing an admission. Reject overlap with Linux System RAM, hidden/malformed ranges, and addresses outside the DE10-Nano's 1 GiB DDR. Existing current-boot admission, candidate checks and transport lease still apply. |
| Version evidence | Ready/run records now include the actual kernel release, RAM ranges and their source hash, transport aperture and explicit SDL/fbdev backend information. Compatibility follows capabilities, without an arbitrary version allowlist. |
| Framebuffer fallback | Do not redirect Diablo's transport to the framebuffer address returned by ioctl: the transport is a separate ABI aperture at `0x3fe00000`, not a Linux framebuffer. If a future ancillary UI uses fbdev, give that UI its own checked fallback. |
| Performance opportunity | The PR's direct/staged distinction is useful when measuring our existing frame-copy path. Use `support/transport/transport_copy_bench.cpp` on each kernel; adopt a copy change only if measurements justify it. The PR provides no Diablo FPS or latency measurement. |
| Mapping lifetime | Diablo already has move-only transport ownership, a process lease and destructor cleanup. Preserve these when adding consumers; do not introduce a second owner that can unmap another consumer's memory. |

## Evidence and remaining qualification

Read-only target inspection reports **5.15.1-MiSTer**, with Linux System RAM ending at `0x1fefffff`. The new admission check accepts its existing `0x3fe00000` transport aperture. No kernel update, target deployment, memory write, or core switch was performed for this review.

Evidence is in `.work/linux-618-compat/target.json`, `target-memory.json`, and `local-inventory.md`. Launcher/package tests pass: `wsl.exe -d Ubuntu --cd D:/Arcade/AI/aCORES/Diablo --exec python3 -m unittest support.tests.test_mister_launcher support.tests.test_package_release -q` (14 tests).

**6.18 hardware compatibility is not yet verified.** On that kernel, retain its exact boot identity/configuration, check `/dev/mem` admission and real mapping, then repeat candidate-bound launch, first frame, title/cinematic/gameplay, sound, controllers, save/relaunch and core-switch cleanup. Keep CRT/direct-video physically unqualified under the user's HDMI-only scope. A successful fbdev workaround in another application is not Diablo qualification.

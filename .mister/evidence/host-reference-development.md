# Host reference implementation, 2026-09-06

Current update: the first session 94893 terminated with the miniupnpc Windows
timeout compile failure (build-host-54780598db08432f972ab5964fbbef8c.json).
The new sequential guide makes step 1 the sole active implementation step.
Session 62980 is rebuilding after the hash-checked fix recorded under
support/patches. It passed miniupnpc and reached engine compilation. The alternate
NO_GETADDRINFO timeout branch also compiled successfully with GCC. The FPGA flow
was interrupted at user request and no Quartus compiler remained live. Read state
for the latest handle/status; the initial-session account below is historical.

Previous goal-turn classification: progress. The prior work replaced the old
plan with a source-backed audit; this turn begins stage A implementation.

Added build-host with an explicit Windows/UCRT64 recipe, input admission and
out-of-tree logs. Source remains the pinned unmodified engine. Inventory covers
24 upstream dependency declaration files; full downloaded/system dependency
closure is still pending. CMake identifies GCC 16.1.0 and has reached SDL2 feature
checks. The first build is still live at handoff; no executable/gameplay success
is claimed. Sound, SDL2, TCP and demo functionality remain enabled.

Live tool session at handoff: 94893. Poll this handle and inspect
`.work/build/reference-host/configure.log` and `build.log` before any restart.
Original command: `python support/scripts/diablo.py build-host --jobs 8`.
The CLI will write a build-host receipt when the operation terminates.

Foundation regression: test-3376902e7bb7464eb1d1a3a3e6400357.json (56 tests pass).
Next: resolve real configure/build failures, inventory resolved dependencies,
execute upstream tests, then exercise both campaigns with private writable
config/save output paths. Stages B–J remain required; the goal is not complete.

## Latest evidence: host build and test execution

Host executable built successfully (build-host-506ef6489d4d4158a394927e6e1d9006.json) and reached the Diablo menu. Gameplay remains unverified. Reconfiguration with console-test linkage fixes passed (build-host-376154eaa57345fbaa128e6c4e0a312c.json). The generated game link still includes SDL2main; console test links do not. Text rendering now links but the first golden test crashes in SDL_RWclose with a null stream; see host-text-render-failure.json for the diagnosis and unchanged-fixture requirement. Source checkout remains clean. Loaded DLL hashes are recorded in host-loaded-modules.json. The remaining test build is live in session 75241; poll before restarting.

## Windows rendering fix verified

The recorded build-local assets.cpp/png.h overlays fix drive/UNC asset paths and null PNG handles. All 25 unchanged upstream text-render golden tests pass (host-render-tests-25.json). Added host regression cases for empty paths and both Windows separators; these await the next rebuild. Full suite build found missing GMock dependencies for crawl/path tests; inspection also found ini_test. The host CMake integration supplies them. No complete upstream suite pass or gameplay acceptance is claimed. Foundation tests pass in test-b883ad97a9ca494086478a86a90189b6.json.

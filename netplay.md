# Diablo MiSTer multiplayer

Use the normal **Multi Player** menu inside Diablo or Hellfire. Select the connection type, choose or create a multiplayer character, and use the game's Create/Join options. Players must use compatible versions, campaigns and mods. DevilutionX supports up to four players.

The native ZeroTier and TCP providers remain enabled. The MiSTer OSD has no multiplayer controls, invite-code fields, or automatic game-selection bridge.

## Asset compatibility

The bundled Hellfire mod is installed as mods/hf.mpq, allowing the normal mod identification and compatibility checks to work. Older packages staged loose Lua/TSV files into mods/hf inside the save folder, triggering the multiplayer override safeguard.

On launch, unchanged legacy files are preserved in a sibling directory named <save-folder>.legacy-hf. Characters and other save files stay in place. Modified legacy files are reported instead of overwritten. Real loose logic overrides remain subject to the engine's normal multiplayer protection.

The package builder uses smpq in Linux/WSL and verifies every packed file by extracting the archive and comparing its contents to the original assets.

## Verification

Run the launcher, package and multiplayer contract tests, rebuild the ARM engine, frontend and RBF, and verify the assembled package before deploying. On MiSTer, check the standard provider, character and Create/Join menus for both campaigns. A connected multi-device game is required to establish end-to-end synchronization.

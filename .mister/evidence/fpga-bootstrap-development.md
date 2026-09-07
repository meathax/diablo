# FPGA bootstrap, 2026-09-06

Observation: The workspace has no FPGA project. The pinned template is available
and the host reference configure is live independently.

Evidence: Current root inventory, source lock and clean template admission.

Selected change: Import the Quartus 17 template with project/file/OSD identity
renamed to Diablo. Preserve sys/ byte-for-byte and keep the template demo video
for the first map baseline. This is not native Diablo video or gameplay.

Verification: Hashed per-file import manifest and exact framework comparison;
fresh Analysis & Synthesis through the installed quartus-safe launcher. Review
actual failures before modifying framework or generated IP.

Known unknowns: Compilation compatibility and all target video/gameplay behavior.
Native 640x480 test patterns and compressed production RBF remain subsequent work.

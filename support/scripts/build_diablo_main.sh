#!/usr/bin/env bash
# Build the resident Diablo MiSTer-Main derivative from VoidSW's vendored,
# proven Main_MiSTer wrapper baseline. The output is the /media/fat/Diablo
# executable selected by MiSTer.ini's [Diablo] main=Diablo entry.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
donor="${VOIDSW_WRAPPER_SOURCE:-$root/../VoidSW/platform/mister/wrapper}"
mkdir -p "$root/.work"
stage="$(mktemp -d "${TMPDIR:-/tmp}/diablo-main-wrapper.XXXXXX")"
cross="${CROSS:-arm-buildroot-linux-gnueabihf-}"

[ -f "$donor/Makefile" ] && [ -f "$donor/main.cpp" ] || {
  echo "VoidSW's vendored MiSTer wrapper is required: $donor" >&2
  exit 1
}
command -v "${cross}gcc" >/dev/null || {
  echo "Missing MiSTer ARM compiler: ${cross}gcc" >&2
  exit 1
}

# VoidSW keeps a number of old object trees alongside its sources.  They are
# neither inputs nor safe to reuse, and copying them from the Windows mount can
# take minutes.  Stage only the source tree and let this build create its own
# bin directory.
(cd "$donor" && tar --exclude='./bin' --exclude='./bin-*' -cf - .) | (cd "$stage" && tar -xf -)
cp "$root/support/mister/diablo_main.cpp" "$stage/main.cpp"
# VoidSW's menu adds a hook for its campaign selector. Diablo has no selector
# at this level (the selected RBF supplies the campaign), so retain the donor
# menu unchanged and provide the inert hook it requires.
cat > "$stage/diablo_menu_compat.cpp" <<'EOF'
bool voidsw_selector_key(unsigned int)
{
  return false;
}
EOF

python3 - "$stage/Makefile" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace("PRJ = Mister_VoidSW", "PRJ = Diablo")
start = text.index("# The resident MISTER DOS frontend")
end = text.index("CPP_SRC =", start)
text = text[:start] + text[end:]
text = text.replace(
    "CPP_SRC = $(filter-out main.cpp,$(wildcard *.cpp)) ",
    "CPP_SRC = $(filter-out voidsw_main.cpp voidsw_wrapper.cpp misterdos_frontend.cpp misterdos_doom_adapter.cpp gzdoom_frame_bridge.cpp gzdoom_io_bridge.cpp nukem_netplay.cpp,$(wildcard *.cpp)) ")
text = text.replace(" $(MISTERDOS_C_OBJ)", "")
text = text.replace(" $(MISTERDOS_C_DEP)", "")
text = text.replace(" -DMISTER_VOIDSW_FULL_WRAPPER -DMISTERDOS_NATIVE_FRONTEND", "")
text = re.sub(
    r"\n\$\(BUILDDIR\)/(?:frontier_transport|mister_video|mister_audio|mister_input)\\.c\\.(?:o|d):.*?(?=\n\$\(BUILDDIR\)/|\nifneq|\Z)",
    "\n", text, flags=re.S)
path.write_text(text)
# Return through stock MiSTer so its core-specific main= selection is rerun.
fpga = path.parent / "fpga_io.cpp"
text = fpga.read_text()
anchor = 'if (!strcasecmp(base, "Mister_VoidSW")'
if text.count(anchor) != 1:
    raise SystemExit("unsupported donor restart implementation")
text = text.replace(anchor, 'if (!strcasecmp(base, "Diablo") || !strcasecmp(base, "Mister_VoidSW")')
fpga.write_text(text)
PY

# Match VoidSW's Docker path exactly.  Its image deliberately carries a newer
# C++ compiler than the MiSTer runtime, so static libstdc++/libgcc are needed
# for an ELF the target loader can resolve.
make -C "$stage" -j"${JOBS:-2}" BASE="${cross%-}" LINKER="${cross}g++" \
  LFLAGS_EXTRA="-static-libstdc++ -static-libgcc" STDLIB_LINK="" bin/Diablo
mkdir -p "$root/output_files"
cp "$stage/bin/Diablo" "$root/output_files/Diablo"
echo "Built $root/output_files/Diablo"

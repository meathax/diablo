"""Build/run the lighting differential test ONLY after user build authorization.

Run on Linux/WSL with a C++20 compiler and SDL2 development headers.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=ROOT / ".work/sources/devilutionx")
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--allow-build", action="store_true",
                        help="explicit confirmation that compiling tests is authorized")
    parser.add_argument("--sanitize", action="store_true", help="enable AddressSanitizer")
    args = parser.parse_args()
    if not args.allow_build:
        parser.error("builds are paused; pass --allow-build only after user authorization")
    source = args.engine.resolve() / "Source"
    overlay = ROOT / "support/reference/lighting"
    expected = json.loads((overlay / "upstream.json").read_text())
    for name, digest in expected.items():
        data = (source / "engine/render" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f"upstream reference changed: {name}")
    sdl_flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "sdl2"], text=True))
    with tempfile.TemporaryDirectory(prefix="diablo-lighting-") as temporary:
        output = Path(temporary)
        header = (source / "engine/render/light_render.hpp").read_text()
        implementation = (source / "engine/render/light_render.cpp").read_text()
        blit = (source / "engine/render/blit_impl.hpp").read_text()
        rename = lambda text: re.sub(r"\bLightmap\b", "ReferenceLightmap", text)
        (output / "reference_light_render.hpp").write_text(rename(header))
        (output / "reference_light_render.cpp").write_text(rename(implementation).replace(
            '"engine/render/light_render.hpp"', '"reference_light_render.hpp"'))
        (output / "reference_blit_impl.hpp").write_text(rename(blit).replace(
            '"engine/render/light_render.hpp"', '"reference_light_render.hpp"').replace(
            "namespace devilution {", "namespace devilution::reference {"))
        binary = output / "lighting-test"
        command = [args.compiler, "-std=c++20", "-O2", "-g", "-DDIABLO_LIGHTING_TESTING",
                   "-I" + str(overlay), "-I" + str(output), "-I" + str(source), *sdl_flags,
                   str(ROOT / "support/tests/lighting_optimization_test.cpp"),
                   str(overlay / "engine/render/light_render.cpp"),
                   str(output / "reference_light_render.cpp"), "-o", str(binary)]
        if args.sanitize:
            command += ["-fsanitize=address", "-fno-omit-frame-pointer"]
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()

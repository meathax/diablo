"""Link a provider test using a fully built Ninja or Windows MinGW engine."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("build", type=Path)
    args = parser.parse_args()
    build = args.build.resolve()
    source = Path(__file__).with_name("netplay_peer.cpp").resolve()
    commands = json.loads((build / "compile_commands.json").read_text())
    entry = next(c for c in commands if c["file"].endswith("/main.cpp"))
    windows = os.name == "nt"
    def split(value):
        return [v.strip('"') for v in shlex.split(value, posix=not windows)]
    command = split(entry["command"])
    obj = str(build / "netplay-peer.o")
    command[command.index("-o") + 1] = obj
    command[command.index("-c") + 1] = str(source)
    subprocess.run(command, cwd=entry["directory"], check=True)
    if windows:
        target = build / "CMakeFiles/devilutionx.dir"
        objects = split((target / "objects1.rsp").read_text())
        if sum(v.endswith("/main.cpp.obj") for v in objects) != 1:
            raise RuntimeError("expected exactly one engine main object")
        objects = [obj if v.endswith("/main.cpp.obj") else v for v in objects]
        response = build / "netplay-peer-objects.rsp"
        response.write_text("\n".join('"' + v + '"' for v in objects))
        link = split((target / "link.txt").read_text().splitlines()[-1])
        begin = link.index("-Wl,--whole-archive")
        end = link.index("-Wl,--no-whole-archive")
        link[begin:end + 1] = ["@" + str(response)]
        libraries = split((target / "linkLibs.rsp").read_text())
        libraries = [v for v in libraries if "SDL2main" not in v and v != "-Wl,--undefined=WinMain"]
        library_response = build / "netplay-peer-libraries.rsp"
        library_response.write_text("\n".join('"' + v + '"' for v in libraries))
        link = ["@" + str(library_response) if v.endswith("linkLibs.rsp") else v for v in link]
        link = [v for v in link if v != "-mwindows" and not v.startswith("-Wl,--out-implib")]
        link[link.index("-o") + 1] = str(build / "netplay-peer.exe")
        subprocess.run(link, cwd=build, check=True)
        print(build / "netplay-peer.exe")
        return
    lines = subprocess.check_output(["ninja", "-t", "commands", "devilutionx"], cwd=build, text=True).splitlines()
    link = shlex.split(lines[-1])
    link = link[link.index("&&") + 1:]
    if "&&" in link:
        link = link[:link.index("&&")]
    mains = [i for i, value in enumerate(link) if value.endswith("/main.cpp.o")]
    if len(mains) != 1:
        raise RuntimeError("expected exactly one engine main object")
    link[mains[0]] = obj
    link[link.index("-o") + 1] = str(build / "netplay-peer")
    link = [v for v in link if not v.startswith("-Wl,--dependency-file=")]
    subprocess.run(link, cwd=build, check=True)
    print(build / "netplay-peer")

if __name__ == "__main__":
    main()

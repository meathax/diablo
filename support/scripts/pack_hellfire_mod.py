#!/usr/bin/env python3
"""Pack redistributable Hellfire assets with smpq (run in Linux/WSL)."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def pack(source: Path, output: Path) -> None:
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise ValueError(f"refusing to replace archive: {output}")
    files = sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file())
    if not files or "manifest.ini" not in files:
        raise ValueError("Hellfire mod assets or manifest are missing")
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("Hellfire assets must not contain symlinks")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["smpq", "-c", "-M", "1", "-A", str(output), *files], cwd=source, check=True)
    # Prove that packing preserved every file, including the Lua and TSV data.
    with tempfile.TemporaryDirectory() as temporary:
        subprocess.run(["smpq", "-x", str(output)], cwd=temporary, check=True)
        extracted = Path(temporary)
        actual = sorted(p.relative_to(extracted).as_posix() for p in extracted.rglob("*") if p.is_file())
        if actual != files or any((extracted / name).read_bytes() != (source / name).read_bytes() for name in files):
            raise ValueError("packed Hellfire mod failed round-trip verification")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    pack(args.source, args.output)

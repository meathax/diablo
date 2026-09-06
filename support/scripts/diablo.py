#!/usr/bin/env python3
"""Reproducible project preflight. Never writes private game data or donor trees."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / ".mister/source-lock.json"
DATA_FILES = {
    "DIABDAT.MPQ": 517501282,
    "hellfire.mpq": 65502336,
    "hfmonk.mpq": 37658368,
    "hfmusic.mpq": 34379360,
    "hfvoice.mpq": 37743520,
}


class GateError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def command(args: list[str], timeout: int = 120, include_stderr: bool = False) -> str:
    result = subprocess.run(args, text=True, encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise GateError(f"Command failed ({result.returncode}): {args[0]}\n"
                        + (result.stderr or result.stdout)[-3000:])
    return (result.stdout + (result.stderr if include_stderr else "")).strip()


def git(path: Path, *args: str, timeout: int = 120) -> str:
    # Scoped trust for the explicitly named donor; never change global Git config.
    return command(["git", "-c", f"safe.directory={path.resolve().as_posix()}",
                    "-C", str(path), *args], timeout)


def load_lock() -> dict:
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    if data.get("schema") != "diablo-source-lock-v1":
        raise GateError("Unsupported source lock schema")
    for name, source in data["sources"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise GateError(f"Unsafe source identifier: {name!r}")
        if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
            raise GateError(f"Unpinned source: {name}")
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git",
                            source["url"]):
            raise GateError(f"Unsupported source URL: {name}")
    return data


def inspect_source(path: Path, source: dict) -> dict:
    if git(path, "rev-parse", "HEAD") != source["commit"]:
        raise GateError(f"HEAD differs from lock: {path}")
    if git(path, "status", "--porcelain", "--untracked-files=all"):
        raise GateError(f"Source checkout contains modifications/untracked files: {path}")
    remote = git(path, "remote", "get-url", "origin")
    if remote.removesuffix(".git").lower() != source["url"].removesuffix(".git").lower():
        raise GateError(f"Origin differs from lock: {path}")
    licenses = {}
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        if (path / name).is_file():
            licenses[name] = sha256(path / name)
    return {"path": str(path), "commit": source["commit"], "origin": remote,
            "tree": git(path, "rev-parse", "HEAD^{tree}"),
            "clean": True, "license_hashes": licenses,
            "submodules": git(path, "submodule", "status", "--recursive")}


def fetch_sources(args: argparse.Namespace) -> dict:
    lock = load_lock()
    selected = args.source or ["devilutionx", "template", "blood"]
    results = {}
    for name in selected:
        if name not in lock["sources"]:
            raise GateError(f"Unknown source: {name}")
        source = lock["sources"][name]
        if "local" in source:
            path = Path(source["local"])
            if not path.is_dir():
                raise GateError(f"Required local donor unavailable: {path}")
        else:
            path = ROOT / ".work/sources" / name
            if not path.exists():
                path.mkdir(parents=True)
                git(path, "init")
                git(path, "remote", "add", "origin", source["url"])
            # Never overwrite even an incomplete checkout with unexpected content.
            if git(path, "status", "--porcelain", "--untracked-files=all"):
                raise GateError(f"Refusing to alter dirty source checkout: {path}")
            try:
                head = git(path, "rev-parse", "--verify", "HEAD")
            except GateError:
                head = None
            if head and head != source["commit"]:
                raise GateError(f"Refusing to replace a different checkout: {path}")
            remote = git(path, "remote", "get-url", "origin")
            if remote != source["url"]:
                raise GateError(f"Refusing unexpected source origin: {path}")
            if head is None:
                git(path, "fetch", "--depth", "1", "origin", source["commit"], timeout=600)
                git(path, "checkout", "--detach", source["commit"])
        results[name] = inspect_source(path, source)
    return {"sources": results, "dependency_closure_verified": False}


def inspect_mpq(path: Path) -> dict:
    """Structural v0 bounds check only; cannot validate compressed member CRCs."""
    size = path.stat().st_size
    with path.open("rb") as stream:
        header = stream.read(32)
    if len(header) != 32:
        raise GateError(f"Truncated MPQ header: {path.name}")
    magic, header_size, archive_size, version, shift, hashes, blocks, nhash, nblock = (
        struct.unpack("<4sIIHHIIII", header))
    if magic != b"MPQ\x1a" or header_size != 32 or version != 0:
        raise GateError(f"Unsupported MPQ layout (needs engine probe): {path.name}")
    if archive_size > size or archive_size < header_size or shift > 16:
        raise GateError(f"Invalid MPQ archive bounds: {path.name}")
    for offset, count in ((hashes, nhash), (blocks, nblock)):
        if count == 0 or offset < header_size or offset + count * 16 > archive_size:
            raise GateError(f"Invalid MPQ table extent: {path.name}")
    return {"bytes": size, "sha256": sha256(path), "mpq_version": version,
            "archive_bytes": archive_size, "trailing_bytes": size - archive_size,
            "hash_entries": nhash, "block_entries": nblock,
            "structural_bounds": "pass", "engine_member_validation": "pending P09"}


def verify_data(_args: argparse.Namespace) -> dict:
    directory = ROOT / "game"
    if directory.is_symlink() or directory.resolve() != directory:
        raise GateError("Private data directory must not redirect outside project")
    result = {}
    for name, observed_size in DATA_FILES.items():
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise GateError(f"Missing or redirected private archive: {name}")
        result[name] = inspect_mpq(path)
        result[name]["planning_size_matches"] = result[name]["bytes"] == observed_size
    manifest = ROOT / ".mister/evidence/private/game-data.json"
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous["files"] != result:
            raise GateError("Private data identity changed; preserve and review the existing manifest")
    else:
        write_json(manifest, {"schema": "diablo-private-data-v1", "files": result})
    return {"manifest": str(manifest.relative_to(ROOT)), "manifest_sha256": sha256(manifest),
            "archive_count": len(result), "total_bytes": sum(x["bytes"] for x in result.values()),
            "scope": "SHA-256 identity and MPQ header/table bounds only; not engine compatibility"}


def doctor(_args: argparse.Namespace) -> dict:
    load_lock()
    tools = {}
    for name in ("python", "git", "cmake", "docker", "wsl", "verilator-safe"):
        tools[name] = shutil.which(name)
    runner = Path("C:/Users/meath/.codex/skills/mister-rbf-build/scripts/quartus_flow.ps1")
    capabilities = None
    if runner.exists():
        capabilities = json.loads(command([
            "C:/Program Files/PowerShell/7/pwsh.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-WindowStyle", "Hidden", "-File", str(runner), "-Action", "Capabilities"]))
    required = ("workflowLease", "unregisteredProcessAdmission", "inferenceAudit",
                "timingAudit", "authenticatedAcceptance", "seedSweep")
    gaps = [key for key in required if not (capabilities or {}).get(key, False)]
    return {"python_version": sys.version, "tools": tools, "quartus_capabilities": capabilities,
            "quartus_blockers": gaps, "production_build_ready": False,
            "status": "blocked" if gaps else "preflight-only",
            "other_pending_gates": ["ARM sysroot/runtime probe", "DDR reservation hardware proof",
                                    "complete dependency lock", "target device availability"]}


def run_tests(_args: argparse.Namespace) -> dict:
    test_sources = {str(path.relative_to(ROOT)): sha256(path)
                    for path in sorted((ROOT / "support/tests").glob("test_*.py"))}
    output = command([sys.executable, "-m", "unittest", "discover", "-s",
                      str(ROOT / "support/tests"), "-v"], include_stderr=True)
    tool_sources = {str(path.relative_to(ROOT)): sha256(path)
                    for path in sorted((ROOT / "support/scripts").glob("*.py"))}
    return {"suite": "foundation", "result": "pass", "test_sources": test_sources,
            "tool_sources": tool_sources, "output": output}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("doctor").set_defaults(handler=doctor)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--locked", action="store_true", required=True)
    fetch.add_argument("--source", action="append")
    fetch.set_defaults(handler=fetch_sources)
    sub.add_parser("verify-data").set_defaults(handler=verify_data)
    tests = sub.add_parser("test")
    tests.add_argument("--suite", choices=["foundation"], required=True)
    tests.set_defaults(handler=run_tests)
    args = parser.parse_args()
    receipt = {"schema": "diablo-operation-receipt-v1", "operation": args.operation,
               "arguments": sys.argv[1:], "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "script_sha256": sha256(Path(__file__)), "source_lock_sha256": sha256(LOCK)}
    try:
        receipt["result"] = args.handler(args)
        receipt["status"] = "blocked" if receipt["result"].get("status") == "blocked" else "pass"
        code = 2 if receipt["status"] == "blocked" else 0
    except (GateError, OSError, subprocess.TimeoutExpired, ValueError) as error:
        receipt.update(status="fail", error=str(error))
        code = 1
    receipt["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    target = ROOT / ".mister/evidence" / (args.operation + "-" + uuid.uuid4().hex + ".json")
    write_json(target, receipt)
    print(json.dumps({"status": receipt["status"], "receipt": str(target.relative_to(ROOT)),
                      "error": receipt.get("error")}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

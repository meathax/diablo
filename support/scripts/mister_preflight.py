"""Verify a staged Diablo package on a reachable MiSTer share.

This is a read-only deployment preflight.  It binds the remote package to the
candidate manifest and records target inventory, but it deliberately does not
claim physical video, audio, input, gameplay or performance acceptance.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import uuid
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support.scripts import candidate_manifest, package_release  # noqa: E402


SCHEMA = "diablo-mister-preflight-v1"
# MiSTer.ini is stored at the SD-card root on the observed target; core-specific
# settings such as cores_recent.cfg live under config/.
DEFAULT_PROBES = ("MiSTer", "menu.rbf", "MiSTer.ini", "config/cores_recent.cfg")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("remote relative path must be a non-empty string")
    normalized = value.replace("\\", "/")
    if "//" in normalized:
        raise ValueError(f"remote relative path contains an empty component: {value}")
    path = PurePosixPath(normalized)
    parts = path.parts
    if not parts or path.is_absolute() or ":" in parts[0] or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"remote relative path escapes target root: {value}")
    return "/".join(parts)


def join_remote(root: Path, relative: str) -> Path:
    safe = safe_relative(relative)
    return root.joinpath(*PurePosixPath(safe).parts)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _record_file(path: Path, relative: str, expected_sha256: str | None = None,
                 expected_bytes: int | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {"path": relative, "exists": path.is_file() and not path.is_symlink()}
    if record["exists"]:
        record["bytes"] = path.stat().st_size
        record["sha256"] = sha256_file(path)
        record["bytes_match"] = expected_bytes is None or record["bytes"] == expected_bytes
        record["sha256_match"] = expected_sha256 is None or record["sha256"] == expected_sha256
        record["match"] = bool(record["bytes_match"] and record["sha256_match"])
    else:
        record.update({"bytes": None, "sha256": None, "bytes_match": False,
                       "sha256_match": False, "match": False})
    return record


def _manifest_records(package: Path) -> list[dict[str, Any]]:
    value = _json(package / package_release.PACKAGE_FILENAME)
    records = value.get("files") if isinstance(value, dict) else None
    if not isinstance(records, list):
        raise ValueError("package manifest files must be a list")
    return [record for record in records if isinstance(record, dict)]


def verify_remote_package(remote_root: Path, package: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    try:
        expected = _manifest_records(package)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        return [], [f"local package manifest cannot be read: {error}"]
    # The package manifest is intentionally not self-listed (a self-hash would
    # be recursive), so bind it explicitly to the remote copy before trusting
    # its file records.  Otherwise a swapped metadata file could evade the
    # otherwise complete artifact hash check.
    manifest_path = package / package_release.PACKAGE_FILENAME
    try:
        manifest_record = _record_file(
            remote_root / package_release.PACKAGE_FILENAME,
            package_release.PACKAGE_FILENAME,
            sha256_file(manifest_path),
            manifest_path.stat().st_size,
        )
    except OSError as error:
        return [], [f"local package manifest cannot be hashed: {error}"]
    records.append(manifest_record)
    if not manifest_record["exists"]:
        problems.append(f"remote package file is missing: {package_release.PACKAGE_FILENAME}")
    elif not manifest_record["match"]:
        problems.append(f"remote package file hash/size mismatch: {package_release.PACKAGE_FILENAME}")
    for item in expected:
        relative = item.get("path")
        try:
            safe = safe_relative(relative)
            remote = join_remote(remote_root, safe)
        except ValueError as error:
            problems.append(str(error))
            continue
        record = _record_file(remote, safe, item.get("sha256"), item.get("bytes"))
        records.append(record)
        if not record["exists"]:
            problems.append(f"remote package file is missing: {safe}")
        elif not record["match"]:
            problems.append(f"remote package file hash/size mismatch: {safe}")
    return records, problems


def probe_target(target_root: Path, probes: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    for relative in probes:
        try:
            safe = safe_relative(relative)
            path = join_remote(target_root, safe)
        except ValueError as error:
            problems.append(str(error))
            continue
        record = _record_file(path, safe)
        if safe == "MiSTer" and record["exists"]:
            with path.open("rb") as handle:
                record["elf_header"] = handle.read(4) == bytes([0x7F]) + b"ELF"
            if not record["elf_header"]:
                problems.append("remote MiSTer executable is not an ARM ELF")
        records.append(record)
        if not record["exists"]:
            problems.append(f"target probe is missing: {safe}")
    return records, problems


def _write_immutable(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"refusing to replace immutable preflight receipt: {path}")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise RuntimeError(f"refusing to replace immutable preflight receipt: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def verify(root: Path, candidate_path: Path, package: Path, target_root: Path,
           remote_package: str, target_name: str, target_host: str,
           board_profile: str, probes: Iterable[str]) -> dict[str, Any]:
    started = utc_now()
    problems: list[str] = []
    candidate_record: dict[str, Any] = {"manifest": str(candidate_path), "candidate_id": None, "source_id": None}
    manifest_problems = candidate_manifest.verify_manifest(root, candidate_path)
    if manifest_problems:
        problems.extend("candidate manifest: " + item for item in manifest_problems)
    else:
        manifest = _json(candidate_path)
        candidate_record.update({"candidate_id": manifest["candidate_id"], "source_id": manifest["source_id"],
                                 "manifest_sha256": sha256_file(candidate_path)})
    package_problems = package_release.verify_package(package, board_profile)
    problems.extend("local package: " + item for item in package_problems)
    try:
        remote_relative = safe_relative(remote_package)
        remote_package_root = join_remote(target_root, remote_package)
    except ValueError as error:
        remote_package_root = target_root
        remote_relative = remote_package
        problems.append(str(error))
    if not target_root.is_dir():
        problems.append(f"target root is not accessible: {target_root}")
    remote_files, remote_problems = verify_remote_package(remote_package_root, package)
    problems.extend(remote_problems)
    target_probes, probe_problems = probe_target(target_root, probes)
    problems.extend(probe_problems)
    finished = utc_now()
    return {
        "schema": SCHEMA,
        "status": "pass" if not problems else "fail",
        "scope": "read-only MiSTer Samba deployment preflight; no physical acceptance",
        "started_utc": started,
        "finished_utc": finished,
        "candidate": candidate_record,
        "package": {"local": str(package), "board_profile": board_profile,
                     "remote_relative": remote_relative, "remote_files": remote_files},
        "target": {"name": target_name, "host": target_host, "root": str(target_root),
                   "probes": target_probes},
        "limitations": ["No physical video/audio/input observer was used",
                        "No gameplay, campaign, save, multiplayer or performance result is implied",
                        "The staged package was not installed as the active core"],
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    verify_parser = parser.add_subparsers(dest="command", required=True).add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.add_argument("--candidate-manifest", type=Path, required=True)
    verify_parser.add_argument("--package", type=Path, required=True)
    verify_parser.add_argument("--target-root", type=Path, required=True)
    verify_parser.add_argument("--remote-package", required=True)
    verify_parser.add_argument("--target-name", required=True)
    verify_parser.add_argument("--target-host", required=True)
    verify_parser.add_argument("--board-profile", required=True)
    verify_parser.add_argument("--probe", action="append", dest="probes", default=list(DEFAULT_PROBES))
    verify_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    candidate_path = args.candidate_manifest if args.candidate_manifest.is_absolute() else root / args.candidate_manifest
    package = args.package if args.package.is_absolute() else root / args.package
    output = args.output if args.output.is_absolute() else root / args.output
    receipt = verify(root, candidate_path, package, args.target_root, args.remote_package,
                     args.target_name, args.target_host, args.board_profile, args.probes)
    _write_immutable(output, receipt)
    print(json.dumps({"receipt": str(output), "status": receipt["status"],
                      "candidate_id": receipt["candidate"]["candidate_id"]}, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

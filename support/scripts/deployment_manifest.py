"""Create and verify a runtime-only MiSTer deployment manifest.

Development candidate manifests bind a checkout, Git identity and source
inputs. A deployed package cannot require those paths. Deployment manifests
bind the installed runtime, target board, launcher and complete asset tree.
Version one remains readable for old local fixtures; new release packages use
version two.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Iterable


SCHEMA = "diablo-deployment-manifest-v2"
LEGACY_SCHEMA = "diablo-deployment-manifest-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_ROLES = {"rbf", "engine", "abi", "launcher"}
LEGACY_REQUIRED_ROLES = {"rbf", "engine", "abi"}
RUNTIME_ROLE_PATHS = {"engine": "devilutionx", "rbf": "Diablo.rbf",
                      "abi": "transport_abi.hex", "launcher": "diablo_launcher.py"}
PRIVATE_MARKERS = (".mpq", ".sav", ".sve", "private", "secret", "password", "token")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _safe_relative(root: Path, value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be a relative path below the deployment root")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} escapes the deployment root") from error
    return path


def relative_file(root: Path, value: str, label: str) -> Path:
    path = _safe_relative(root, value, label)
    candidate = root / path
    resolved = candidate.resolve()
    if candidate.is_symlink() or not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"{label} must be a real file: {path}")
    return resolved


def _asset_paths(root: Path, value: str) -> tuple[Path, list[Path]]:
    path = _safe_relative(root, value, "assets directory")
    candidate = root / path
    resolved = candidate.resolve()
    if candidate.is_symlink() or resolved.is_symlink() or not resolved.is_dir():
        raise ValueError(f"assets directory must be a real directory: {path}")
    files: list[Path] = []
    for entry in sorted(resolved.rglob("*")):
        relative = entry.relative_to(resolved).as_posix()
        lowered = relative.lower()
        if any(marker in lowered for marker in PRIVATE_MARKERS):
            raise ValueError(f"assets directory contains private-looking file: {relative}")
        if entry.is_symlink():
            raise ValueError(f"assets directory must not contain symlinks: {relative}")
        if entry.is_file():
            files.append(entry)
        elif not entry.is_dir():
            raise ValueError(f"assets directory contains unsupported entry: {relative}")
    if not files:
        raise ValueError("assets directory must contain at least one file")
    return resolved, files


def asset_tree_record(root: Path, value: str = "assets") -> dict[str, object]:
    assets_root, files = _asset_paths(root, value)
    records = [{"path": path.relative_to(assets_root).as_posix(),
                "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in files]
    records.sort(key=lambda record: str(record["path"]))
    total = sum(int(record["bytes"]) for record in records)
    return {"path": Path(value).as_posix(), "bytes": total,
            "sha256": hashlib.sha256(canonical_bytes(records)).hexdigest(), "files": records}


def artifact_record(root: Path, role: str, value: str) -> dict[str, object]:
    path = relative_file(root, value, f"{role} artifact")
    return {"role": role, "path": path.relative_to(root.resolve()).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def make_manifest(root: Path, candidate_id: str, source_id: str, abi_digest: str,
                  board_profile: str, artifacts: Iterable[tuple[str, str]],
                  assets_path: str | None = None) -> dict[str, object]:
    if not HEX64.fullmatch(candidate_id) or not HEX64.fullmatch(source_id) or not HEX64.fullmatch(abi_digest):
        raise ValueError("candidate_id, source_id and abi_digest must be 64 lowercase hex characters")
    if not board_profile:
        raise ValueError("board_profile is required")
    records = [artifact_record(root, role, value) for role, value in artifacts]
    roles = [str(record["role"]) for record in records]
    if assets_path is None and set(roles) == LEGACY_REQUIRED_ROLES and len(roles) == len(set(roles)):
        return {"schema": LEGACY_SCHEMA, "status": "pass", "candidate_id": candidate_id,
                "source_id": source_id, "abi_digest": abi_digest, "board_profile": board_profile,
                "private_data_excluded": True,
                "created_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
                "artifacts": sorted(records, key=lambda record: str(record["role"]))}
    if set(roles) != REQUIRED_ROLES or len(roles) != len(set(roles)):
        raise ValueError(f"deployment artifacts must contain exactly these roles: {sorted(REQUIRED_ROLES)}")
    assets = asset_tree_record(root, assets_path or "assets")
    return {"schema": SCHEMA, "status": "pass", "candidate_id": candidate_id,
            "source_id": source_id, "abi_digest": abi_digest, "board_profile": board_profile,
            "private_data_excluded": True,
            "created_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "artifacts": sorted(records, key=lambda record: str(record["role"])),
            "runtime_assets": assets}


def _verify_assets(root: Path, record: object, problems: list[str]) -> None:
    if not isinstance(record, dict):
        problems.append("deployment runtime_assets must be an object")
        return
    value = record.get("path")
    if not isinstance(value, str):
        problems.append("deployment runtime_assets path is missing")
        return
    try:
        assets_root, current = _asset_paths(root, value)
    except ValueError as error:
        problems.append(str(error))
        return
    listed = record.get("files")
    if not isinstance(listed, list):
        problems.append("deployment runtime_assets files must be a list")
        return
    seen: set[str] = set()
    for item in listed:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            problems.append("deployment asset record must be an object with a path")
            continue
        relative = item["path"]
        if relative in seen:
            problems.append(f"deployment asset paths must be unique: {relative}")
            continue
        seen.add(relative)
        try:
            path = relative_file(assets_root, relative, "deployment asset")
            if item.get("bytes") != path.stat().st_size or item.get("sha256") != sha256_file(path):
                problems.append(f"deployment asset bytes/hash mismatch: {relative}")
        except ValueError as error:
            problems.append(str(error))
    current_records = [{"path": path.relative_to(assets_root).as_posix(),
                        "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in current]
    current_records.sort(key=lambda item: str(item["path"]))
    if seen != {str(item["path"]) for item in current_records}:
        problems.append("deployment runtime_assets files do not cover exactly the asset tree")
    total = sum(int(item["bytes"]) for item in current_records)
    digest = hashlib.sha256(canonical_bytes(current_records)).hexdigest()
    if record.get("bytes") != total or record.get("sha256") != digest:
        problems.append("deployment runtime_assets tree hash/size mismatch")


def verify_manifest(root: Path, manifest_path: Path, expected_board_profile: str | None = None) -> list[str]:
    root = root.resolve()
    if manifest_path.is_symlink():
        return [f"deployment manifest must not be a symlink: {manifest_path}"]
    try:
        manifest_path.resolve().relative_to(root)
    except ValueError:
        return ["deployment manifest must be below the deployment root"]
    if not manifest_path.is_file():
        return [f"deployment manifest is missing: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"deployment manifest is invalid: {error}"]
    problems: list[str] = []
    schema = manifest.get("schema")
    if schema not in {SCHEMA, LEGACY_SCHEMA}:
        problems.append("unsupported deployment manifest schema")
    if manifest.get("status") != "pass":
        problems.append("deployment manifest status is not pass")
    for field in ("candidate_id", "source_id", "abi_digest"):
        if not HEX64.fullmatch(str(manifest.get(field, ""))):
            problems.append(f"deployment manifest {field} is not a 64-hex identity")
    board_profile = manifest.get("board_profile")
    if not isinstance(board_profile, str) or not board_profile:
        problems.append("deployment manifest board_profile is missing")
    elif expected_board_profile is not None and board_profile != expected_board_profile:
        problems.append("deployment manifest board_profile does not match target")
    if manifest.get("private_data_excluded") is not True:
        problems.append("deployment manifest does not declare private data exclusion")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return problems + ["deployment manifest artifacts must be a list"]
    roles: set[str] = set()
    for record in artifacts:
        if not isinstance(record, dict):
            problems.append("deployment artifact record must be an object")
            continue
        role = record.get("role")
        if not isinstance(role, str) or not role or role in roles:
            problems.append("deployment artifact roles must be unique non-empty strings")
            continue
        roles.add(role)
        try:
            path = relative_file(root, str(record.get("path", "")), f"{role} artifact")
            if record.get("bytes") != path.stat().st_size or record.get("sha256") != sha256_file(path):
                problems.append(f"deployment artifact bytes/hash mismatch: {role}")
        except ValueError as error:
            problems.append(str(error))
    required = LEGACY_REQUIRED_ROLES if schema == LEGACY_SCHEMA else REQUIRED_ROLES
    if roles != required:
        problems.append(f"deployment artifacts must contain exactly these roles: {sorted(required)}")
    if schema == SCHEMA:
        for record in artifacts:
            if isinstance(record, dict) and record.get("role") in RUNTIME_ROLE_PATHS:
                expected_path = RUNTIME_ROLE_PATHS[record["role"]]
                if record.get("path") != expected_path:
                    problems.append(f"deployment artifact path for {record['role']} must be {expected_path}")
        _verify_assets(root, manifest.get("runtime_assets"), problems)
    return problems


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + os.urandom(8).hex() + ".tmp")
    try:
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise RuntimeError(f"refusing to overwrite immutable deployment manifest: {path}") from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--abi-digest", required=True)
    parser.add_argument("--board-profile", required=True)
    parser.add_argument("--artifact", action="append", nargs=2, metavar=("ROLE", "PATH"), required=True)
    parser.add_argument("--assets", default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    if args.verify:
        problems = verify_manifest(root, output, args.board_profile)
        print(json.dumps({"ok": not problems, "problems": problems}, sort_keys=True))
        return 0 if not problems else 1
    try:
        manifest = make_manifest(root, args.candidate_id, args.source_id, args.abi_digest, args.board_profile,
                                 args.artifact, args.assets)
        write_manifest(output, manifest)
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "manifest": str(output), "candidate_id": args.candidate_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build and verify a clean, runtime-only MiSTer deployment package.

The release contains the ARM engine, matching RBF and ABI, a project-owned
target launcher, and the complete redistributable engine asset tree. Private
game data, saves, checkouts and build directories are never copied. The output
directory is published atomically and every metadata file is immutable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support.scripts import candidate_manifest, deployment_manifest  # noqa: E402


SCHEMA = "diablo-package-manifest-v2"
LEGACY_SCHEMA = "diablo-package-manifest-v1"
DEPLOYMENT_FILENAME = "deployment.json"
PACKAGE_FILENAME = "package-manifest.json"
RUNTIME_FILES = ("devilutionx", "Diablo.rbf", "transport_abi.hex", "diablo_launcher.py")
RUNTIME_ROLES = {"engine", "rbf", "abi", "launcher"}
RUNTIME_ROLE_PATHS = {"engine": "devilutionx", "rbf": "Diablo.rbf",
                      "abi": "transport_abi.hex", "launcher": "diablo_launcher.py"}
PACKAGE_DOCUMENTS = ("NOTICE.txt", "SETUP.md")
TOP_LEVEL_FILES = set(RUNTIME_FILES) | {DEPLOYMENT_FILENAME, PACKAGE_FILENAME}
TOP_LEVEL_FILES.update(PACKAGE_DOCUMENTS)
PRIVATE_MARKERS = (".mpq", ".sav", ".sve", "private", "secret", "password", "token")

NOTICE_TEXT = """Diablo MiSTer runtime package

This package contains the project runtime, FPGA core, transport ABI, launcher,
and redistributable engine assets. It intentionally excludes licensed Diablo and
Hellfire data files, save games, private captures, credentials, and build trees.

Supply legally obtained game data on the target according to SETUP.md. The
package and its manifests are content-addressed; do not edit files in place.
"""

SETUP_TEXT = """# Diablo MiSTer package setup

1. Copy this package to a clean MiSTer SD-card directory without changing any
   file names or manifest contents.
2. Supply your own legally obtained Diablo or Hellfire data directory. Licensed
   MPQ files and save/configuration data are deliberately outside this package.
3. Verify `package-manifest.json` and `deployment.json` before activation.
4. Use the project launcher/menu integration to select a campaign. The launcher
   creates a campaign-specific writable save directory and refuses mismatched
   core, ABI, board, or candidate identities.
5. Keep the previous package available until an update has completed a second
   launch and save/load smoke check. If an update is interrupted, leave the
   active release selected and retry from a fresh staging directory.

The package does not claim physical video, audio, input, gameplay, performance,
or release acceptance by itself; those claims require the qualification receipts
listed in the completion plan.
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _identity(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _safe_source(root: Path, value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be a relative file below the source root")
    candidate = root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} escapes the source root") from error
    if candidate.is_symlink() or resolved.is_symlink() or not resolved.is_file():
        raise ValueError(f"{label} must be a real file: {path}")
    lowered_parts = {part.lower() for part in path.parts}
    lowered_name = path.name.lower()
    if "game" in lowered_parts or any(marker in lowered_name for marker in PRIVATE_MARKERS):
        raise ValueError(f"{label} points at private game data: {path}")
    return resolved


def _safe_asset_source(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("assets source must be a relative directory below the source root")
    candidate = root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("assets source escapes the source root") from error
    if candidate.is_symlink() or resolved.is_symlink() or not resolved.is_dir():
        raise ValueError(f"assets source must be a real directory: {path}")
    files = list(resolved.rglob("*"))
    if not any(entry.is_file() for entry in files):
        raise ValueError("assets source must contain at least one file")
    for entry in files:
        relative = entry.relative_to(resolved).as_posix().lower()
        if any(marker in relative for marker in PRIVATE_MARKERS):
            raise ValueError(f"assets source contains private-looking path: {relative}")
        if entry.is_symlink():
            raise ValueError(f"assets source must not contain symlinks: {entry}")
        if not entry.is_file() and not entry.is_dir():
            raise ValueError(f"assets source contains unsupported entry: {entry}")
    return resolved


def _safe_package_file(root: Path, value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be a relative package path")
    candidate = root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} escapes the package root") from error
    if candidate.is_symlink() or resolved.is_symlink() or not resolved.is_file():
        raise ValueError(f"{label} must be a real package file: {path}")
    return resolved


def _artifact_record(root: Path, path: str, role: str) -> dict[str, object]:
    resolved = _safe_package_file(root, path, f"{role} artifact")
    return {"role": role, "path": resolved.relative_to(root.resolve()).as_posix(),
            "bytes": resolved.stat().st_size, "sha256": sha256_file(resolved)}


def _asset_records(root: Path) -> list[dict[str, object]]:
    assets = root / "assets"
    if not assets.is_dir() or assets.is_symlink():
        raise ValueError("package assets directory is missing")
    records: list[dict[str, object]] = []
    for path in sorted(assets.rglob("*")):
        relative = path.relative_to(root).as_posix()
        lowered = relative.lower()
        if any(marker in lowered for marker in PRIVATE_MARKERS):
            raise ValueError(f"package contains private-data-looking file: {relative}")
        if path.is_symlink():
            raise ValueError(f"package contains symlink: {relative}")
        if path.is_file():
            records.append(_artifact_record(root, relative, "asset"))
        elif not path.is_dir():
            raise ValueError(f"package contains unsupported asset entry: {relative}")
    if not records:
        raise ValueError("package assets directory is empty")
    return records


def _immutable_write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"refusing to overwrite immutable package manifest: {path}")
    temporary = path.with_name(path.name + "." + os.urandom(8).hex() + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.link(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _parse_artifact(value: str) -> tuple[str, str]:
    role, separator, path = value.partition("=")
    if not separator or not role or not path:
        raise ValueError("artifact must be ROLE=PATH")
    if role not in RUNTIME_ROLES:
        raise ValueError(f"unsupported runtime artifact role: {role}")
    return role, path


def _package_file_records(root: Path) -> list[dict[str, object]]:
    records = [_artifact_record(root, name, "runtime" if name in RUNTIME_FILES
                                else "deployment-manifest" if name == DEPLOYMENT_FILENAME
                                else "release-document")
               for name in (*RUNTIME_FILES, DEPLOYMENT_FILENAME, *PACKAGE_DOCUMENTS)]
    records.extend(_asset_records(root))
    return records


def make_package_manifest(root: Path, candidate_id: str, source_id: str, board_profile: str,
                          deployment_path: Path) -> dict[str, object]:
    if not _identity(candidate_id) or not _identity(source_id):
        raise ValueError("candidate_id and source_id must be 64 lowercase hex characters")
    if not board_profile:
        raise ValueError("board_profile is required")
    deployment_relative = deployment_path.resolve().relative_to(root.resolve()).as_posix()
    return {
        "schema": SCHEMA,
        "status": "pass",
        "candidate_id": candidate_id,
        "source_id": source_id,
        "board_profile": board_profile,
        "private_data_excluded": True,
        "deployment_manifest": {"path": deployment_relative, "sha256": sha256_file(deployment_path)},
        "files": _package_file_records(root),
    }


def _manifest_from_candidate(root: Path, manifest_path: Path) -> dict[str, Any]:
    problems = candidate_manifest.verify_manifest(root, manifest_path)
    if problems:
        raise ValueError("candidate manifest verification failed: " + "; ".join(problems))
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"candidate manifest is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("candidate manifest must be a JSON object")
    return value


def _candidate_hashes(candidate: dict[str, Any]) -> set[str]:
    return {str(record.get("sha256")) for record in candidate.get("artifacts", [])
            if isinstance(record, dict) and isinstance(record.get("sha256"), str)}


def _copy_asset_tree(source: Path, destination: Path, candidate_hashes: set[str]) -> None:
    for source_path in sorted(source.rglob("*")):
        relative = source_path.relative_to(source)
        target = destination / relative
        if source_path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        digest = sha256_file(source_path)
        if digest not in candidate_hashes:
            raise ValueError(f"asset source is not an artifact in the selected candidate manifest: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)


def create_package(root: Path, candidate_path: Path, artifacts: Iterable[tuple[str, str]],
                   board_profile: str, output: Path, assets: str | None = None) -> dict[str, object]:
    root = root.resolve()
    candidate_path = candidate_path if candidate_path.is_absolute() else root / candidate_path
    candidate = _manifest_from_candidate(root, candidate_path)
    if output.exists() or output.is_symlink():
        raise ValueError(f"refusing to replace existing package directory: {output}")
    artifact_map = dict(artifacts)
    if set(artifact_map) != RUNTIME_ROLES:
        raise ValueError(f"runtime artifacts must contain exactly {sorted(RUNTIME_ROLES)}")
    candidate_hashes = _candidate_hashes(candidate)
    if assets is None:
        raise ValueError("--assets is required for a complete package")
    asset_source = _safe_asset_source(root, assets)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=output.name + ".", dir=output.parent))
    try:
        target_names = {"engine": "devilutionx", "rbf": "Diablo.rbf", "abi": "transport_abi.hex",
                        "launcher": "diablo_launcher.py"}
        for role, source_value in artifact_map.items():
            source = _safe_source(root, source_value, f"{role} source")
            if sha256_file(source) not in candidate_hashes:
                raise ValueError(f"{role} source is not an artifact in the selected candidate manifest: {source_value}")
            shutil.copyfile(source, temporary / target_names[role])
        _copy_asset_tree(asset_source, temporary / "assets", candidate_hashes)
        (temporary / "NOTICE.txt").write_text(NOTICE_TEXT, encoding="utf-8")
        (temporary / "SETUP.md").write_text(SETUP_TEXT, encoding="utf-8")
        abi_digest = sha256_file(temporary / target_names["abi"])
        deployment = deployment_manifest.make_manifest(
            temporary, str(candidate["candidate_id"]), str(candidate["source_id"]), abi_digest,
            board_profile, (("engine", "devilutionx"), ("rbf", "Diablo.rbf"),
                            ("abi", "transport_abi.hex"), ("launcher", "diablo_launcher.py")), "assets")
        deployment_path = temporary / DEPLOYMENT_FILENAME
        deployment_manifest.write_manifest(deployment_path, deployment)
        package = make_package_manifest(temporary, str(candidate["candidate_id"]),
                                        str(candidate["source_id"]), board_profile, deployment_path)
        _immutable_write(temporary / PACKAGE_FILENAME, package)
        problems = verify_package(temporary, board_profile)
        if problems:
            raise RuntimeError("new package failed self-verification: " + "; ".join(problems))
        temporary.rename(output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"package": str(output), "candidate_id": candidate["candidate_id"],
            "source_id": candidate["source_id"], "board_profile": board_profile}


def verify_package(package: Path, expected_board_profile: str | None = None) -> list[str]:
    package = package.resolve()
    if not package.is_dir() or package.is_symlink():
        return [f"package directory is missing or invalid: {package}"]
    problems: list[str] = []
    files = {path.relative_to(package).as_posix(): path for path in package.rglob("*") if path.is_file()}
    symlinks = [path for path in package.rglob("*") if path.is_symlink()]
    if symlinks:
        problems.append("package contains symlinks")
    for name in files:
        lowered = name.lower()
        if any(marker in lowered for marker in PRIVATE_MARKERS):
            problems.append(f"package contains private-data-looking file: {name}")
    if any(path not in TOP_LEVEL_FILES and not path.startswith("assets/") for path in files):
        unexpected = sorted(path for path in files if path not in TOP_LEVEL_FILES and not path.startswith("assets/"))
        problems.append("package contains unexpected files: " + ", ".join(unexpected))
    manifest_path = package / PACKAGE_FILENAME
    deployment_path = package / DEPLOYMENT_FILENAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return problems + [f"package manifest is invalid: {error}"]
    if not isinstance(manifest, dict):
        return problems + ["package manifest must be a JSON object"]
    if manifest.get("schema") != SCHEMA:
        problems.append("unsupported package manifest schema")
    if manifest.get("status") != "pass":
        problems.append("package manifest status is not pass")
    if manifest.get("private_data_excluded") is not True:
        problems.append("package manifest does not declare private data exclusion")
    for field in ("candidate_id", "source_id"):
        if not _identity(manifest.get(field)):
            problems.append(f"package manifest {field} is not a 64-hex identity")
    board_profile = manifest.get("board_profile")
    if not isinstance(board_profile, str) or not board_profile:
        problems.append("package manifest board_profile is missing")
    elif expected_board_profile is not None and board_profile != expected_board_profile:
        problems.append("package manifest board_profile does not match target")
    deployment_record = manifest.get("deployment_manifest")
    if not isinstance(deployment_record, dict) or deployment_record.get("path") != DEPLOYMENT_FILENAME:
        problems.append("package manifest deployment_manifest path is invalid")
    elif deployment_record.get("sha256") != (sha256_file(deployment_path) if deployment_path.is_file() else None):
        problems.append("package deployment manifest hash does not match")
    if deployment_path.is_file():
        problems.extend(deployment_manifest.verify_manifest(package, deployment_path, expected_board_profile))
    else:
        problems.append("package deployment manifest is missing")
    records = manifest.get("files")
    if not isinstance(records, list):
        problems.append("package manifest files must be a list")
    else:
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                problems.append("package file record must be an object")
                continue
            path = record.get("path")
            if not isinstance(path, str) or path in seen:
                problems.append("package file paths must be unique strings")
                continue
            seen.add(path)
            try:
                resolved = _safe_package_file(package, path, "package file")
                if record.get("bytes") != resolved.stat().st_size or record.get("sha256") != sha256_file(resolved):
                    problems.append(f"package file bytes/hash mismatch: {path}")
            except ValueError as error:
                problems.append(str(error))
        expected_paths = (set(TOP_LEVEL_FILES) - {PACKAGE_FILENAME}) | {path.relative_to(package).as_posix()
                                                 for path in (package / "assets").rglob("*") if path.is_file()}
        if seen != expected_paths:
            problems.append("package manifest files do not cover exactly the runtime files and asset tree")
    deployment_records = []
    if deployment_path.is_file():
        try:
            deployment_records = json.loads(deployment_path.read_text(encoding="utf-8")).get("artifacts", [])
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            deployment_records = []
    for record in deployment_records:
        if isinstance(record, dict) and record.get("role") in RUNTIME_ROLE_PATHS:
            expected_path = RUNTIME_ROLE_PATHS[record["role"]]
            if record.get("path") != expected_path:
                problems.append(f"deployment artifact path for {record['role']} must be {expected_path}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--candidate-manifest", type=Path, required=True)
    create.add_argument("--artifact", action="append", required=True, metavar="ROLE=PATH")
    create.add_argument("--assets", required=True, metavar="PATH")
    create.add_argument("--board-profile", required=True)
    create.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--package", type=Path, required=True)
    verify.add_argument("--board-profile")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            result = create_package(args.root, args.candidate_manifest,
                                    [_parse_artifact(value) for value in args.artifact],
                                    args.board_profile, args.output, args.assets)
        else:
            problems = verify_package(args.package, args.board_profile)
            result = {"package": str(args.package.resolve()), "ok": not problems, "problems": problems}
            if problems:
                print(json.dumps(result))
                return 1
        print(json.dumps(result))
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

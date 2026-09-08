"""Install, update, verify, and roll back a verified Diablo MiSTer package.

The target-facing launcher deliberately remains separate from installation. This
module provides the same transaction contract on a local or mounted target
directory so interrupted copies and rollback can be qualified without touching a
live MiSTer boot. A package is copied into an immutable candidate-named release
directory, then a small activation record is atomically replaced. User data
directories are never copied or removed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support.scripts import package_release


STATE_SCHEMA = "diablo-install-state-v1"
STATE_FILENAME = ".diablo-install.json"
RELEASES_DIRNAME = ".diablo-releases"
STAGING_DIRNAME = ".diablo-staging"


class InstallError(ValueError):
    """Raised when a package cannot be safely installed or activated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_candidate_id(value: object) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise InstallError("package candidate_id is not a 64-character lowercase identity")
    return text


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InstallError(f"invalid JSON file {path}: {error}") from error
    if not isinstance(value, dict):
        raise InstallError(f"JSON file must contain an object: {path}")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _package_identity(package: Path, board_profile: str) -> tuple[dict[str, Any], str]:
    problems = package_release.verify_package(package, board_profile)
    if problems:
        raise InstallError("package verification failed: " + "; ".join(problems))
    manifest = _read_json(package / package_release.PACKAGE_FILENAME)
    candidate_id = _safe_candidate_id(manifest.get("candidate_id"))
    return manifest, candidate_id


def _copy_package(package: Path, staging: Path, fail_after: int | None = None) -> int:
    copied = 0
    for source in sorted(package.rglob("*")):
        relative = source.relative_to(package)
        target = staging / relative
        if source.is_symlink():
            raise InstallError(f"package contains symlink: {relative}")
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not source.is_file():
            raise InstallError(f"package contains unsupported entry: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
        if fail_after is not None and copied >= fail_after:
            raise InstallError(f"simulated interrupted update after {copied} files")
    return copied


def _state_path(target: Path) -> Path:
    return target / STATE_FILENAME


def _load_state(target: Path) -> dict[str, Any] | None:
    path = _state_path(target)
    if not path.exists():
        return None
    state = _read_json(path)
    if state.get("schema") != STATE_SCHEMA:
        raise InstallError("unsupported installation state schema")
    return state


def _relative_release(target: Path, candidate_id: str) -> str:
    return (Path(RELEASES_DIRNAME) / candidate_id).as_posix()


def _release_path(target: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.parts[:1] != (RELEASES_DIRNAME,):
        raise InstallError("activation record points outside the managed release directory")
    result = (target / path).resolve()
    try:
        result.relative_to((target / RELEASES_DIRNAME).resolve())
    except ValueError as error:
        raise InstallError("activation record escapes the managed release directory") from error
    return result


def _state_for(target: Path, manifest: dict[str, Any], candidate_id: str,
               active_release: str, previous: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "status": "pass",
        "board_profile": manifest["board_profile"],
        "active_candidate_id": candidate_id,
        "active_release": active_release,
        "active_package_manifest_sha256": sha256_file(target / active_release / package_release.PACKAGE_FILENAME),
        "previous_candidate_id": previous.get("active_candidate_id") if previous else None,
        "previous_release": previous.get("active_release") if previous else None,
        "user_data_policy": "existing data, saves, and configuration are preserved outside managed releases",
    }


def install_package(package: Path, target: Path, board_profile: str,
                    fail_after: int | None = None) -> dict[str, Any]:
    """Install a package transactionally and return the new activation state."""
    package = package.resolve()
    target = target.resolve()
    manifest, candidate_id = _package_identity(package, board_profile)
    if target.exists() and target.is_symlink():
        raise InstallError("installation target must not be a symlink")
    target.mkdir(parents=True, exist_ok=True)
    releases = target / RELEASES_DIRNAME
    staging_root = target / STAGING_DIRNAME
    releases.mkdir(exist_ok=True)
    staging_root.mkdir(exist_ok=True)
    current = _load_state(target)
    release_relative = _relative_release(target, candidate_id)
    release = _release_path(target, release_relative)
    staging = staging_root / f"{candidate_id}.{uuid.uuid4().hex}"
    try:
        if release.exists():
            problems = package_release.verify_package(release, board_profile)
            if problems:
                raise InstallError("existing release failed verification: " + "; ".join(problems))
            if current and current.get("active_release") == release_relative:
                # A retry of an already active package is a no-op. In particular,
                # do not turn the active release into its own rollback target.
                return current
        else:
            staging.mkdir(parents=True)
            _copy_package(package, staging, fail_after)
            problems = package_release.verify_package(staging, board_profile)
            if problems:
                raise InstallError("staged release failed verification: " + "; ".join(problems))
            release.parent.mkdir(parents=True, exist_ok=True)
            staging.rename(release)
        state = _state_for(target, manifest, candidate_id, release_relative, current)
        _write_json_atomic(_state_path(target), state)
        return state
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def verify_installation(target: Path, board_profile: str) -> dict[str, Any]:
    target = target.resolve()
    state = _load_state(target)
    if state is None:
        raise InstallError("installation activation record is missing")
    active_candidate = _safe_candidate_id(state.get("active_candidate_id"))
    release = _release_path(target, str(state.get("active_release", "")))
    problems = package_release.verify_package(release, board_profile)
    if problems:
        raise InstallError("active release failed verification: " + "; ".join(problems))
    manifest = _read_json(release / package_release.PACKAGE_FILENAME)
    if manifest.get("candidate_id") != active_candidate:
        raise InstallError("activation candidate does not match active package")
    expected_hash = sha256_file(release / package_release.PACKAGE_FILENAME)
    if state.get("active_package_manifest_sha256") != expected_hash:
        raise InstallError("activation package-manifest hash does not match active release")
    return {"ok": True, "target": str(target), "state": state, "release": str(release)}


def rollback_installation(target: Path, board_profile: str) -> dict[str, Any]:
    target = target.resolve()
    current = _load_state(target)
    if current is None or not current.get("previous_release"):
        raise InstallError("no previous release is available for rollback")
    previous_release = str(current["previous_release"])
    release = _release_path(target, previous_release)
    problems = package_release.verify_package(release, board_profile)
    if problems:
        raise InstallError("previous release failed verification: " + "; ".join(problems))
    manifest = _read_json(release / package_release.PACKAGE_FILENAME)
    candidate_id = _safe_candidate_id(manifest.get("candidate_id"))
    state = _state_for(target, manifest, candidate_id, previous_release, current)
    _write_json_atomic(_state_path(target), state)
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install = subparsers.add_parser("install")
    install.add_argument("--package", type=Path, required=True)
    install.add_argument("--target", type=Path, required=True)
    install.add_argument("--board-profile", required=True)
    install.add_argument("--simulate-interruption-after", type=int)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--target", type=Path, required=True)
    verify.add_argument("--board-profile", required=True)
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--target", type=Path, required=True)
    rollback.add_argument("--board-profile", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            result = install_package(args.package, args.target, args.board_profile,
                                     args.simulate_interruption_after)
        elif args.command == "verify":
            result = verify_installation(args.target, args.board_profile)
        else:
            result = rollback_installation(args.target, args.board_profile)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, InstallError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

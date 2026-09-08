"""Run the package install/update/interruption/rollback qualification fixture."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support.scripts import deploy_package, package_release


SCHEMA = "diablo-deployment-lifecycle-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _immutable_write(path: Path, value: dict[str, object]) -> None:
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"refusing to replace lifecycle receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _make_update_package(package: Path, destination: Path) -> tuple[Path, str]:
    """Make a second content-addressed package for the local update fixture."""
    shutil.copytree(package, destination)
    package_manifest_path = destination / package_release.PACKAGE_FILENAME
    deployment_path = destination / package_release.DEPLOYMENT_FILENAME
    package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))
    deployment = json.loads(deployment_path.read_text(encoding="utf-8"))
    candidate_id = hashlib.sha256((str(package_manifest["candidate_id"]) + ":update").encode()).hexdigest()
    package_manifest["candidate_id"] = candidate_id
    deployment["candidate_id"] = candidate_id
    deployment_path.write_text(json.dumps(deployment, indent=2) + "\n", encoding="utf-8")
    deployment_hash = _sha256(deployment_path)
    package_manifest["deployment_manifest"]["sha256"] = deployment_hash
    for record in package_manifest["files"]:
        if record.get("path") == package_release.DEPLOYMENT_FILENAME:
            record["bytes"] = deployment_path.stat().st_size
            record["sha256"] = deployment_hash
    package_manifest_path.write_text(json.dumps(package_manifest, indent=2) + "\n", encoding="utf-8")
    return destination, candidate_id


def run(package: Path, board_profile: str, output: Path) -> dict[str, object]:
    started = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    package = package.resolve()
    package_problems = package_release.verify_package(package, board_profile)
    if package_problems:
        raise ValueError("package verification failed: " + "; ".join(package_problems))
    manifest = json.loads((package / package_release.PACKAGE_FILENAME).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="diablo-deployment-lifecycle-") as temporary:
        root = Path(temporary)
        update_package, update_candidate = _make_update_package(package, root / "update-package")
        update_problems = package_release.verify_package(update_package, board_profile)
        if update_problems:
            raise ValueError("synthetic update package failed verification: " + "; ".join(update_problems))
        target = root / "target"
        (target / "saves").mkdir(parents=True)
        save = target / "saves" / "diablo.sav"
        save.write_bytes(b"qualification fixture save")
        before_save = _sha256(save)
        first = deploy_package.install_package(package, target, board_profile)
        interrupted = False
        try:
            deploy_package.install_package(update_package, target, board_profile, fail_after=2)
        except deploy_package.InstallError as error:
            interrupted = "simulated interrupted update" in str(error)
        after_interrupt = deploy_package.verify_installation(target, board_profile)["state"]
        updated = deploy_package.install_package(update_package, target, board_profile)
        rolled_back = deploy_package.rollback_installation(target, board_profile)
        verified = deploy_package.verify_installation(target, board_profile)
        finished = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        result = {
            "schema": SCHEMA,
            "status": "pass" if interrupted and after_interrupt["active_candidate_id"] == first["active_candidate_id"]
                      and updated["active_candidate_id"] == update_candidate
                      and rolled_back["active_candidate_id"] == first["active_candidate_id"]
                      and _sha256(save) == before_save and verified["ok"] else "fail",
            "scope": "local package transaction qualification; no physical MiSTer acceptance",
            "started_utc": started,
            "finished_utc": finished,
            "board_profile": board_profile,
            "package": str(package),
            "package_manifest_sha256": _sha256(package / package_release.PACKAGE_FILENAME),
            "candidate_id": manifest["candidate_id"],
            "update_fixture_candidate_id": update_candidate,
            "checks": {
                "clean_install": first["active_candidate_id"] == manifest["candidate_id"],
                "interrupted_update_preserves_activation": interrupted and after_interrupt["active_candidate_id"] == first["active_candidate_id"],
                "successful_update": updated["active_candidate_id"] == update_candidate,
                "rollback": rolled_back["active_candidate_id"] == first["active_candidate_id"],
                "save_preserved": _sha256(save) == before_save,
                "final_manifest_verify": verified["ok"],
                "staging_clean": not any((target / deploy_package.STAGING_DIRNAME).iterdir()),
            },
            "limitations": ["No menu entry was activated", "No physical video/audio/input observer was used"],
        }
    _immutable_write(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--board-profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.package, args.board_profile, args.output)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

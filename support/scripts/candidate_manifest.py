"""Create and verify immutable, content-addressed Diablo candidate manifests."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "diablo-candidate-manifest-v1"
SOURCE_INPUTS = (
    ".gitignore",
    "netplay.md",
    "Diablo.qpf",
    "Diablo.qsf",
    "Diablo.sdc",
    "Diablo.srf",
    "Diablo.sv",
    "files.qip",
    "build_id.v",
    ".mister/source-lock.json",
    "support/host-reference.json",
    "support/mister",
    "support/transport",
    "sys",
    "rtl",
    "support/cmake",
    "support/patches",
    "support/reference",
    "support/scripts",
    "support/qualification",
    "support/tests",
    "support/licenses",
    "scripts",
    "external_files.csv",
    "distribution/game_files.json",
    "distribution/diablo_mister.json",
    "distribution/downloader_meathax_diablo.ini",
    "LICENSE.fpga",
)
DIRECTORY_INPUTS = frozenset({
    "rtl", "support/cmake", "support/mister", "support/patches", "support/reference", "support/scripts", "support/qualification",
    "support/tests", "support/transport", "support/licenses", "sys", "scripts",
})
IGNORED_SOURCE_DIRECTORY_PARTS = frozenset({"__pycache__", ".pytest_cache"})
IGNORED_SOURCE_SUFFIXES = frozenset({".pyc", ".pyo"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def first_symlink_component(path: Path, stop: Path | None = None) -> Path | None:
    """Return the first symlink in ``path`` or its parents.

    The check intentionally happens before ``resolve``.  A final path can be a
    regular file while a parent directory redirects the lookup elsewhere.
    ``stop`` is an optional project-root boundary; paths outside it are still
    checked all the way to the filesystem root.
    """
    current = Path(os.path.abspath(path))
    boundary = Path(os.path.abspath(stop)) if stop is not None else None
    while True:
        if current.is_symlink():
            return current
        if boundary is not None and current == boundary:
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def ignored_source_path(path: Path) -> bool:
    """Identify interpreter/test caches that are not project source inputs."""
    return (any(part.casefold() in IGNORED_SOURCE_DIRECTORY_PARTS for part in path.parts)
            or path.suffix.casefold() in IGNORED_SOURCE_SUFFIXES)


def files_for_inputs(root: Path, inputs: Iterable[str] = SOURCE_INPUTS) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for input_name in inputs:
        path = root / input_name
        symlink = first_symlink_component(path, root)
        if symlink is not None:
            raise RuntimeError(f"candidate input path must not contain a symlink: {symlink}")
        if path.is_symlink():
            raise RuntimeError(f"candidate input must not be a symlink: {input_name}")
        if not path.exists():
            raise RuntimeError(f"candidate input is missing: {input_name}")
        if path.is_file():
            paths = [path]
        else:
            paths = []
            for candidate in sorted(path.rglob("*")):
                if ignored_source_path(candidate):
                    continue
                if candidate.is_symlink():
                    raise RuntimeError(f"candidate input must not contain a symlink: {relative(root, candidate)}")
                if candidate.is_file():
                    paths.append(candidate)
        for candidate in paths:
            if candidate.is_symlink():
                raise RuntimeError(f"candidate input must not contain a symlink: {relative(root, candidate)}")
            records.append({"path": relative(root, candidate), "bytes": candidate.stat().st_size,
                            "sha256": sha256_file(candidate)})
    paths = [record["path"] for record in records]
    if len(paths) != len(set(paths)):
        raise RuntimeError("candidate input list contains the same file more than once")
    return sorted(records, key=lambda record: str(record["path"]))


def git_identity(root: Path, source_paths: Iterable[str], status_paths: Iterable[str] = SOURCE_INPUTS) -> dict[str, object]:
    def run(*args: str) -> str | None:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
        # Preserve the leading porcelain status column.  ``str.strip()`` would
        # remove the first line's leading worktree-space and make a manifest
        # fail verification whenever that file sorts first in git status.
        if result.returncode != 0:
            return None
        value = result.stdout
        if value.endswith("\\r\\n"):
            value = value[:-4]
        elif value.endswith("\\n") or value.endswith("\\r"):
            value = value[:-2]
        return value.rstrip("\r\n")

    tracked_paths = set(source_paths)
    # The checkout intentionally keeps large ignored build/package trees.  Ask
    # Git only about manifest inputs so obtaining a candidate identity never
    # walks those unrelated directories (or times out while doing so).
    status = run("status", "--porcelain=v1", "--untracked-files=all", "--", *status_paths)
    relevant_status = None
    if status is not None:
        relevant_lines = []
        for line in status.splitlines():
            path = line[3:]
            if path in tracked_paths:
                relevant_lines.append(line)
        relevant_status = "\n".join(relevant_lines)
    return {
        "head": run("rev-parse", "HEAD"),
        "status_porcelain_v1": relevant_status,
    }


def artifact_records(root: Path, artifacts: Iterable[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for artifact in artifacts:
        symlink = first_symlink_component(artifact, root)
        if symlink is not None:
            if Path(os.path.abspath(artifact)) == symlink:
                raise RuntimeError(f"candidate artifact must not be a symlink: {artifact}")
            raise RuntimeError(f"candidate artifact path must not contain a symlink: {symlink}")
        resolved = artifact.resolve()
        if not resolved.is_file() or resolved.is_symlink():
            raise RuntimeError(f"candidate artifact is missing: {artifact}")
        try:
            stored_path = relative(root, resolved)
        except ValueError:
            stored_path = str(resolved)
        records.append({"path": stored_path, "bytes": resolved.stat().st_size, "sha256": sha256_file(resolved)})
    if not records:
        raise RuntimeError("at least one --artifact is required")
    return sorted(records, key=lambda record: str(record["path"]))


def make_manifest(root: Path, artifacts: Iterable[Path], tool_versions: dict[str, str] | None = None) -> dict[str, object]:
    source_files = files_for_inputs(root)
    inputs = {
        "source_files": source_files,
        "git": git_identity(root, (str(record["path"]) for record in source_files)),
        "tool_versions": tool_versions or {},
    }
    source_id = hashlib.sha256(canonical_bytes(inputs)).hexdigest()
    output_artifacts = artifact_records(root, artifacts)
    candidate_id = hashlib.sha256(canonical_bytes({"source_id": source_id, "artifacts": output_artifacts})).hexdigest()
    return {
        "schema": SCHEMA,
        "status": "pass",
        "candidate_id": candidate_id,
        "source_id": source_id,
        "created_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": inputs,
        "artifacts": output_artifacts,
    }


def verify_manifest(root: Path, manifest_path: Path) -> list[str]:
    if manifest_path.is_symlink():
        return [f"manifest must not be a symlink: {manifest_path}"]
    symlink = first_symlink_component(manifest_path.parent, root)
    if symlink is not None:
        return [f"manifest path must not contain a symlink: {symlink}"]
    if not manifest_path.is_file():
        return [f"manifest is missing: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"manifest is invalid JSON: {error.msg}"]
    except (OSError, UnicodeError) as error:
        return [f"manifest cannot be read: {error}"]
    if manifest.get("schema") != SCHEMA:
        return ["unsupported manifest schema"]
    problems: list[str] = []
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict):
        return ["manifest inputs are missing"]
    expected_inputs = dict(inputs)
    expected_inputs["source_files"] = files_for_inputs(root)
    expected_inputs["git"] = git_identity(root, (str(record["path"])
                                                  for record in expected_inputs["source_files"]))
    source_id = hashlib.sha256(canonical_bytes(expected_inputs)).hexdigest()
    if source_id != manifest.get("source_id"):
        problems.append("source inputs no longer match manifest")
    artifacts: list[Path] = []
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            problems.append("invalid artifact record")
            continue
        path = Path(artifact["path"])
        artifacts.append(path if path.is_absolute() else root / path)
    try:
        current_artifacts = artifact_records(root, artifacts)
    except RuntimeError as error:
        problems.append(str(error))
        current_artifacts = []
    candidate_id = hashlib.sha256(canonical_bytes({"source_id": manifest.get("source_id"),
                                                    "artifacts": current_artifacts})).hexdigest()
    if candidate_id != manifest.get("candidate_id"):
        problems.append("artifact content no longer matches manifest")
    return problems


def parse_tools(values: list[str]) -> dict[str, str]:
    tools: dict[str, str] = {}
    for value in values:
        name, separator, version = value.partition("=")
        if not separator or not name or not version:
            raise argparse.ArgumentTypeError("--tool must be NAME=VERSION")
        if name in tools:
            raise argparse.ArgumentTypeError(f"duplicate tool name: {name}")
        tools[name] = version
    return tools


def write_new_manifest(path: Path, manifest: dict[str, object]) -> None:
    """Publish a manifest once without replacing an earlier candidate record.

    ``os.replace`` is intentionally not used here: a candidate manifest is an
    acceptance input, not a latest-result file.  Publishing through a hard link
    makes the completed JSON visible atomically and fails if another process has
    already claimed the requested name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + os.urandom(8).hex() + ".tmp")
    try:
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise RuntimeError(f"refusing to overwrite immutable manifest: {path}") from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--artifact", type=Path, action="append", required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--tool", action="append", default=[])
    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "create":
        manifest = make_manifest(root, [path if path.is_absolute() else root / path for path in args.artifact],
                                 parse_tools(args.tool))
        output = args.output if args.output.is_absolute() else root / args.output
        write_new_manifest(output, manifest)
        print(json.dumps({"candidate_id": manifest["candidate_id"], "manifest": str(output)}, sort_keys=True))
        return 0
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    problems = verify_manifest(root, manifest_path)
    if problems:
        print(json.dumps({"ok": False, "problems": problems}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "manifest": str(manifest_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

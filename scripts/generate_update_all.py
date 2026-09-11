"""Generate Downloader_MiSTer databases and the archived Diablo runtime."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_FILES_PATH = ROOT / "external_files.csv"
INVENTORY_PATH = ROOT / "distribution" / "game_files.json"  # Legacy audit input.
OUTPUT_PATH = ROOT / "distribution" / "diablo_mister.json"
OUTPUT_ZIP_PATH = ROOT / "distribution" / "diablo_mister.json.zip"
RUNTIME_OUTPUT_PATH = ROOT / "distribution" / "diablo_runtime.json"
RUNTIME_OUTPUT_ZIP_PATH = ROOT / "distribution" / "diablo_runtime.json.zip"
RUNTIME_ARCHIVE_PATH = ROOT / "distribution" / "diablo_runtime.zip"
READY_ROOT = ROOT / "ready"

ARCHIVE_BASE_URL = "https://archive.org/download"
PUBLISHED_DISTRIBUTION_URL = (
    "https://raw.githubusercontent.com/meathax/diablo/main/distribution"
)
PUBLISHED_READY_URL = "https://raw.githubusercontent.com/meathax/diablo/main/ready"
RUNTIME_ARCHIVE_ID = "diablo_runtime_bundle"
DATABASE_TIMESTAMP = 1788912000
CSV_FIELDS = (
    "Path",
    "URL",
    "Size in bytes (optional but recommended)",
    "MD5 Hash (optional but recommended)",
    "Filter Terms (optional)",
    "Overwrite (optional)",
    "Comments (optional)",
)
REQUIRED_FILES = {
    "games/Diablo/DIABDAT.MPQ": ("Diablo.iso", 517501282, "011bc6518e6166206231080a4440b373"),
    "games/Diablo/hellfire.mpq": ("Hellfire.iso", 65502336, "c996bd970df13ea7aa5e2417f8e78b9f"),
    "games/Diablo/hfmonk.mpq": ("Hellfire.iso", 37658368, "5a6b8f1ef6d505d469c31aef6e48e89d"),
    "games/Diablo/hfmusic.mpq": ("Hellfire.iso", 34379360, "5f79b271b4a291fc8968df7e8aa80d52"),
    "games/Diablo/hfvoice.mpq": ("Hellfire.iso", 37743520, "6ae6ce3e89ece92c1e3e912a91d0b186"),
}
EXECUTABLES = {
    "Diablo",
    "_Other/Diablo/devilutionx",
    "_Other/Diablo/diablo_launcher.py",
    "_Other/Diablo/Diablo.sh",
    "_Other/Diablo/Hellfire.sh",
}
MD5_RE = re.compile(r"^[0-9a-f]{32}$")


class InventoryError(ValueError):
    """Raised when a database input could install extra or invalid content."""


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InventoryError(f"cannot read inventory {path}: {error}") from error
    if not isinstance(value, dict):
        raise InventoryError("inventory must be a JSON object")
    return value


def load_inventory(path: Path = INVENTORY_PATH) -> dict[str, object]:
    """Load the retained pre-CSV inventory for compatibility and audit history."""
    data = _load_json(path)
    required_fields = {
        "version": int,
        "database_id": str,
        "timestamp": int,
        "archive_item": str,
        "destination_root": str,
        "files": list,
    }
    for field, expected_type in required_fields.items():
        value = data.get(field)
        if not isinstance(value, expected_type) or isinstance(value, bool):
            raise InventoryError(f"inventory field {field!r} must be {expected_type.__name__}")
    if data["version"] != 1 or data["database_id"] != "diablo_mister":
        raise InventoryError("legacy inventory identity or version changed")
    if data["archive_item"] != "diablohellfire" or data["destination_root"] != "games/Diablo":
        raise InventoryError("legacy inventory source or destination changed")
    if data["timestamp"] <= 0:
        raise InventoryError("timestamp must be a positive Unix epoch")

    names: set[str] = set()
    for entry in data["files"]:
        if not isinstance(entry, dict):
            raise InventoryError("every legacy file entry must be an object")
        for field in ("name", "archive", "size", "md5", "kind"):
            if field not in entry:
                raise InventoryError(f"legacy file entry is missing {field!r}")
        name = str(entry["name"])
        destination = f"games/Diablo/{name}"
        if destination not in REQUIRED_FILES or REQUIRED_FILES[destination][0] != entry["archive"]:
            raise InventoryError(f"{name}: not an allowed Diablo/Hellfire archive member")
        if name in names:
            raise InventoryError(f"duplicate game file {name!r}")
        names.add(name)
    expected_names = {Path(path).name for path in REQUIRED_FILES}
    if names != expected_names:
        raise InventoryError("legacy inventory must contain exactly the five required files")
    return data


def load_external_files(path: Path = EXTERNAL_FILES_PATH) -> list[dict[str, object]]:
    """Read the DB-Template/BiosDB external_files.csv contract, failing closed."""
    try:
        stream = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as error:
        raise InventoryError(f"cannot read external file list {path}: {error}") from error
    with stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise InventoryError("external_files.csv header does not match the MiSTer DB template")
        rows = list(reader)

    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        destination = row[CSV_FIELDS[0]].strip()
        url = row[CSV_FIELDS[1]].strip()
        size_text = row[CSV_FIELDS[2]].strip()
        digest = row[CSV_FIELDS[3]].strip()
        tags = row[CSV_FIELDS[4]].strip()
        overwrite_text = row[CSV_FIELDS[5]].strip().lower()
        if destination in seen:
            raise InventoryError(f"duplicate external file {destination!r}")
        seen.add(destination)
        if destination not in REQUIRED_FILES:
            raise InventoryError(f"external file is not required: {destination!r}")
        archive, expected_size, expected_digest = REQUIRED_FILES[destination]
        expected_url = "/".join((
            ARCHIVE_BASE_URL,
            "diablohellfire",
            quote(archive, safe=""),
            quote(Path(destination).name, safe=""),
        ))
        try:
            size = int(size_text)
        except ValueError as error:
            raise InventoryError(f"{destination}: size must be an integer") from error
        if url != expected_url or size != expected_size or digest != expected_digest:
            raise InventoryError(f"{destination}: URL, size, or MD5 differs from the audited file")
        if not MD5_RE.fullmatch(digest):
            raise InventoryError(f"{destination}: invalid MD5")
        if tags != "diablo":
            raise InventoryError(f"{destination}: filter term must be 'diablo'")
        if overwrite_text not in ("", "overwrite:true", "overwrite:false"):
            raise InventoryError(f"{destination}: invalid overwrite directive")
        normalized.append({
            "path": destination,
            "url": url,
            "size": size,
            "md5": digest,
            "tags": ["diablo"],
            "overwrite": overwrite_text != "overwrite:false",
        })

    if seen != set(REQUIRED_FILES):
        missing = sorted(set(REQUIRED_FILES) - seen)
        extra = sorted(seen - set(REQUIRED_FILES))
        raise InventoryError(f"external file list must contain exactly five files (missing={missing}, extra={extra})")
    return normalized


def member_url(data: dict[str, object], entry: dict[str, object]) -> str:
    """Return the legacy inventory's individual Archive.org member URL."""
    return "/".join((
        ARCHIVE_BASE_URL,
        quote(str(data["archive_item"]), safe=""),
        quote(str(entry["archive"]), safe=""),
        quote(str(entry["name"]), safe=""),
    ))


def build_database(source: dict[str, object] | list[dict[str, object]]) -> dict[str, object]:
    """Build the game-data database from CSV, accepting the legacy test shape."""
    if isinstance(source, dict):
        rows = [{
            "path": f"{source['destination_root']}/{entry['name']}",
            "url": member_url(source, entry),
            "size": entry["size"],
            "md5": entry["md5"],
            "tags": ["diablo"],
            "overwrite": True,
        } for entry in source["files"]]
        timestamp = source["timestamp"]
    else:
        rows = source
        timestamp = DATABASE_TIMESTAMP
    files = {
        str(entry["path"]): {
            "hash": entry["md5"],
            "overwrite": entry["overwrite"],
            "size": entry["size"],
            "tags": entry["tags"],
            "url": entry["url"],
        }
        for entry in sorted(rows, key=lambda item: str(item["path"]).casefold())
    }
    return {
        "v": 1,
        "db_id": "diablo_mister",
        "timestamp": timestamp,
        "files": files,
        "folders": {
            "games/": {"tags": ["diablo"]},
            "games/Diablo/": {"tags": ["diablo"]},
        },
    }


def rendered_database(source: dict[str, object] | list[dict[str, object]]) -> str:
    return json.dumps(build_database(source), indent=2, sort_keys=True) + "\n"


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _zip_info(name: str, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = ((0o100755 if executable else 0o100644) & 0xFFFF) << 16
    return info


def compressed_json(filename: str, body: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info(filename), body)
    return output.getvalue()


def write_game_artifacts(source_path: Path = EXTERNAL_FILES_PATH,
                         output_path: Path = OUTPUT_PATH,
                         output_zip_path: Path = OUTPUT_ZIP_PATH) -> None:
    body = rendered_database(load_external_files(source_path)).encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(body)
    output_zip_path.write_bytes(compressed_json(output_path.name, body))


def _ready_files(ready_root: Path) -> list[Path]:
    if not ready_root.is_dir():
        raise InventoryError(f"ready tree is missing: {ready_root}")
    files = sorted((path for path in ready_root.rglob("*") if path.is_file()),
                   key=lambda path: path.relative_to(ready_root).as_posix().casefold())
    if not files:
        raise InventoryError("ready tree is empty")
    return files


def _runtime_files(ready_root: Path) -> list[Path]:
    """Return only redistributable runtime files, never games or user saves."""
    return [path for path in _ready_files(ready_root)
            if not path.relative_to(ready_root).as_posix().startswith("games/")]


def write_runtime_artifacts(ready_root: Path = READY_ROOT,
                            database_path: Path = RUNTIME_OUTPUT_PATH,
                            database_zip_path: Path = RUNTIME_OUTPUT_ZIP_PATH,
                            archive_path: Path = RUNTIME_ARCHIVE_PATH,
                            timestamp: int | None = None,
                            archive_url: str = f"{PUBLISHED_DISTRIBUTION_URL}/diablo_runtime.zip",
                            base_files_url: str = PUBLISHED_READY_URL) -> None:
    ready_files = _runtime_files(ready_root)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in ready_files:
            relative = source.relative_to(ready_root).as_posix()
            archive.writestr(_zip_info(relative, relative in EXECUTABLES), source.read_bytes())

    summary_files: dict[str, dict[str, object]] = {}
    summary_folders: dict[str, dict[str, object]] = {}
    for source in ready_files:
        relative = source.relative_to(ready_root).as_posix()
        summary_files[relative] = {
            "hash": _digest(source, "md5"),
            "size": source.stat().st_size,
            "arc_id": RUNTIME_ARCHIVE_ID,
            "arc_at": relative,
            "tags": ["diablo"],
            "overwrite": True,
        }
        parent = Path(relative).parent
        while parent.as_posix() not in (".", ""):
            summary_folders[parent.as_posix()] = {
                "arc_id": RUNTIME_ARCHIVE_ID,
                "tags": ["diablo"],
            }
            parent = parent.parent

    database = {
        "v": 1,
        "db_id": "diablo_runtime",
        "timestamp": int(time.time()) if timestamp is None else timestamp,
        "files": {},
        "folders": {},
        "archives": {
            RUNTIME_ARCHIVE_ID: {
                "format": "zip",
                "extract": "selective",
                "description": "Installing Diablo and Hellfire runtime",
                "archive_file": {
                    "hash": _digest(archive_path, "md5"),
                    "size": archive_path.stat().st_size,
                    "url": archive_url,
                },
                "summary_inline": {
                    "files": dict(sorted(summary_files.items())),
                    "folders": dict(sorted(summary_folders.items())),
                },
                "base_files_url": base_files_url.rstrip("/"),
            }
        },
    }
    body = (json.dumps(database, indent=2, sort_keys=True) + "\n").encode("utf-8")
    database_path.write_bytes(body)
    database_zip_path.write_bytes(compressed_json(database_path.name, body))


def _check_compressed_json(path: Path, member: str, expected: bytes) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.namelist() != [member] or archive.read(member) != expected:
                raise InventoryError(f"compressed database is stale: {path}")
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise InventoryError(f"cannot validate compressed database {path}: {error}") from error


def check_runtime_artifacts(ready_root: Path = READY_ROOT,
                            database_path: Path = RUNTIME_OUTPUT_PATH,
                            database_zip_path: Path = RUNTIME_OUTPUT_ZIP_PATH,
                            archive_path: Path = RUNTIME_ARCHIVE_PATH) -> None:
    database = _load_json(database_path)
    if database.get("db_id") != "diablo_runtime" or database.get("v") != 1:
        raise InventoryError("runtime database identity or version changed")
    archives = database.get("archives")
    if not isinstance(archives, dict) or set(archives) != {RUNTIME_ARCHIVE_ID}:
        raise InventoryError("runtime database must contain exactly one archive")
    descriptor = archives[RUNTIME_ARCHIVE_ID]
    summary = descriptor.get("summary_inline", {})
    summary_files = summary.get("files", {})
    actual_files = _runtime_files(ready_root)
    actual_names = {path.relative_to(ready_root).as_posix() for path in actual_files}
    if set(summary_files) != actual_names:
        raise InventoryError("runtime archive summary does not match ready tree")
    for source in actual_files:
        relative = source.relative_to(ready_root).as_posix()
        entry = summary_files[relative]
        if (entry.get("hash") != _digest(source, "md5")
                or entry.get("size") != source.stat().st_size
                or entry.get("arc_id") != RUNTIME_ARCHIVE_ID
                or entry.get("arc_at") != relative):
            raise InventoryError(f"runtime summary mismatch: {relative}")
    archive_file = descriptor.get("archive_file", {})
    if archive_file.get("hash") != _digest(archive_path, "md5") or archive_file.get("size") != archive_path.stat().st_size:
        raise InventoryError("runtime archive hash or size is stale")
    with zipfile.ZipFile(archive_path) as archive:
        if set(archive.namelist()) != actual_names:
            raise InventoryError("runtime ZIP contents do not match ready tree")
        for source in actual_files:
            relative = source.relative_to(ready_root).as_posix()
            if hashlib.md5(archive.read(relative)).hexdigest() != summary_files[relative]["hash"]:
                raise InventoryError(f"runtime ZIP member mismatch: {relative}")
    body = database_path.read_bytes()
    _check_compressed_json(database_zip_path, database_path.name, body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-files", type=Path, default=EXTERNAL_FILES_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--output-zip", type=Path, default=OUTPUT_ZIP_PATH)
    parser.add_argument("--ready-root", type=Path, default=READY_ROOT)
    parser.add_argument("--runtime-output", type=Path, default=RUNTIME_OUTPUT_PATH)
    parser.add_argument("--runtime-output-zip", type=Path, default=RUNTIME_OUTPUT_ZIP_PATH)
    parser.add_argument("--runtime-archive", type=Path, default=RUNTIME_ARCHIVE_PATH)
    parser.add_argument("--check", action="store_true", help="fail if generated artifacts are stale")
    args = parser.parse_args(argv)
    try:
        expected_game = rendered_database(load_external_files(args.external_files)).encode("utf-8")
        if args.check:
            if args.output.read_bytes() != expected_game:
                raise InventoryError(f"generated database is stale: {args.output}")
            _check_compressed_json(args.output_zip, args.output.name, expected_game)
            check_runtime_artifacts(args.ready_root, args.runtime_output,
                                    args.runtime_output_zip, args.runtime_archive)
        else:
            write_game_artifacts(args.external_files, args.output, args.output_zip)
            write_runtime_artifacts(args.ready_root, args.runtime_output,
                                    args.runtime_output_zip, args.runtime_archive)
    except (InventoryError, OSError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())

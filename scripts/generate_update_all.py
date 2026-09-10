"""Generate the narrow update_all database for Diablo + Hellfire data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "distribution" / "game_files.json"
OUTPUT_PATH = ROOT / "distribution" / "diablo_mister.json"
ARCHIVE_BASE_URL = "https://archive.org/download"
REQUIRED_FILES = {
    "DIABDAT.MPQ": "Diablo.iso",
    "hellfire.mpq": "Hellfire.iso",
    "hfmonk.mpq": "Hellfire.iso",
    "hfmusic.mpq": "Hellfire.iso",
    "hfvoice.mpq": "Hellfire.iso",
}
MD5_RE = re.compile(r"^[0-9a-f]{32}$")


class InventoryError(ValueError):
    """Raised when a database inventory could download extra or invalid content."""


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InventoryError(f"cannot read inventory {path}: {error}") from error
    if not isinstance(value, dict):
        raise InventoryError("inventory must be a JSON object")
    return value


def load_inventory(path: Path = INVENTORY_PATH) -> dict[str, object]:
    """Load and fail closed unless the inventory is exactly the runtime contract."""
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

    if data["version"] != 1:
        raise InventoryError("only update_all database format version 1 is supported")
    if data["database_id"] != "diablo_mister":
        raise InventoryError("database_id must remain 'diablo_mister'")
    if data["archive_item"] != "diablohellfire":
        raise InventoryError("archive_item must be the requested diablohellfire item")
    if data["destination_root"] != "games/Diablo":
        raise InventoryError("download destination must be games/Diablo")
    if data["timestamp"] <= 0:
        raise InventoryError("timestamp must be a positive Unix epoch")

    entries = data["files"]
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise InventoryError("every file entry must be an object")
        for field in ("name", "archive", "size", "md5", "kind"):
            if field not in entry:
                raise InventoryError(f"file entry is missing {field!r}")
        name = entry["name"]
        archive = entry["archive"]
        size = entry["size"]
        digest = entry["md5"]
        if not isinstance(name, str) or not isinstance(archive, str):
            raise InventoryError("file names and archive names must be strings")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise InventoryError(f"{name}: size must be a positive integer")
        if not isinstance(digest, str) or not MD5_RE.fullmatch(digest):
            raise InventoryError(f"{name}: md5 must be a lowercase 32-character digest")
        if name in names:
            raise InventoryError(f"duplicate game file {name!r}")
        names.add(name)
        if REQUIRED_FILES.get(name) != archive:
            raise InventoryError(f"{name}: not an allowed Diablo/Hellfire archive member")

    if names != set(REQUIRED_FILES):
        missing = sorted(set(REQUIRED_FILES) - names)
        extra = sorted(names - set(REQUIRED_FILES))
        raise InventoryError(f"inventory must contain exactly the five required files (missing={missing}, extra={extra})")
    return data


def member_url(data: dict[str, object], entry: dict[str, object]) -> str:
    """Return Archive.org's individual-member URL, never a whole disc image."""
    return "/".join((
        ARCHIVE_BASE_URL,
        quote(str(data["archive_item"]), safe=""),
        quote(str(entry["archive"]), safe=""),
        quote(str(entry["name"]), safe=""),
    ))


def build_database(data: dict[str, object]) -> dict[str, object]:
    """Build the Downloader_MiSTer custom-database document."""
    root = str(data["destination_root"])
    files: dict[str, dict[str, object]] = {}
    for entry in sorted(data["files"], key=lambda item: str(item["name"]).casefold()):
        name = str(entry["name"])
        files[f"{root}/{name}"] = {
            "hash": entry["md5"],
            "size": entry["size"],
            "url": member_url(data, entry),
            "overwrite": True,
            "tags": ["diablo"],
        }
    return {
        "v": 1,
        "db_id": data["database_id"],
        "timestamp": data["timestamp"],
        "files": files,
        "folders": {"games/": {"tags": ["diablo"]},
                    "games/Diablo/": {"tags": ["diablo"]}},
    }


def rendered_database(data: dict[str, object]) -> str:
    return json.dumps(build_database(data), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true", help="fail if the generated database is stale")
    args = parser.parse_args(argv)
    try:
        rendered = rendered_database(load_inventory(args.inventory))
    except InventoryError as error:
        parser.error(str(error))
    if args.check:
        try:
            existing = args.output.read_text(encoding="utf-8")
        except OSError as error:
            parser.error(f"cannot read generated database {args.output}: {error}")
        if existing != rendered:
            parser.error(f"generated database is stale: run {Path(__file__).name}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

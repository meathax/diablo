"""Apply or inspect the offline MiSTer Xbox controller preset in a diablo.ini."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Iterable


BACKUP_SUFFIX = ".before-mister-controller-preset.bak"
RELEASE_READINESS = "requires-complete-controller-behavior-implementation-before-release"

# The spellings are the names serialized by PadmapperOptions in
# ``Source/options.cpp``.  In particular, Xbox View and L3 use the engine's
# portable names Select and LS.
PADMAPPING_PRESET: tuple[tuple[str, str], ...] = (
    ("QuickSpell1", "RT+X"),
    ("QuickSpell2", "RT+Y"),
    ("QuickSpell3", "RT+A"),
    ("QuickSpell4", "RT+B"),
    ("PrimaryAction", "A"),
    ("SecondaryAction", "Y"),
    ("SpellAction", "X"),
    ("CancelAction", "B"),
    ("DisplaySpells", "B"),
    ("UseHealthPotion", "LB"),
    ("UseManaPotion", "RB"),
    ("StandGround", "LT"),
    ("ToggleItemHighlighting", "LS"),
    ("SpellBook", "Up"),
    ("Inventory", "Right"),
    ("QuestLog", "Down"),
    ("Character", "Left"),
    ("ToggleAutomap", "Select"),
    ("ToggleGameMenu1", "Start"),
    ("LeftMouseClick1", "RS"),
    ("RightMouseClick1", "RT+RS"),
    ("AutomapMoveUp", "RT+Up"),
    ("AutomapMoveDown", "RT+Down"),
    ("AutomapMoveLeft", "RT+Left"),
    ("AutomapMoveRight", "RT+Right"),
    # These old mappings conflict with the controller contract and are
    # explicitly unbound. An empty value is how PadmapperOptions saves NONE.
    ("MoveUp", ""),
    ("MoveDown", ""),
    ("MoveLeft", ""),
    ("MoveRight", ""),
    ("MouseUp", ""),
    ("MouseDown", ""),
    ("MouseLeft", ""),
    ("MouseRight", ""),
    ("LeftMouseClick2", ""),
    ("RightMouseClick2", ""),
    ("PadHotspellMenu", ""),
    ("PadMenuNavigator", ""),
    ("ToggleGameMenu2", ""),
)

GAME_PRESET: tuple[tuple[str, str], ...] = (
    ("Quick Cast", "1"),
    ("Auto Refill Belt", "1"),
    ("Auto Gold Pickup", "1"),
)

SECTION_HEADER = re.compile(r"^[ \t]*\[([^\]\r\n]+)\][ \t]*(?:[;#].*)?$")
KEY_VALUE = re.compile(r"^[ \t]*([^=;#\s][^=]*?)[ \t]*=(.*)$")


class PresetError(ValueError):
    """The requested INI cannot be safely inspected or rewritten."""


@dataclass(frozen=True)
class Section:
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class PresetCheck:
    missing: tuple[str, ...]
    conflicting: tuple[str, ...]
    duplicate: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing and not self.conflicting and not self.duplicate


@dataclass(frozen=True)
class ApplyResult:
    changed: bool
    backup: Path | None
    check: PresetCheck


def backup_path_for(ini_path: Path) -> Path:
    return ini_path.with_name(ini_path.name + BACKUP_SUFFIX)


def _split_text(raw: bytes, path: Path) -> tuple[bytes, str]:
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    try:
        return bom, raw[len(bom):].decode("utf-8")
    except UnicodeDecodeError as error:
        raise PresetError(f"INI is not valid UTF-8: {path}") from error


def _line_body(line: str) -> str:
    return line[:-2] if line.endswith("\r\n") else line[:-1] if line.endswith("\n") else line


def _line_ending(line: str) -> str:
    return "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""


def _preferred_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _parse_sections(text: str) -> tuple[list[str], list[Section]]:
    lines = text.splitlines(keepends=True)
    sections: list[Section] = []
    current_name: str | None = None
    current_start = -1
    for index, line in enumerate(lines):
        body = _line_body(line)
        stripped = body.strip()
        if not stripped or stripped.startswith((";", "#")):
            continue
        section_match = SECTION_HEADER.fullmatch(body)
        if section_match is not None:
            if current_name is not None:
                sections.append(Section(current_name, current_start, index))
            current_name = section_match.group(1)
            current_start = index
            continue
        if body.lstrip().startswith("["):
            raise PresetError(f"malformed section header on line {index + 1}")
        key_match = KEY_VALUE.fullmatch(body)
        if current_name is None or key_match is None or not key_match.group(1).strip():
            raise PresetError(f"malformed INI entry on line {index + 1}")
    if current_name is not None:
        sections.append(Section(current_name, current_start, len(lines)))
    if not sections:
        raise PresetError("INI contains no sections")
    return lines, sections


def _entry(line: str) -> tuple[str, str] | None:
    match = KEY_VALUE.fullmatch(_line_body(line))
    if match is None:
        return None
    return match.group(1).strip(), match.group(2).strip()


def _required_sections(sections: Iterable[Section]) -> dict[str, Section]:
    selected: dict[str, Section] = {}
    for section in sections:
        if section.name not in {"Game", "Padmapping"}:
            continue
        if section.name in selected:
            raise PresetError(f"duplicate [{section.name}] section is ambiguous")
        selected[section.name] = section
    return selected


def _check_section(lines: list[str], section: Section | None,
                   required: tuple[tuple[str, str], ...]) -> PresetCheck:
    values: dict[str, list[str]] = {key: [] for key, _value in required}
    if section is not None:
        for line in lines[section.start + 1:section.end]:
            parsed = _entry(line)
            if parsed is not None and parsed[0] in values:
                values[parsed[0]].append(parsed[1])
    missing: list[str] = []
    conflicting: list[str] = []
    duplicate: list[str] = []
    for key, expected in required:
        actual = values[key]
        label = f"[{section.name if section is not None else ('Game' if required is GAME_PRESET else 'Padmapping')}] {key}"
        if not actual:
            missing.append(label)
        elif any(value != expected for value in actual):
            conflicting.append(label)
        if len(actual) > 1:
            duplicate.append(label)
    return PresetCheck(tuple(missing), tuple(conflicting), tuple(duplicate))


def check_text(text: str) -> PresetCheck:
    lines, sections = _parse_sections(text)
    selected = _required_sections(sections)
    game = _check_section(lines, selected.get("Game"), GAME_PRESET)
    padmapping = _check_section(lines, selected.get("Padmapping"), PADMAPPING_PRESET)
    return PresetCheck(game.missing + padmapping.missing,
                       game.conflicting + padmapping.conflicting,
                       game.duplicate + padmapping.duplicate)


def _canonical_line(key: str, value: str, ending: str) -> str:
    return f"{key}={value}{ending}"


def _rewrite_section(body: list[str], required: tuple[tuple[str, str], ...], newline: str) -> list[str]:
    required_values = dict(required)
    seen: set[str] = set()
    rewritten: list[str] = []
    for line in body:
        parsed = _entry(line)
        if parsed is None or parsed[0] not in required_values:
            rewritten.append(line)
            continue
        key = parsed[0]
        if key in seen:
            continue
        seen.add(key)
        rewritten.append(_canonical_line(key, required_values[key], _line_ending(line) or newline))
    missing = [(key, value) for key, value in required if key not in seen]
    if missing:
        if rewritten and not rewritten[-1].endswith(("\n", "\r")):
            rewritten[-1] += newline
        rewritten.extend(_canonical_line(key, value, newline) for key, value in missing)
    return rewritten


def rewrite_text(text: str) -> str:
    lines, sections = _parse_sections(text)
    selected = _required_sections(sections)
    newline = _preferred_newline(text)
    required_by_section = {"Game": GAME_PRESET, "Padmapping": PADMAPPING_PRESET}
    output: list[str] = []
    cursor = 0
    for section in sections:
        required = required_by_section.get(section.name)
        if required is None:
            continue
        output.extend(lines[cursor:section.start + 1])
        output.extend(_rewrite_section(lines[section.start + 1:section.end], required, newline))
        cursor = section.end
    output.extend(lines[cursor:])
    rendered = "".join(output)
    for name, required in required_by_section.items():
        if name in selected:
            continue
        separator = "" if not rendered or rendered.endswith(("\n", "\r")) else newline
        rendered += f"{separator}[{name}]{newline}"
        rendered += "".join(_canonical_line(key, value, newline) for key, value in required)
    # The rendered document must be self-consistent before callers can create a
    # backup or replace the supplied configuration.
    if not check_text(rendered).complete:
        raise PresetError("internal error: generated preset did not validate")
    return rendered


def _read_ini(ini_path: Path) -> tuple[bytes, bytes, str]:
    if not ini_path.is_file():
        raise PresetError(f"INI does not exist or is not a regular file: {ini_path}")
    raw = ini_path.read_bytes()
    bom, text = _split_text(raw, ini_path)
    _parse_sections(text)
    return raw, bom, text


def check_preset(ini_path: Path) -> PresetCheck:
    _raw, _bom, text = _read_ini(ini_path)
    return check_text(text)


def apply_preset(ini_path: Path) -> ApplyResult:
    raw, bom, text = _read_ini(ini_path)
    rendered = rewrite_text(text)
    replacement = bom + rendered.encode("utf-8")
    backup = backup_path_for(ini_path)
    created_backup: Path | None = None
    if not backup.exists():
        try:
            with backup.open("xb") as file:
                file.write(raw)
            created_backup = backup
        except FileExistsError:
            pass
    elif not backup.is_file() or backup.is_symlink():
        raise PresetError(f"backup path is not a regular file: {backup}")
    if replacement != raw:
        temporary = ini_path.with_name(ini_path.name + ".controller-preset.tmp")
        created_temporary = False
        try:
            with temporary.open("xb") as file:
                created_temporary = True
                file.write(replacement)
            temporary.replace(ini_path)
        finally:
            if created_temporary:
                temporary.unlink(missing_ok=True)
    return ApplyResult(replacement != raw, created_backup, check_text(rendered))


def _report(ini_path: Path, check: PresetCheck, *, changed: bool | None,
            backup: Path | None) -> str:
    return json.dumps({
        "status": "complete" if check.complete else "incomplete",
        "config": str(ini_path),
        "changed": changed,
        "backup": str(backup) if backup is not None else None,
        "missing": list(check.missing),
        "conflicting": list(check.conflicting),
        "duplicate": list(check.duplicate),
        "release_readiness": RELEASE_READINESS,
    }, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write the preset and preserve the original byte backup")
    mode.add_argument("--check", action="store_true", help="inspect only (the default)")
    parser.add_argument("ini", type=Path, help="local diablo.ini to inspect or update")
    args = parser.parse_args(argv)
    try:
        if args.apply:
            result = apply_preset(args.ini)
            print(_report(args.ini, result.check, changed=result.changed, backup=result.backup))
            return 0 if result.check.complete else 1
        check = check_preset(args.ini)
        print(_report(args.ini, check, changed=None, backup=None))
        return 0 if check.complete else 1
    except (OSError, PresetError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

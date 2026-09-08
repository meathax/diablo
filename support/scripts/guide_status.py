"""Check that contributor guides and machine state describe the same audit plan.

This is intentionally a validation-only command. Updating the plan digest or a
state field is a reviewable source change; the checker never silently rewrites
the project state to make a stale guide appear current.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("PLAN.md")
STATE = Path(".mister/state.json")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DOCUMENT_TOKENS = {
    Path("README.md"): ("PLAN.md", "PROGRESS.md", ".mister/state.json", "accepted"),
    Path("CORE_COMPLETION_AUDIT.md"): ("PLAN.md", "PROGRESS.md", ".mister/state.json"),
    Path("support/ARM_RUNTIME.md"): ("../PLAN.md", "diablo_launch.py",
                                      "DIABLO_MISTER_ADMISSION_FILE"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read state: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("state root must be an object")
    return value


def is_local_link(target: str) -> bool:
    return not target.startswith(("#", "http:", "https:", "mailto:", "codex:"))


def document_problems(root: Path, document: Path, tokens: tuple[str, ...]) -> list[str]:
    path = root / document
    problems: list[str] = []
    if not path.is_file():
        return [f"required guide is missing: {document}"]
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        if token.lower() not in text.lower():
            problems.append(f"{document} does not identify required guidance: {token}")
    for target in LINK.findall(text):
        target = target.strip().strip("<>")
        if not is_local_link(target):
            continue
        file_part = target.split("#", 1)[0]
        if not file_part:
            continue
        candidate = (path.parent / file_part).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            problems.append(f"{document} link escapes project: {target}")
            continue
        if not candidate.exists():
            problems.append(f"{document} has a broken local link: {target}")
    return problems


def validate(root: Path) -> dict[str, object]:
    root = root.resolve()
    problems: list[str] = []
    plan = root / PLAN
    if not plan.is_file():
        problems.append(f"completion plan is missing: {PLAN}")
    for document, tokens in DOCUMENT_TOKENS.items():
        problems.extend(document_problems(root, document, tokens))
    try:
        state = read_state(root / STATE)
        if state.get("schema") != "diablo-project-state-v2":
            problems.append("state schema is not diablo-project-state-v2")
        if state.get("completion_document") != PLAN.as_posix():
            problems.append("state completion_document does not name the detailed closure plan")
        if plan.is_file() and state.get("completion_document_sha256") != sha256(plan):
            problems.append("state completion_document_sha256 is stale")
        if "next_exact_command" in state:
            problems.append("state labels prose as next_exact_command; use next_action or an executable command")
        if not isinstance(state.get("next_action"), str) or not state["next_action"].strip():
            problems.append("state needs a non-empty next_action")
        candidate = state.get("candidate")
        if not isinstance(candidate, dict) or candidate.get("state") != "no-current-accepted-candidate" or candidate.get("id") is not None:
            problems.append("state must explicitly identify that no current accepted candidate exists")
        if state.get("accepted_build_id") is not None:
            problems.append("accepted_build_id must remain null until an accepted candidate exists")
    except ValueError as error:
        problems.append(str(error))
    return {"schema": "diablo-guide-status-v1", "ok": not problems, "plan": PLAN.as_posix(),
            "plan_sha256": sha256(plan) if plan.is_file() else None, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = validate(args.root)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify DIST-STATUS banner blocks in repo READMEs match registry distribution_status.

For every public entry with a local checkout, the README.md is checked:
- source_only entries must contain a DIST-STATUS banner naming the source install.
- published entries must not carry a stale source-only banner.

Usage: check_dist_status.py [--root DIR]   (default root: ecosystem root)
"""
import argparse
import re
import sys
from pathlib import Path

import json

HUB = Path(__file__).resolve().parent.parent
BEGIN = re.compile(r"<!--\s*DIST-STATUS:BEGIN")
END = re.compile(r"<!--\s*DIST-STATUS:END")
GIT_URL = "github.com/Icaro0310/{name}.git"


def errors_for(entry: dict, root: Path) -> list[str]:
    name = entry.get("name")
    status = entry.get("distribution_status")
    if not status:
        return []
    repo = root / (entry.get("local_dir") or name)
    if not repo.is_dir():
        return []
    readme = repo / "README.md"
    if not readme.is_file():
        return [f"{name}: checkout exists but README.md is missing"]
    text = readme.read_text(encoding="utf-8", errors="replace")
    begin = BEGIN.search(text)
    end = END.search(text)
    has_block = bool(begin and end and begin.start() < end.start())
    problems = []
    if status == "source_only":
        if not has_block:
            problems.append(f"{name}: source_only but README lacks a DIST-STATUS block")
        elif GIT_URL.format(name=name) not in text[begin.start():end.end()]:
            problems.append(f"{name}: DIST-STATUS block lacks this repo's github.com install URL")
    elif status == "published" and (begin or end):
        problems.append(f"{name}: published but README still carries a DIST-STATUS marker")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=HUB.parent,
                    help="ecosystem root; local_dir paths resolve against it")
    args = ap.parse_args()
    registry = json.loads((HUB / "registry.json").read_text())
    problems = []
    for e in registry["repositories"]:
        if e.get("visibility") == "public":
            problems.extend(errors_for(e, args.root))
    for p in problems:
        print(f"error: {p}")
    print(f"dist-status check: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

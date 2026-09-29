#!/usr/bin/env python3
"""new-repo.py — bootstrap a new devin-* repo from template/.

Usage:
    python tools/new-repo.py <name> "<description>"

Example:
    python tools/new-repo.py history "Session history exporter..."

Creates ../devin-<name>/ next to this repo, fills {{name}} / {{module}} /
{{description}} placeholders, renames src/devin_template -> src/devin_<module>,
and runs `git init -b main`. Does NOT create the GitHub remote — do that with:
    gh repo create Icaro0310/devin-<name> --public --source=. --push
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
ECOSYSTEM = HUB.parent
TEMPLATE = HUB / "template"

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}


def fill(text: str, name: str, module: str, description: str) -> str:
    return (
        text.replace("{{name}}", name)
        .replace("{{module}}", module)
        .replace("{{description}}", description)
        .replace("devin_template", f"devin_{module}")
    )


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    name = sys.argv[1].removeprefix("devin-")
    description = sys.argv[2]
    if not re.fullmatch(r"[a-z0-9-]+", name):
        sys.exit(f"invalid name: {name!r} (kebab-case only)")
    module = name.replace("-", "_")
    dest = ECOSYSTEM / f"devin-{name}"
    if dest.exists():
        sys.exit(f"already exists: {dest}")

    for src in sorted(TEMPLATE.rglob("*")):
        if any(part in SKIP_DIRS for part in src.parts):
            continue
        rel = src.relative_to(TEMPLATE)
        if src.is_dir():
            continue
        rel_str = str(rel).replace("devin_template", f"devin_{module}")
        dst = dest / rel_str
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = src.read_text(encoding="utf-8")
            dst.write_text(fill(content, name, module, description), encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src, dst)

    subprocess.run(["git", "init", "-b", "main"], cwd=dest, check=True)
    print(f"created {dest}")
    print(f"next: cd {dest} && git add -A && git commit -m init && "
          f"gh repo create Icaro0310/devin-{name} --public --source=. --push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

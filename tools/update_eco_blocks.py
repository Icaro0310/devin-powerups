#!/usr/bin/env python3
"""Insert or refresh the generated 'Part of the DEVIN ecosystem' block in
each public tool's README.md.

The block is rendered by ``render_surfaces.py block <name>`` from
registry.json — this script only places it. Insertion point: right after
the first ``</div>`` that closes the centered banner/badges block, falling
back to after the first ``# `` heading. Idempotent: content between
``<!-- DEVIN-ECO:BEGIN -->`` and ``<!-- DEVIN-ECO:END -->`` is replaced.

Usage:
    python3 tools/update_eco_blocks.py --root /path/to/clones [--check]
    python3 tools/update_eco_blocks.py --root ~/devin --repo devin-evals
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
REGISTRY = HUB / "registry.json"

BEGIN = "<!-- DEVIN-ECO:BEGIN -->"
END = "<!-- DEVIN-ECO:END -->"

# Local clone layout: repo name -> path relative to --root.
EXTRA_PATHS = {"poordjaevin": "poordjaevin"}  # lives outside devin-ecosystem/


def render_block(name: str) -> str:
    out = subprocess.run(
        [sys.executable, str(HUB / "tools" / "render_surfaces.py"),
         "block", name],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return f"{BEGIN}\n{out}\n{END}"


def find_insert(lines: list[str]) -> int:
    """Index after the first </div>, else after the first '# ' heading."""
    for i, line in enumerate(lines):
        if "</div>" in line:
            return i + 1
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return i + 1
    return 0


def update_readme(path: Path, block: str) -> bool:
    text = path.read_text(encoding="utf-8")
    block = block + "\n"
    if BEGIN in text and END in text:
        new = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?",
            block, text, count=1, flags=re.DOTALL,
        )
    else:
        lines = text.splitlines(keepends=True)
        at = find_insert(lines)
        insertion = ["\n", block, "\n"]
        if at == 0:
            insertion = [block, "\n"]
        lines[at:at] = insertion
        new = "".join(lines)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True,
                    help="parent of the local clones (devin-ecosystem dir or "
                         "the dir containing it)")
    ap.add_argument("--repo", action="append",
                    help="limit to these repo names (repeatable)")
    ap.add_argument("--check", action="store_true",
                    help="report drift without writing")
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    args = ap.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    names = {
        r["name"] for r in registry["repositories"]
        if r.get("artifact") == "tool" and r.get("visibility") == "public"
        and r.get("public") is not False
    }
    if args.repo:
        names &= set(args.repo)

    eco = args.root / "devin-ecosystem"
    base = eco if eco.is_dir() else args.root
    changed, missing = [], []
    for name in sorted(names):
        rel = EXTRA_PATHS.get(name)
        if rel is None:
            readme = base / name / "README.md"
        else:
            readme = args.root / rel / "README.md"
        if not readme.is_file():
            missing.append(name)
            continue
        block = render_block(name)
        if args.check:
            text = readme.read_text(encoding="utf-8")
            if block not in text:
                changed.append(name)
            continue
        if update_readme(readme, block):
            changed.append(name)

    for name in changed:
        print(("would-update" if args.check else "updated") + f" {name}")
    for name in missing:
        print(f"missing-clone {name}", file=sys.stderr)
    return 1 if (args.check and changed) else 0


if __name__ == "__main__":
    raise SystemExit(main())

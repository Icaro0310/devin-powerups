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

def render_block(name: str, registry: Path) -> str:
    out = subprocess.run(
        [sys.executable, str(HUB / "tools" / "render_surfaces.py"),
         "block", name, "--registry", str(registry.resolve())],
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
        # block already ends with "\n"; add a spacer only when the next
        # existing line is not already blank
        insertion = [block]
        if not (at < len(lines) and not lines[at].strip()):
            insertion.append("\n")
        if at > 0 and lines[at - 1].strip():
            insertion.insert(0, "\n")
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
    entries = [
        r for r in registry["repositories"]
        if r.get("artifact") == "tool" and r.get("visibility") == "public"
        and r.get("public") is not False
    ]
    if args.repo:
        wanted = set(args.repo)
        entries = [e for e in entries if e["name"] in wanted]

    eco = args.root / "devin-ecosystem"
    base = eco if eco.is_dir() else args.root
    registry_dir = args.registry.resolve().parent
    changed, missing = [], []
    for e in sorted(entries, key=lambda x: x["name"]):
        candidates = []
        if e.get("local_dir"):
            # local_dir is recorded relative to the hub clone; an explicit
            # --root selects a different workspace, so resolve there first
            candidates.append(
                (args.root / e["local_dir"]).resolve() / "README.md"
            )
        candidates += [
            base / e["name"] / "README.md",
            args.root / e["name"] / "README.md",
        ]
        if e.get("local_dir"):
            # last resort: the checkout beside the registry itself
            candidates.append(
                (registry_dir / e["local_dir"]).resolve() / "README.md"
            )
        readme = next((c for c in candidates if c.is_file()), candidates[-1])
        if not readme.is_file():
            missing.append(e["name"])
            continue
        block = render_block(e["name"], args.registry)
        if args.check:
            if block not in readme.read_text(encoding="utf-8"):
                changed.append(e["name"])
            continue
        if update_readme(readme, block):
            changed.append(e["name"])

    for name in changed:
        print(("would-update" if args.check else "updated") + f" {name}")
    for name in missing:
        print(f"missing-clone {name}", file=sys.stderr)
    return 1 if (args.check and (changed or missing)) else 0


if __name__ == "__main__":
    raise SystemExit(main())

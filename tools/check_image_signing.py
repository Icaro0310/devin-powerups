#!/usr/bin/env python3
"""Fail when a workflow pushes a container image without cosign signing.

For every public registry entry with a local checkout, scan
``.github/workflows/*.yml`` (and ``.yaml``): a workflow that pushes to a
container registry (``ghcr.io``) must also grant ``id-token: write`` and
invoke cosign/sigstore — otherwise a new image workflow is born unsigned
and nobody notices.

Usage: check_image_signing.py [--root DIR]   (default root: ecosystem root)
"""
import argparse
import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
PUSH_RE = re.compile(r"ghcr\.io")
SIGN_RE = re.compile(r"cosign|sigstore")
TOKEN_RE = re.compile(r"id-token:\s*write")


def problems_for(repo: Path, name: str) -> list[str]:
    wf_dir = repo / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    problems = []
    for wf in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        text = wf.read_text(encoding="utf-8", errors="replace")
        if not PUSH_RE.search(text):
            continue
        if not TOKEN_RE.search(text):
            problems.append(
                f"{name}: {wf.name} pushes a container image without "
                "'id-token: write' — cosign keyless needs the OIDC token"
            )
        if not SIGN_RE.search(text):
            problems.append(
                f"{name}: {wf.name} pushes a container image but never "
                "signs it — add sigstore/cosign-installer + 'cosign sign'"
            )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=HUB.parent,
                    help="ecosystem root; local_dir paths resolve against it")
    args = ap.parse_args()
    registry = json.loads((HUB / "registry.json").read_text())
    problems = []
    for e in registry["repositories"]:
        if e.get("visibility") != "public":
            continue
        name = e.get("name")
        repo = args.root / (e.get("local_dir") or name)
        if repo.is_dir():
            problems.extend(problems_for(repo, name))
    for p in problems:
        print(f"error: {p}")
    print(f"image-signing check: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

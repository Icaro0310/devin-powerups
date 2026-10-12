#!/usr/bin/env python3
"""Fail when a workflow pushes a container image without cosign signing.

For every public registry entry with a local checkout, scan
``.github/workflows/*.yml`` (and ``.yaml``): a workflow that pushes a
container image (a registry push command, a ``--push`` build flag, or a
build-push/bake-action ``push:`` input that is not literal ``false``)
must also grant ``id-token: write`` and actually sign (``cosign
sign``/``attest`` or a sigstore signing action) — otherwise a new image
workflow is born unsigned and nobody notices. Pulls, image references
and comments mentioning a registry do not count as publishing.

Usage: check_image_signing.py [--root DIR]   (default root: ecosystem root)
"""
import argparse
import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
# Publishing evidence: a push verb or --push flag in a run step, or a
# 'push:' input with a truthy value. A bare registry hostname (pulls,
# image refs, comments) is not a publish. 'push:' at line end is the
# 'on: push' trigger, not an action input, so a value must follow.
PUSH_RE = re.compile(
    r"(?:docker|podman|nerdctl|buildah|crane|oras)\s+(?:compose\s+)?push\b"
    r"|--push\b"
    r"|\bpush:[ \t]+(?!false\b|\{)\S"
)
# Signing evidence: an actual sign/attest invocation or a sigstore signing
# action — a bare 'cosign'/'sigstore' mention (comment, env var, install
# step, 'cosign verify') never produced a signature.
SIGN_RE = re.compile(
    r"cosign\s+(?:sign|attest)\b"
    r"|docker\s+trust\s+sign\b"
    r"|notation\s+sign\b"
    r"|uses:\s*sigstore/gh-action-sigstore-python"
)
TOKEN_RE = re.compile(r"id-token:\s*write")


def _code_lines(text: str) -> str:
    """Strip comment lines and trailing ' #...' so a commented-out push,
    token grant or sign step cannot fake (or fabricate) evidence."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(re.sub(r"[ \t]+#.*$", "", line))
    return "\n".join(out)


def problems_for(repo: Path, name: str) -> list[str]:
    wf_dir = repo / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    problems = []
    for wf in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        text = _code_lines(wf.read_text(encoding="utf-8", errors="replace"))
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

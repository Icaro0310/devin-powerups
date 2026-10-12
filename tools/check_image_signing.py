#!/usr/bin/env python3
"""Fail when a workflow pushes a container image without cosign signing.

For every public registry entry with a local checkout, scan
``.github/workflows/*.yml`` (and ``.yaml``): a workflow that pushes a
container image (a registry push command such as ``docker push`` or
``docker image push``, a ``--push`` build flag that is not disabled,
``--output=type=registry``, or a build-push/bake-action ``push:`` input
that is not ``false``)
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
# Publishing evidence: a registry CLI push ('docker push', 'docker image
# push', 'docker manifest push', 'docker[- ]compose push',
# podman/crane/oras equivalents), a --push flag that is not '=false', a
# build-push/bake 'push:' input that is not 'false', or a buildx
# 'output=type=registry' target. The subcommand list is a closed set so
# an image named 'push' (e.g. 'docker image inspect push') is not a
# publish. A bare registry hostname (pulls, image refs, comments) is not
# a publish, and 'push:' at line end is the 'on: push' trigger, not an
# action input.
PUSH_RE = re.compile(
    r"(?:docker|podman|nerdctl|buildah|crane|oras)(?:-compose)?\s+"
    # Global CLI flags may sit between the binary and the push verb.
    # Valueless flags take nothing; valued flags take '=v' or ' v' — a
    # flag must never swallow the push word itself.
    r"(?:(?:--debug|-D|--tlsverify|--tls|--help)\s+"
    r"|(?:--log-level|-l|--host|-H|--context|-c|--config"
    r"|--tlscacert|--tlscert|--tlskey)(?:[ =]\S+)\s+)*"
    r"(?:(?:compose|image|manifest)\s+)?push\b"
    r"|--push\b(?![ \t]*=[ \t]*['\"]?(?i:false)['\"]?)"
    r"|\bpush:[ \t]+(?!['\"]?(?i:false)['\"]?|\{)\S"
    r"|\boutput=type=registry\b"
    r"|--output[ \t]+type=registry\b"
    r"|-o[ \t]+type=registry\b"
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


_YAML_KEY_RE = re.compile(r"^\s*(?:-\s*)?[\w.-]+\s*:\s*")


def _code_lines(text: str) -> str:
    """Strip comments, and blank mid-line quoted interiors.

    A '#' opens a comment only outside quotes and only at line start or
    after whitespace, so 'run: echo "a # b"; docker push x' keeps its
    push. But text inside a shell-level quote is an argument, not a
    command: 'echo "# cosign sign x"' must not count as signing evidence,
    so every quoted span mid-line has its interior blanked (the quote
    chars stay, the '#' inside no longer needs to survive). The one
    exception is a quoted YAML scalar right after 'key:' — 'run: "docker
    push x"' is the whole value and keeps its content.
    """
    out = []
    for line in text.splitlines():
        i = 0
        # A 'key:' followed by a quote opens a YAML-level scalar: keep it.
        m = _YAML_KEY_RE.match(line)
        if m and m.end() < len(line) and line[m.end()] in "'\"":
            q = line[m.end()]
            i = m.end() + 1
            while i < len(line):
                if line[i] == "\\" and q == '"':
                    i += 1
                elif line[i] == q:
                    i += 1
                    break
                i += 1
        buf = list(line[:i])
        quote = None  # mid-line "'", '"' or None (outside quotes)
        while i < len(line):
            c = line[i]
            if quote == '"':
                if c == "\\":
                    buf.append(c)
                    i += 1
                    buf.append(line[i])
                elif c == '"':
                    buf.append(c)
                    quote = None
                else:
                    buf.append(" ")
            elif quote == "'":
                if c == "'":
                    buf.append(c)
                    quote = None
                else:
                    buf.append(" ")
            elif c in "'\"":
                quote = c
                buf.append(c)
            elif c == "#" and (i == 0 or line[i - 1] in " \t"):
                break
            else:
                buf.append(c)
            i += 1
        out.append("".join(buf).rstrip())
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

#!/usr/bin/env python3
"""Render discovery surfaces from registry.json.

The registry already carries the semantic layer (track, role, nature,
mode, maturity, audiences, interfaces). This tool turns that metadata
into generated, derivable surfaces so hand-edited copies never drift:

- ``intent``    — "What do you want to do?" map (track -> tools)
- ``audience``  — browse-by-audience grouping
- ``interface`` — browse-by-interface grouping
- ``block``     — per-repo "Part of the DEVIN ecosystem" README block
- ``counts``    — derivable headline numbers

Consumed by awesome-devin, the profile README, the site and per-repo
README blocks. Editorial copy (positioning, claims) is never generated.

Usage:
    python3 tools/render_surfaces.py intent
    python3 tools/render_surfaces.py block devin-evals
    python3 tools/render_surfaces.py counts --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
REGISTRY = HUB / "registry.json"

# track -> (order, intent verb, one-line promise). Product tracks only.
TRACK_META = {
    "observe": (0, "Understand", "observe sessions, activity and behavior"),
    "assure": (1, "Verify", "validate claims, actions and outcomes"),
    "guard": (2, "Control", "constrain execution, data and lifecycle"),
    "platform": (3, "Build", "create integrations and tooling"),
    "navigation": (4, "Navigate", "find your way across the ecosystem"),
    "related": (5, "Related", "adjacent projects and artifacts"),
}

AUDIENCE_LABELS = {
    "qa": "QA engineers",
    "developers": "developers",
    "ai-engineers": "AI engineers",
    "security": "security engineers",
    "operations": "operations",
    "maintainers": "maintainers",
    "end-users": "end users",
}

INTERFACE_LABELS = {
    "cli": "CLI",
    "library": "Python library",
    "mcp": "MCP server",
    "dashboard": "dashboard",
    "service": "service",
    "installer": "installer",
    "automation": "automation",
    "bridge": "bridge",
    "registry": "registry",
    "docs": "docs",
}


def public_entries(registry: dict) -> list[dict]:
    return [
        r for r in registry["repositories"]
        if r.get("visibility") == "public" and r.get("public") is not False
    ]


def _line(repo: dict) -> str:
    return f"- [`{repo['name']}`]({repo['url']}) — {repo['description']}"


def render_intent_map(registry: dict) -> str:
    """'What do you want to do?' — tracks as intents, tools underneath."""
    by_track: dict[str, list[dict]] = defaultdict(list)
    for repo in public_entries(registry):
        track = repo.get("track")
        if track:
            by_track[track].append(repo)
    lines = ["## What do you want to do?", ""]
    ordered = sorted(
        by_track, key=lambda t: (TRACK_META.get(t, (90, t.title(), ""))[0], t)
    )
    for track in ordered:
        _, verb, promise = TRACK_META.get(track, (90, track.title(), ""))
        suffix = f" — {promise}" if promise else ""
        lines += [f"**{verb}**{suffix}", ""]
        lines += [_line(r) for r in sorted(by_track[track], key=lambda r: r["name"])]
        lines.append("")
    return "\n".join(lines).rstrip()


def render_browse(registry: dict, axis: str) -> str:
    """Group public entries by ``audiences`` or ``interfaces``."""
    if axis not in ("audiences", "interfaces"):
        raise ValueError(f"unknown axis {axis}")
    labels = AUDIENCE_LABELS if axis == "audiences" else INTERFACE_LABELS
    groups: dict[str, list[dict]] = defaultdict(list)
    for repo in public_entries(registry):
        for value in repo.get(axis) or []:
            groups[value].append(repo)
    title = "Browse by audience" if axis == "audiences" else "Browse by interface"
    lines = [f"## {title}", ""]
    for value in sorted(groups, key=lambda v: labels.get(v, v)):
        label = labels.get(value, value)
        lines += [f"**{label}**", ""]
        lines += [_line(r) for r in sorted(groups[value], key=lambda r: r["name"])]
        lines.append("")
    return "\n".join(lines).rstrip()


def render_tool_block(repo: dict) -> str:
    """Per-repo README block: where it fits and what it connects to."""
    track = repo.get("track")
    track_line = TRACK_META.get(track, (9, track or "related", ""))[1]
    audiences = ", ".join(
        AUDIENCE_LABELS.get(a, a) for a in repo.get("audiences") or []
    ) or "ecosystem users"
    interfaces = " / ".join(
        INTERFACE_LABELS.get(i, i) for i in repo.get("interfaces") or []
    ) or "—"
    # trailing two spaces = hard line breaks; plain `>` lines would fold
    # into one paragraph in rendered Markdown
    return "\n".join(
        [
            "> **Part of the [DEVIN ecosystem](https://github.com/Icaro0310/awesome-devin)**  ",
            f"> Track: {track_line} · Nature: {repo.get('nature', 'product')}  ",
            f"> For: {audiences}  ",
            f"> Interface: {interfaces}",
        ]
    )


def counts(registry: dict) -> dict:
    pub = public_entries(registry)
    return {
        "registry_version": registry.get("version"),
        "entries": len(registry["repositories"]),
        "public_entries": len(pub),
        "tools": sum(1 for r in pub if r.get("artifact") == "tool"),
        "tracks": dict(
            sorted(
                {
                    t: sum(1 for r in pub if r.get("track") == t)
                    for t in {r.get("track") for r in pub} - {None}
                }.items()
            )
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "surface",
        choices=["intent", "audience", "interface", "block", "counts"],
    )
    ap.add_argument("name", nargs="?", help="repo name for surface=block")
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--json", action="store_true", help="machine output")
    args = ap.parse_args(argv)

    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.surface == "counts":
        out = counts(registry)
        print(json.dumps(out, indent=2) if args.json else out)
        return 0

    if args.json:
        print("error: --json is only supported for surface=counts",
              file=sys.stderr)
        return 2

    if args.surface == "block":
        if not args.name:
            print("error: surface=block needs a repo name", file=sys.stderr)
            return 2
        repo = next(
            (r for r in public_entries(registry) if r["name"] == args.name),
            None,
        )
        if repo is None:
            print(f"error: unknown repo {args.name}", file=sys.stderr)
            return 2
        print(render_tool_block(repo))
        return 0

    if args.surface == "intent":
        print(render_intent_map(registry))
    elif args.surface == "audience":
        print(render_browse(registry, "audiences"))
    elif args.surface == "interface":
        print(render_browse(registry, "interfaces"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
    "developers": "Developers",
    "ai-engineers": "AI engineers",
    "security": "Security engineers",
    "operations": "Local-first ops",
    "maintainers": "Maintainers",
    "end-users": "End users",
    "devops": "DevOps engineers",
    "data-scientists": "Data Scientists",
}

INTERFACE_LABELS = {
    "cli": "CLI",
    "library": "Python library",
    "mcp": "MCP server",
    "dashboard": "Dashboard",
    "service": "Service",
    "installer": "Installer",
    "automation": "Automation",
    "bridge": "Bridge",
    "registry": "Registry",
    "docs": "Docs",
}


def public_entries(registry: dict) -> list[dict]:
    return [
        r for r in registry["repositories"]
        if r.get("visibility") == "public" and r.get("public") is not False
    ]


def _line(repo: dict) -> str:
    return f"- [`{repo['name']}`]({repo['url']}) — {repo['description']}"


def render_intent_map(registry: dict) -> str:
    """'What do you want to do?' — jobs as intents, tools underneath."""
    job_to_track = {"understand": "observe", "verify": "assure",
                    "control": "guard", "build": "platform"}
    categories = registry.get("devkit", {}).get("tools", {})
    by_track: dict[str, list[dict]] = defaultdict(list)
    for repo in public_entries(registry):
        track = job_to_track.get(repo.get("job"))
        # Foundation-category tools (e.g. internals-spec) are not a job;
        # track fallback stays for non-product entries (hub, related, nav).
        if track is None and categories.get(repo["name"], {}).get("category") != "foundation":
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


def validate_journeys(registry: dict) -> list[str]:
    """Cross-check ``journeys`` against repository entries — the schema
    constrains shape, but repo references and audience fit are semantic."""
    import validate_registry as vr

    errors = vr.journey_errors(registry)
    for audience in (registry.get("journeys") or {}):
        if audience not in AUDIENCE_LABELS:
            errors.append(f"journeys.{audience}: unknown audience")
    return errors


def render_journeys(registry: dict) -> str:
    """Curated 'Paths by audience' — ordered steps with reasons, the
    editorial layer above the flat browse lists."""
    errors = validate_journeys(registry)
    if errors:
        raise ValueError("; ".join(errors))
    journeys = registry.get("journeys") or {}
    by_name = {r["name"]: r for r in public_entries(registry)}
    lines = ["## Paths by audience", ""]
    for audience in sorted(journeys, key=lambda a: AUDIENCE_LABELS.get(a, a)):
        lines += [f"**{AUDIENCE_LABELS.get(audience, audience)}**", ""]
        for i, step in enumerate(journeys[audience], 1):
            repo = by_name[step["repo"]]
            name = step.get("label") or repo["name"]
            url = step.get("url") or repo["url"]
            lines.append(f"{i}. [`{name}`]({url}) — {step['why']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def journey_context(registry: dict) -> dict[str, list[dict]]:
    """repo name -> ordered path memberships: audience, step, neighbours."""
    ctx: dict[str, list[dict]] = {}
    for audience, steps in (registry.get("journeys") or {}).items():
        for i, step in enumerate(steps):
            ctx.setdefault(step["repo"], []).append({
                "audience": AUDIENCE_LABELS.get(audience, audience),
                "label": step.get("label"),
                "step": i + 1,
                "total": len(steps),
                "after": (
                    steps[i - 1].get("label") or steps[i - 1]["repo"]
                ) if i else None,
                "before": (
                    steps[i + 1].get("label") or steps[i + 1]["repo"]
                ) if i + 1 < len(steps) else None,
            })
    return ctx


def render_journeys_html(registry: dict) -> str:
    """Site surface: one card per journey, steps as an ordered chain."""
    errors = validate_journeys(registry)
    if errors:
        raise ValueError("; ".join(errors))
    by_name = {r["name"]: r for r in public_entries(registry)}
    lines = []
    for audience in sorted(registry.get("journeys") or {},
                           key=lambda a: AUDIENCE_LABELS.get(a, a)):
        steps = registry["journeys"][audience]
        chain = " &rarr; ".join(
            f'<a href="{s.get("url") or by_name[s["repo"]]["url"]}">'
            f'<code>{s.get("label") or s["repo"]}</code></a>'
            for s in steps
        )
        lines.append(
            f'  <div class="card"><h3>{AUDIENCE_LABELS.get(audience, audience)}</h3>'
            f"<p>{chain}.</p></div>"
        )
    return "\n".join(lines)


def render_journeys_compact(registry: dict) -> str:
    """Profile surface: one line per journey — Audience: a → b → c."""
    errors = validate_journeys(registry)
    if errors:
        raise ValueError("; ".join(errors))
    by_name = {r["name"]: r for r in public_entries(registry)}
    lines = []
    for audience in sorted(registry.get("journeys") or {},
                           key=lambda a: AUDIENCE_LABELS.get(a, a)):
        chain = " → ".join(
            f"[`{s.get('label') or s['repo']}`]"
            f"({s.get('url') or by_name[s['repo']]['url']})"
            for s in registry["journeys"][audience]
        )
        lines.append(f"- **{AUDIENCE_LABELS.get(audience, audience)}:** {chain}")
    return "\n".join(lines)


def render_tool_block(repo: dict, registry: dict | None = None) -> str:
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
    lines = [
        "> **Part of the [DEVIN ecosystem](https://github.com/Icaro0310/awesome-devin)**",
        f"> Track: {track_line} · Nature: {repo.get('nature', 'product')}",
        f"> For: {audiences}",
        f"> Interface: {interfaces}",
    ]
    if registry is not None:
        for membership in journey_context(registry).get(repo["name"], []):
            pos = []
            if membership["after"]:
                pos.append(f"after `{membership['after']}`")
            if membership["before"]:
                pos.append(f"before `{membership['before']}`")
            tail = f" — {', '.join(pos)}" if pos else ""
            alias = (
                f" (as `{membership['label']}`)"
                if membership.get("label") and membership["label"] != repo["name"]
                else ""
            )
            lines.append(
                f"> Path: {membership['audience']} · step "
                f"{membership['step']}/{membership['total']}{alias}{tail}"
            )
    return "\n".join(
        line + "  " if i < len(lines) - 1 else line
        for i, line in enumerate(lines)
    )


JOB_LABELS = {
    "understand": "Understand",
    "verify": "Verify",
    "control": "Control",
    "build": "Build",
}


def _package_label(repo: dict) -> str:
    pkg = repo.get("package") or {}
    path = (pkg.get("path") or "").rstrip("/")
    if path and path != ".":
        return path.split("/")[-1]
    return pkg.get("name") or repo["name"].removeprefix("devin-")


def render_where(repo: dict, registry: dict) -> str:
    """'Where this fits' section for product-holder READMEs — the product
    boundary, member packages and governance pointers, all from the
    registry. Rendered only for entries that hold a product_id."""
    members = [
        r for r in registry["repositories"]
        if r.get("product_id") == repo["name"]
    ]
    members.sort(
        key=lambda r: (r["name"] != repo["name"], _package_label(r))
    )
    packages = " · ".join(f"`{_package_label(r)}`" for r in members) or "—"
    mode = {"read": "read-only", "write": "write",
            "mixed": "mixed"}.get(repo.get("mode"), "—")
    job = JOB_LABELS.get(repo.get("job") or "", (repo.get("job") or "—").title())
    lines = [
        "## Where this fits",
        "",
        f"- **Job:** {job}",
        f"- **Product:** [`{repo['name']}`]({repo['url']})",
        f"- **Packages:** {packages}",
        f"- **Mode:** {mode}",
    ]
    if any(
        "devin-internals-spec" in (r.get("package") or {}).get("depends_on", [])
        for r in members
    ):
        lines.append(
            "- **Foundation:** [`devin-internals-spec`]"
            "(https://github.com/Icaro0310/devin-internals-spec)"
        )
    lines.append(
        "- **Ecosystem:** [`awesome-devin`]"
        "(https://github.com/Icaro0310/awesome-devin) · registry: "
        "[`devin-powerups`](https://github.com/Icaro0310/devin-powerups)"
    )
    return "\n".join(lines)


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
        choices=["intent", "audience", "interface", "block", "counts", "paths",
                 "paths-compact", "paths-html", "where"],
    )
    ap.add_argument("name", nargs="?", help="repo name for surface=block|where")
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

    if args.surface in ("block", "where"):
        if not args.name:
            print(f"error: surface={args.surface} needs a repo name",
                  file=sys.stderr)
            return 2
        repo = next(
            (r for r in public_entries(registry) if r["name"] == args.name),
            None,
        )
        if repo is None:
            print(f"error: unknown repo {args.name}", file=sys.stderr)
            return 2
        if args.surface == "where" and not any(
            r.get("product_id") == repo["name"]
            for r in registry["repositories"]
        ):
            print(f"error: {args.name} holds no product", file=sys.stderr)
            return 2
        print(
            render_tool_block(repo, registry)
            if args.surface == "block"
            else render_where(repo, registry)
        )
        return 0

    if args.surface == "intent":
        print(render_intent_map(registry))
    elif args.surface == "paths":
        print(render_journeys(registry))
    elif args.surface == "paths-compact":
        print(render_journeys_compact(registry))
    elif args.surface == "paths-html":
        print(render_journeys_html(registry))
    elif args.surface == "audience":
        print(render_browse(registry, "audiences"))
    elif args.surface == "interface":
        print(render_browse(registry, "interfaces"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

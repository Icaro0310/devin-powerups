#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
REGISTRY = HUB / "registry.json"


def _escape(value: str) -> str:
    return " ".join(value.replace("|", "\\|").split())


def catalog_sections(registry: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    public = [r for r in registry["repositories"] if r.get("visibility") == "public"]
    devkit_tools = registry.get("devkit", {}).get("tools", {})
    tools = [
        r for r in public
        if r.get("artifact") == "tool"
        and (r["name"].startswith("devin-") or r["name"] in devkit_tools)
    ]
    hubs = [r for r in public if r.get("artifact") == "infrastructure"]
    distributions = [r for r in public if r.get("artifact") == "distribution"]
    grouped = {r["name"] for r in tools + hubs + distributions}
    related = [r for r in public if r["name"] not in grouped]
    return tools, hubs, distributions, related


def render_profile_catalog(registry: dict) -> str:
    tools, hubs, distributions, related = catalog_sections(registry)
    categories = registry["devkit"]["tools"]
    category_labels = {"qa": "QA", "evaluation": "Evaluation", "security": "Security", "memory": "Memory", "operations": "Operations", "governance": "Governance", "foundation": "Foundation"}
    track_labels = {
        "observe": "Understand",
        "assure": "Verify",
        "guard": "Control",
        "platform": "Build",
        "navigation": "Navigate",
        # "related" intentionally falls back to the devkit category —
        # a first-party tool labeled Related reads as external.
    }
    entry_count = len(tools) + len(hubs) + len(distributions) + len(related)
    product_count = len({r["product_id"] for r in tools if r.get("product_id")})
    plural = lambda n: "" if n == 1 else "s"  # noqa: E731
    lines = [
        f"<summary><b>The ecosystem — {product_count} products · {len(tools)} first-party tools · {len(distributions)} distribution layer{plural(len(distributions))} · {len(hubs)} registry hub{plural(len(hubs))} · {len(related)} related artifact{plural(len(related))} ({entry_count} entries)</b></summary>",
        "",
        "<br/>",
        "",
        "*(Understand / Verify / Control / Build are the public tracks;*",
        "*Operations, Distribution and Maintainer hub are support roles.)*",
        "",
        "| Group | Repo | What it does |",
        "|---|---|---|",
    ]
    for repo in tools:
        name = repo["name"]
        group = track_labels.get(repo.get("track"))
        if group is None:
            group = category_labels[categories[name]["category"]]
        lines.append(
            f"| **{group}** | [`{name}`]({repo['url']}) | {_escape(repo['description'])} |"
        )
    for repo in distributions:
        lines.append(
            f"| **Distribution** | [`{repo['name']}`]({repo['url']}) | {_escape(repo['description'])} |"
        )
    for repo in hubs:
        lines.append(
            f"| **Maintainer hub** | [`{repo['name']}`]({repo['url']}) | {_escape(repo['description'])} |"
        )
    for repo in related:
        artifact = repo.get("artifact", "project").replace("-", " ").title()
        lines.append(
            f"| **Related {artifact}** | [`{repo['name']}`]({repo['url']}) | {_escape(repo['description'])} |"
        )
    return "\n".join(lines)


def patch_profile_catalog(text: str, rendered: str) -> str:
    begin = "<!-- DEVIN-CATALOG:BEGIN -->"
    end = "<!-- DEVIN-CATALOG:END -->"
    start = text.index(begin) + len(begin)
    stop = text.index(end)
    return text[:start] + "\n" + rendered.rstrip() + "\n" + text[stop:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the public profile catalog from registry.json.")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args(argv)

    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        rendered = render_profile_catalog(registry) + "\n"
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            current = args.check.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read {args.check}: {exc}", file=sys.stderr)
            return 1
        if rendered.rstrip() not in current:
            print(f"stale catalog: {args.check}", file=sys.stderr)
            return 1
        print(f"ok: catalog in {args.check} matches registry.json")
        return 0

    if args.patch:
        try:
            current = args.patch.read_text(encoding="utf-8")
            args.patch.write_text(patch_profile_catalog(current, rendered), encoding="utf-8")
        except (OSError, ValueError) as exc:
            print(f"error: cannot patch {args.patch}: {exc}", file=sys.stderr)
            return 1
        print(f"ok: catalog in {args.patch} matches registry.json")
        return 0

    if args.out:
        try:
            args.out.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

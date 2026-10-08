#!/usr/bin/env python3
"""Fork-visibility metrics: our PRs in upstream awesome-lists.

Counts pull requests authored by the owner in repositories we do not own,
grouped by upstream repo and outcome (open / merged / closed-unmerged).
This is the funnel for the awesome-list submission campaign: submitted →
merged upstream → referral traffic.

A PR counts toward the funnel only when it promotes a first-party tool —
its title or body must name one of the repositories registered in
registry.json (or a known package name). PRs by the same author that do
not promote a tool (portfolio entries, CI fixes to the upstream repo)
are kept under ``other`` for transparency but excluded from the funnel
counts. A failed GitHub search is recorded in ``errors`` and makes the
totals ``null`` — never a silent zero.

Usage:
    python3 tools/fork_visibility.py [--json out.json] [--md]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

OWNER = "Icaro0310"
HUB = Path(__file__).resolve().parent.parent


def tool_names() -> list[str]:
    """First-party names a campaign PR promotes (registry + packages)."""
    names: set[str] = set()
    try:
        registry = json.loads((HUB / "registry.json").read_text())
    except (OSError, json.JSONDecodeError):
        registry = {}
    for section in ("repositories", "tools"):
        for entry in registry.get(section, []) or []:
            for key in ("name", "repo", "pypi", "npm", "package"):
                value = entry.get(key)
                if isinstance(value, str) and value:
                    names.add(value.split("/")[-1].lower())
    # safety net for anything the registry does not name
    names.add("poordjaevin")
    return sorted(n for n in names if len(n) > 2)


def gh_search(query: str) -> list[dict]:
    out = subprocess.run(
        [
            "gh", "api", "--paginate",
            f"search/issues?q={query}&per_page=100",
            "--jq", ".items[] | @json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"gh api failed: {out.stderr.strip()[:200]}")
    return [json.loads(l) for l in out.stdout.strip().splitlines() if l]


def collect() -> dict:
    errors: list[str] = []
    items: list[dict] = []
    try:
        items = gh_search(f"author:{OWNER}+type:pr+-user:{OWNER}")
    except RuntimeError as exc:
        errors.append(str(exc))

    names = tool_names()
    pattern = re.compile(
        "|".join(re.escape(n) for n in names), re.IGNORECASE
    ) if names else None

    repos: dict[str, dict] = defaultdict(
        lambda: {"open": 0, "merged": 0, "closed_unmerged": 0, "prs": [], "other": []}
    )
    for item in items:
        repo = "/".join(item["repository_url"].split("/")[-2:])
        pr = item.get("pull_request") or {}
        merged = bool(pr.get("merged_at"))
        state = (
            "merged" if merged
            else "open" if item["state"] == "open"
            else "closed_unmerged"
        )
        text = f"{item.get('title') or ''}\n{item.get('body') or ''}"
        promotes = sorted({m.lower() for m in pattern.findall(text)}) if pattern else []
        entry = {
            "title": item["title"],
            "url": item.get("html_url"),
            "state": state,
            "merged_at": pr.get("merged_at"),
        }
        if promotes:
            entry["promotes"] = promotes
            repos[repo][state] += 1
            repos[repo]["prs"].append(entry)
        else:
            repos[repo]["other"].append(entry)

    totals = None
    if not errors:
        totals = {
            "open": sum(m["open"] for m in repos.values()),
            "merged": sum(m["merged"] for m in repos.values()),
            "closed_unmerged": sum(m["closed_unmerged"] for m in repos.values()),
            "other": sum(len(m["other"]) for m in repos.values()),
        }
    return {
        "date": date.today().isoformat(),
        "upstream_prs": {
            repo: {
                "open": m["open"],
                "merged": m["merged"],
                "closed_unmerged": m["closed_unmerged"],
                "other": len(m["other"]),
            }
            for repo, m in sorted(repos.items())
        },
        "details": dict(sorted(repos.items())),
        "totals": totals,
        "errors": errors,
    }


def to_markdown(snap: dict) -> str:
    lines = [
        f"## Fork visibility {snap['date']}",
        "",
        "| upstream repo | open | merged | closed unmerged |",
        "|---|---|---|---|",
    ]
    for repo, m in snap["upstream_prs"].items():
        lines.append(
            f"| {repo} | {m['open']} | {m['merged']} | {m['closed_unmerged']} |"
        )
    t = snap["totals"]
    if t:
        lines.append(
            f"| **total** | **{t['open']}** | **{t['merged']}** | "
            f"**{t['closed_unmerged']}** |"
        )
    else:
        lines.append("| **total** | n/a | n/a | n/a |")
    if snap.get("errors"):
        lines += ["", "Collection errors:", *[f"- {e}" for e in snap["errors"]]]
    other = sum(m["other"] for m in snap["upstream_prs"].values())
    if other:
        lines += [
            "",
            f"({other} PR(s) by the same author excluded — they do not "
            "promote a first-party tool; see `details.*.other`)",
        ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write raw snapshot JSON here")
    ap.add_argument("--md", action="store_true", help="print markdown table")
    args = ap.parse_args()

    snap = collect()
    if args.json:
        Path(args.json).write_text(json.dumps(snap, indent=2) + "\n")
    print(to_markdown(snap) if args.md else json.dumps(snap, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

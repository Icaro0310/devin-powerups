#!/usr/bin/env python3
"""Fork-visibility metrics: our PRs in upstream awesome-lists.

Counts pull requests authored by the owner in repositories we do not own,
grouped by upstream repo and outcome (open / merged / closed-unmerged).
This is the funnel for the awesome-list submission campaign: submitted →
merged upstream → referral traffic.

Usage:
    python3 tools/fork_visibility.py [--json out.json] [--md]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

OWNER = "Icaro0310"


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
        return []
    return [json.loads(l) for l in out.stdout.strip().splitlines() if l]


def collect() -> dict:
    items = gh_search(f"author:{OWNER}+type:pr+-user:{OWNER}")
    repos: dict[str, dict] = defaultdict(
        lambda: {"open": 0, "merged": 0, "closed_unmerged": 0, "prs": []}
    )
    for item in items:
        repo = "/".join(item["repository_url"].split("/")[-2:])
        pr = item.get("pull_request") or {}
        merged = bool(pr.get("merged_at"))
        state = "merged" if merged else ("open" if item["state"] == "open" else "closed_unmerged")
        repos[repo][state] += 1
        repos[repo]["prs"].append(
            {
                "title": item["title"],
                "url": item.get("html_url"),
                "state": state,
                "merged_at": pr.get("merged_at"),
            }
        )
    return {
        "date": date.today().isoformat(),
        "upstream_prs": {
            repo: {
                "open": m["open"],
                "merged": m["merged"],
                "closed_unmerged": m["closed_unmerged"],
            }
            for repo, m in sorted(repos.items())
        },
        "details": dict(sorted(repos.items())),
        "totals": {
            "open": sum(m["open"] for m in repos.values()),
            "merged": sum(m["merged"] for m in repos.values()),
            "closed_unmerged": sum(m["closed_unmerged"] for m in repos.values()),
        },
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
    lines += [
        f"| **total** | **{t['open']}** | **{t['merged']}** | **{t['closed_unmerged']}** |",
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

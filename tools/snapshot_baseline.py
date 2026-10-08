#!/usr/bin/env python3
"""Collect a P5 adoption baseline snapshot for the public ecosystem.

Reads registry.json, then per public repository collects:

- GitHub: stargazers, forks, watchers, open issues, open PRs
- GitHub traffic (push access): views and clones over the trailing 14 days
- Package downloads (published entries only): PyPI via pypistats.org,
  npm via api.npmjs.org — both keyless

Usage:
    python3 tools/snapshot_baseline.py [--json out.json] [--md]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.json"
OWNER = "Icaro0310"


def gh_api(path: str) -> dict:
    out = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return {}
    return json.loads(out.stdout or "{}")


def http_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def collect_repo(name: str) -> dict:
    repo = gh_api(f"repos/{OWNER}/{name}")
    views = gh_api(f"repos/{OWNER}/{name}/traffic/views")
    clones = gh_api(f"repos/{OWNER}/{name}/traffic/clones")
    prs = gh_api(f"repos/{OWNER}/{name}/pulls?state=open&per_page=100")
    return {
        "stars": repo.get("stargazers_count"),
        "forks": repo.get("forks_count"),
        "watchers": repo.get("subscribers_count"),
        "open_issues": repo.get("open_issues_count"),
        "open_prs": len(prs) if isinstance(prs, list) else None,
        "views_14d": views.get("count"),
        "unique_visitors_14d": views.get("uniques"),
        "clones_14d": clones.get("count"),
        "unique_cloners_14d": clones.get("uniques"),
    }


def collect_downloads(registry: dict) -> dict:
    out = {}
    for name, tool in (registry.get("devkit", {}).get("tools") or {}).items():
        if tool.get("status") != "published":
            continue
        src, pkg = tool.get("source"), tool.get("package")
        if src == "pypi" and pkg:
            data = http_json(
                f"https://pypistats.org/api/packages/{pkg}/recent"
            ).get("data", {})
            out[pkg] = {
                "pypi_last_month": data.get("last_month"),
                "pypi_last_week": data.get("last_week"),
            }
        elif src == "npm" and pkg:
            data = http_json(
                f"https://api.npmjs.org/downloads/point/last-month/{pkg}"
            )
            out[pkg] = {"npm_last_month": data.get("downloads")}
    return out


def to_markdown(snapshot: dict) -> str:
    lines = [
        f"## Snapshot {snapshot['date']}",
        "",
        "| repo | stars | forks | open issues | open PRs | views 14d | clones 14d |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, m in sorted(snapshot["repos"].items()):
        lines.append(
            f"| {name} | {m['stars']} | {m['forks']} | {m['open_issues']} "
            f"| {m['open_prs']} | {m['views_14d']} ({m['unique_visitors_14d']}u) "
            f"| {m['clones_14d']} ({m['unique_cloners_14d']}u) |"
        )
    lines += ["", "| package | downloads last month |", "|---|---|"]
    for pkg, m in sorted(snapshot["downloads"].items()):
        val = m.get("pypi_last_month", m.get("npm_last_month"))
        lines.append(f"| {pkg} | {val} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write raw snapshot JSON here")
    ap.add_argument("--md", action="store_true", help="print markdown table")
    args = ap.parse_args()

    registry = json.loads(REGISTRY.read_text())
    repos = [
        e["name"]
        for e in registry["repositories"]
        if e.get("visibility") == "public"
    ]

    snapshot = {
        "date": date.today().isoformat(),
        "registry_version": registry.get("version"),
        "repos": {name: collect_repo(name) for name in repos},
        "downloads": collect_downloads(registry),
    }

    if args.json:
        Path(args.json).write_text(json.dumps(snapshot, indent=2) + "\n")
    print(to_markdown(snapshot) if args.md else json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

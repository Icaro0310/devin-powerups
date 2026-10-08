#!/usr/bin/env python3
"""Collect a P5 adoption/reliability baseline snapshot for the public ecosystem.

Reads registry.json, then per public repository collects:

- GitHub: stargazers, forks, watchers, open issues (PRs excluded), open PRs
- GitHub traffic (push access): views and clones over the trailing 14 days
- GitHub reliability: conclusion mix of default-branch workflow runs (14d)
- Package downloads (published entries only): PyPI via pypistats.org,
  npm via api.npmjs.org — both keyless

API failures are recorded under each repo's ``errors`` list and never
silently zeroed — a null metric with an error is different from a real 0.

Usage:
    python3 tools/snapshot_baseline.py [--json out.json] [--md]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.json"
OWNER = "Icaro0310"


def gh_api(path: str, errors: list[str]) -> dict | list:
    out = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        errors.append(f"gh api {path}: {out.stderr.strip()[:120]}")
        return {}
    return json.loads(out.stdout or "{}")


def http_json(url: str, errors: list[str]) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        errors.append(f"{url}: {exc}")
        return {}


def collect_repo(name: str) -> dict:
    errors: list[str] = []
    repo = gh_api(f"repos/{OWNER}/{name}", errors)
    views = gh_api(f"repos/{OWNER}/{name}/traffic/views", errors)
    clones = gh_api(f"repos/{OWNER}/{name}/traffic/clones", errors)

    # total_count avoids pagination caps and keeps PRs out of the issue count
    pr_search = gh_api(
        f"search/issues?q=repo:{OWNER}/{name}+type:pr+state:open",
        errors,
    )
    open_prs = (
        pr_search.get("total_count") if isinstance(pr_search, dict) else None
    )
    open_issues_raw = repo.get("open_issues_count")
    open_issues = (
        open_issues_raw - open_prs
        if open_issues_raw is not None and open_prs is not None
        else None
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    ci_errors_before = len(errors)
    conclusions: Counter[str] = Counter()
    for page in range(1, 4):
        runs = gh_api(
            f"repos/{OWNER}/{name}/actions/runs?branch=main"
            f"&created=>={cutoff.date().isoformat()}&per_page=100&page={page}",
            errors,
        )
        page_runs = runs.get("workflow_runs") or []
        for run in page_runs:
            created = datetime.fromisoformat(
                run["created_at"].replace("Z", "+00:00")
            )
            if created >= cutoff and run.get("conclusion"):
                conclusions[run["conclusion"]] += 1
        if len(page_runs) < 100:
            break
    if len(errors) > ci_errors_before:
        ci = {"runs_14d": None, "pass_rate_14d": None, "failures_14d": None}
    else:
        total = sum(conclusions.values())
        ci = {
            "runs_14d": total,
            "pass_rate_14d": (
                round(conclusions["success"] / total, 3) if total else None
            ),
            "failures_14d": conclusions.get("failure", 0)
            + conclusions.get("startup_failure", 0),
        }

    result = {
        "stars": repo.get("stargazers_count"),
        "forks": repo.get("forks_count"),
        "watchers": repo.get("subscribers_count"),
        "open_issues": open_issues,
        "open_prs": open_prs,
        "views_14d": views.get("count"),
        "unique_visitors_14d": views.get("uniques"),
        "clones_14d": clones.get("count"),
        "unique_cloners_14d": clones.get("uniques"),
        "ci": ci,
    }
    if errors:
        result["errors"] = errors
    return result


def collect_downloads(registry: dict) -> dict:
    out = {}
    for name, tool in (registry.get("devkit", {}).get("tools") or {}).items():
        if tool.get("status") != "published":
            continue
        # pypistats/npm rate-limit bursts; pace package-stat calls
        time.sleep(2)
        src, pkg = tool.get("source"), tool.get("package")
        if src == "pypi" and pkg:
            errors: list[str] = []
            data = http_json(
                f"https://pypistats.org/api/packages/{pkg}/recent", errors
            ).get("data", {})
            out[pkg] = {
                "pypi_last_day": data.get("last_day"),
                "pypi_last_week": data.get("last_week"),
                "pypi_last_month": data.get("last_month"),
            }
            if errors:
                out[pkg]["errors"] = errors
        elif src == "npm" and pkg:
            errors = []
            encoded = urllib.parse.quote(pkg, safe="")
            data = http_json(
                f"https://api.npmjs.org/downloads/point/last-month/{encoded}",
                errors,
            )
            out[pkg] = {"npm_last_month": data.get("downloads")}
            if errors:
                out[pkg]["errors"] = errors
    return out


def structure(registry: dict) -> dict:
    """Structural fingerprint: what each snapshot is actually measuring.

    Lets a later analysis correlate metric deltas with structural changes
    instead of freezing the architecture for a 'clean' series.
    """
    entries = {}
    for e in registry["repositories"]:
        entries[e["name"]] = {
            "track": e.get("track"),
            "visibility": e.get("visibility"),
            "artifact": e.get("artifact"),
            "nature": e.get("nature"),
            "role": e.get("role"),
            "mode": e.get("mode"),
            "audiences": e.get("audiences"),
            "interfaces": e.get("interfaces"),
        }
    pub = [e for e in registry["repositories"] if e.get("visibility") == "public"]
    return {
        "registry_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True,
        ).stdout.strip() or None,
        "first_party_tools": sum(
            1 for e in pub if e.get("artifact") == "tool"
        ),
        "public_repos": len(pub),
        "private_repos": len(registry["repositories"]) - len(pub),
        "entries": entries,
    }


def diff_structure(prev: dict, cur: dict) -> dict:
    """Compare two ``structure`` blocks; empty diff if either is missing."""
    pe, ce = (prev or {}).get("entries", {}), cur.get("entries", {})
    out = {
        "created_repos": sorted(set(ce) - set(pe)),
        "removed_repos": sorted(set(pe) - set(ce)),
        "reclassified": sorted(
            n for n in set(pe) & set(ce)
            if any(
                pe[n].get(f) != ce[n].get(f)
                for f in ("track", "nature", "artifact", "role", "mode",
                          "audiences", "interfaces")
            )
        ),
        "visibility_changed": sorted(
            n for n in set(pe) & set(ce)
            if pe[n].get("visibility") != ce[n].get("visibility")
        ),
    }
    return {k: v for k, v in out.items() if v}


def previous_snapshot(today: str) -> dict | None:
    snaps = sorted((ROOT / "snapshots").glob("????-??-??.json"))
    prev = [p for p in snaps if p.stem < today]
    if not prev:
        return None
    try:
        return json.loads(prev[-1].read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _fmt(value: object) -> str:
    return "n/a" if value is None else str(value)


def to_markdown(snapshot: dict) -> str:
    lines = [
        f"## Snapshot {snapshot['date']}",
        "",
        "| repo | stars | forks | open issues | open PRs | views 14d | clones 14d | CI pass 14d |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, m in sorted(snapshot["repos"].items()):
        ci = m["ci"]
        lines.append(
            f"| {name} | {_fmt(m['stars'])} | {_fmt(m['forks'])} "
            f"| {_fmt(m['open_issues'])} | {_fmt(m['open_prs'])} "
            f"| {_fmt(m['views_14d'])} ({_fmt(m['unique_visitors_14d'])}u) "
            f"| {_fmt(m['clones_14d'])} ({_fmt(m['unique_cloners_14d'])}u) "
            f"| {_fmt(ci['pass_rate_14d'])} ({_fmt(ci['runs_14d'])} runs) |"
        )
    lines += ["", "| package | last day | last week | last month |", "|---|---|---|---|"]
    for pkg, m in sorted(snapshot["downloads"].items()):
        if "npm_last_month" in m:
            lines.append(f"| {pkg} | — | — | {_fmt(m['npm_last_month'])} |")
        else:
            lines.append(
                f"| {pkg} | {_fmt(m['pypi_last_day'])} "
                f"| {_fmt(m['pypi_last_week'])} | {_fmt(m['pypi_last_month'])} |"
            )
    errors = {
        n: m["errors"]
        for n, m in {**snapshot["repos"], **snapshot["downloads"]}.items()
        if m.get("errors")
    }
    if errors:
        lines += ["", "**Collection errors:**"]
        lines += [f"- `{n}`: {len(errs)} failed call(s)" for n, errs in sorted(errors.items())]
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

    today = date.today().isoformat()
    struct = structure(registry)
    prev = previous_snapshot(today)
    if prev is None:
        changes: dict | str = "no previous snapshot"
    elif "structure" not in prev:
        changes = "fingerprint established (previous snapshot predates structure)"
    else:
        changes = diff_structure(prev["structure"], struct)
    snapshot = {
        "date": today,
        "registry_version": registry.get("version"),
        "structure": {k: v for k, v in struct.items() if k != "entries"},
        "structural_changes_since_previous": changes,
        "repos": {name: collect_repo(name) for name in repos},
        "downloads": collect_downloads(registry),
    }
    # full per-entry fingerprint is kept for future diffs
    snapshot["structure"]["entries"] = struct["entries"]

    if args.json:
        Path(args.json).write_text(json.dumps(snapshot, indent=2) + "\n")
    print(to_markdown(snapshot) if args.md else json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

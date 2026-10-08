#!/usr/bin/env python3
"""Compare two baseline snapshots: deltas, adoption funnel, CI attribution.

The December audit compares the first dated snapshot against the last one.
This tool turns that pair into a report:

- per-repo deltas (stars, forks, issues, PRs, views, clones, downloads);
- funnel ratios (visitors -> cloners -> installs) so traffic, adoption and
  real dependency are not conflated;
- a CI-vs-human attribution heuristic: repos where clone volume is high
  but unique cloners are low relative to CI runs are flagged as
  CI-dominated candidates. The flag is a hypothesis, not a verdict —
  confirm with per-day traffic/run correlation before drawing
  conclusions (see BASELINE.md and the V4 report §23).

Usage:
    python3 tools/analyze_baseline.py SNAP_A.json SNAP_B.json [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FUNNEL_FIELDS = ("unique_visitors_14d", "unique_cloners_14d")


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def delta(cur: object, prev: object) -> int | None:
    if isinstance(cur, int) and isinstance(prev, int):
        return cur - prev
    return None


def per_repo(a: dict, b: dict) -> list[dict]:
    rows = []
    names = sorted(set(a.get("repos", {})) | set(b.get("repos", {})))
    for name in names:
        pa, pb = a["repos"].get(name), b["repos"].get(name)
        row = {"repo": name}
        if pa is None or pb is None:
            row["status"] = "added" if pb else "removed"
            rows.append(row)
            continue
        row["status"] = "tracked"
        for field in (
            "stars",
            "forks",
            "open_issues",
            "open_prs",
            "views_14d",
            "unique_visitors_14d",
            "clones_14d",
            "unique_cloners_14d",
        ):
            row[field] = delta(pb.get(field), pa.get(field))
            if row[field] is None:
                row[field] = pb.get(field)
        ci = pb.get("ci") or {}
        row["ci_runs_14d"] = ci.get("runs_14d")
        row["ci_pass_rate"] = ci.get("pass_rate_14d")
        rows.append(row)
    return rows


def funnel(repo: dict) -> dict:
    visitors = repo.get("unique_visitors_14d")
    cloners = repo.get("unique_cloners_14d")
    out = {}
    if visitors and cloners is not None:
        out["clone_rate"] = round(cloners / visitors, 2)
    return out


def ci_attribution(repo: dict) -> str:
    """Heuristic flag — see module docstring for the honesty rule."""
    clones = repo.get("clones_14d") or 0
    uniques = repo.get("unique_cloners_14d") or 0
    runs = repo.get("ci_runs_14d")
    if runs is None:
        runs = (repo.get("ci") or {}).get("runs_14d") or 0
    if runs >= 20 and clones >= 10 * uniques and uniques > 0:
        return "ci-dominated?"
    if runs == 0 and uniques > 0:
        return "human-driven"
    return "mixed/unclear"


def report(a: dict, b: dict) -> list[dict]:
    rows = per_repo(a, b)
    for row in rows:
        if row["status"] != "tracked":
            continue
        # Funnel and attribution must read the later snapshot's absolute
        # counts — the row's metric fields are deltas, and dividing deltas
        # produces negative or missing rates.
        latest = b["repos"].get(row["repo"], {})
        row.update(funnel(latest))
        row["attribution"] = ci_attribution(latest)
    return rows


def to_markdown(rows: list[dict], date_a: str, date_b: str) -> str:
    lines = [
        f"# Baseline comparison {date_a} -> {date_b}",
        "",
        "| repo | stars | forks | clones 14d | uniques | clone rate | CI runs | pass | attribution |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] != "tracked":
            lines.append(f"| {r['repo']} | — | — | — | — | — | — | — | {r['status']} |")
            continue
        def g(k):
            v = r.get(k)
            return "—" if v is None else str(v)

        lines.append(
            "| {repo} | {stars} | {forks} | {clones} | {uniques} | {rate} | {runs} | {ps} | {attr} |".format(
                repo=r["repo"],
                stars=g("stars"),
                forks=g("forks"),
                clones=g("clones_14d"),
                uniques=g("unique_cloners_14d"),
                rate=g("clone_rate"),
                runs=g("ci_runs_14d"),
                ps=g("ci_pass_rate"),
                attr=r.get("attribution", "—"),
            )
        )
    lines += [
        "",
        "Attribution is a heuristic: `ci-dominated?` means clones are at",
        "least 10x unique cloners with heavy CI runs. Confirm with per-day",
        "correlation before drawing conclusions.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("snapshot_a", help="earlier snapshot JSON")
    ap.add_argument("snapshot_b", help="later snapshot JSON")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    a, b = load(args.snapshot_a), load(args.snapshot_b)
    rows = report(a, b)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(to_markdown(rows, a.get("date", "?"), b.get("date", "?")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

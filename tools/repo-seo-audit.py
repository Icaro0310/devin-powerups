#!/usr/bin/env python3
"""repo-seo-audit.py — discoverability audit of the owner's public repos.

Lists the GitHub account's repositories via ``gh repo list <owner> --json
name,description,homepageUrl,repositoryTopics,visibility``, keeps only the
public ones and flags every repo missing a description, topics or a
homepage — the metadata GitHub search and awesome-list reviewers key on.
Read-only: nothing is PATCHed or PUT (the fix half stays in PAS
``scripts/repo_seo_fix.py``).

Default output keeps the PAS audit contract — a ``total: N`` header plus
one ``<name> | t=<topic count> | <description>`` line per repo, with a
``<-- GAP`` marker when any audited field is missing. ``--json`` prints
the findings list instead.

Usage:
    python3 tools/repo-seo-audit.py [--owner Icaro0310] [--json] [--out FILE]

Exit codes: 0 = report produced (gaps are findings, not failures) ·
2 = input/tool problem (gh missing, auth failure, bad JSON).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent

DEFAULT_OWNER = "Icaro0310"
GH_TIMEOUT = 30
REPO_FIELDS = "name,description,homepageUrl,repositoryTopics,visibility"


def _run_gh(args: list[str]) -> list:
    """Run a gh command expected to print a JSON array; raise on failure."""
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=GH_TIMEOUT,
    )
    if proc.returncode != 0:
        detail = (
            proc.stderr.strip().splitlines()[0]
            if proc.stderr.strip()
            else "no stderr"
        )
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {detail[:200]}")
    payload = json.loads(proc.stdout)
    if not isinstance(payload, list):
        raise ValueError("gh repo list: expected a JSON array")
    return payload


def fetch_repos(owner: str) -> list[dict]:
    """Return the owner's repos as dicts (public and private)."""
    return [
        repo
        for repo in _run_gh(
            ["repo", "list", owner, "--limit", "1000", "--json", REPO_FIELDS]
        )
        if isinstance(repo, dict)
    ]


def _topic_names(repo: dict) -> list[str]:
    """Topic names from either gh shape: ``repositoryTopics`` objects
    (repo list) or plain ``topics`` strings (REST API)."""
    names = []
    for topic in repo.get("repositoryTopics") or repo.get("topics") or []:
        if isinstance(topic, str):
            names.append(topic)
        elif isinstance(topic, dict) and topic.get("name"):
            names.append(str(topic["name"]))
    return sorted(names)


def audit_repo(repo: dict) -> dict:
    """One audit finding: the metadata fields and which are missing."""
    description = str(repo.get("description") or "")
    homepage = str(repo.get("homepageUrl") or repo.get("homepage") or "")
    topics = _topic_names(repo)
    missing = []
    if not description.strip():
        missing.append("description")
    if not topics:
        missing.append("topics")
    if not homepage.strip():
        missing.append("homepage")
    return {
        "name": str(repo.get("name") or ""),
        "description": description,
        "topics": topics,
        "homepage": homepage,
        "missing": missing,
        "gap": bool(missing),
    }


def audit(owner: str) -> list[dict]:
    """Audit findings for the owner's public repos, sorted by name."""
    findings = [
        audit_repo(repo)
        for repo in fetch_repos(owner)
        if str(repo.get("visibility") or "").lower() == "public"
    ]
    findings.sort(key=lambda finding: finding["name"])
    return findings


def render_text(findings: list[dict]) -> str:
    """PAS-compatible report: a ``total: N`` header, one line per repo."""
    lines = [f"total: {len(findings)}"]
    for finding in findings:
        marker = ""
        if finding["gap"]:
            marker = f"  <-- GAP (missing: {', '.join(finding['missing'])})"
        lines.append(
            f"{finding['name']:35} | t={len(finding['topics']):2} | "
            f"{(finding['description'] or '-')[:60]}{marker}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--owner", default=DEFAULT_OWNER,
        help="GitHub account whose public repos are audited",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the findings list as JSON instead of the text report",
    )
    parser.add_argument(
        "--out", metavar="FILE",
        help="also write the findings JSON to FILE",
    )
    args = parser.parse_args(argv)

    try:
        findings = audit(args.owner)
    except FileNotFoundError:
        print("error: gh CLI not found on PATH", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired as exc:
        print(f"error: gh timed out: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(findings, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(findings, indent=2) if args.json
        else render_text(findings)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

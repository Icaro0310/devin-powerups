#!/usr/bin/env python3
"""reconcile_registry.py — diff registry.json against GitHub and local clones.

Three sources are reconciled, read-only (registry.json is never modified):

1. ``registry.json`` entries (this repo);
2. the GitHub account's repos via ``gh repo list <owner> --limit 100 --json
   name,visibility,description,latestRelease,url`` plus a bounded
   ``gh api repos/<owner>/<repo>/tags`` per registry entry that declares
   ``version`` or ``tag``;
3. local git clones found under the ecosystem checkout roots (default:
   ``../`` and ``../../`` relative to this repo, overridable with
   ``--local-root``).

Reports repositories on GitHub missing from the registry, registry entries
missing on GitHub, visibility drift, stale version/tag fields, and registry
entries without a local clone. ``machine_id``-free: prints only repo names.

Usage:
    python tools/reconcile_registry.py [--registry registry.json]
                                       [--owner Icaro0310]
                                       [--local-root PATH ...]
                                       [--skip-tags] [--json] [--out FILE]
                                       [--fail-on-drift]

Exit codes: 0 = report produced, 1 = drift found (only with --fail-on-drift),
2 = input/tool problem (gh missing, bad JSON, ...).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent

DEFAULT_OWNER = "Icaro0310"
GH_TIMEOUT = 30
TAG_LIMIT = 100

_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _norm_version(tag: str) -> str | None:
    """Normalize 'v0.2.0'/'0.2.0' to '0.2.0'; None if not semver-shaped."""
    match = _TAG_RE.match(str(tag).strip())
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}" if match else None


def _version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))


def load_registry(path: Path) -> dict[str, dict]:
    """Return {name: entry} from registry.json, with light structural checks."""
    try:
        registry = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {path}: {exc}") from exc
    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError(f"{path}: 'repositories' must be a list")
    entries = {}
    for entry in repositories:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"{path}: repository entries must be objects with a 'name'")
        entries[entry["name"]] = entry
    return entries


def _run_gh(args: list[str]) -> list[dict] | list:
    """Run a gh command expected to print a JSON array; raise on failure."""
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=GH_TIMEOUT,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else "no stderr"
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {detail[:200]}")
    return json.loads(proc.stdout)


def fetch_github_repos(owner: str) -> dict[str, dict]:
    """Return {name: repo} for every repo of ``owner`` (public and private)."""
    repos = _run_gh(
        ["repo", "list", owner, "--limit", "100", "--json",
         "name,visibility,description,latestRelease,url,isArchived"]
    )
    return {repo["name"]: repo for repo in repos if isinstance(repo, dict)}


def fetch_github_tags(owner: str, name: str) -> list[str]:
    """Return tag names for one repo (bounded to TAG_LIMIT entries)."""
    # NB: gh api -f/-F switches the request to POST — keep params in the path.
    items = _run_gh(["api", f"repos/{owner}/{name}/tags?per_page=100"])
    return [str(item["name"]) for item in items[:TAG_LIMIT]
            if isinstance(item, dict) and item.get("name")]


def find_local_clones(roots: list[Path]) -> dict[str, Path]:
    """Return {dir-name: path} for directories containing a .git entry."""
    clones = {}
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / ".git").exists():
                clones.setdefault(child.name, child)
    return clones


def _is_repository_entry(name: str, entry: dict) -> bool:
    url_name = str(entry.get("url", "")).rstrip("/").rsplit("/", 1)[-1]
    return not (
        entry.get("kind") == "system"
        and url_name
        and url_name != name
        and not entry.get("local_dir")
    )


def reconcile(
    registry_path: Path,
    owner: str,
    local_roots: list[Path],
    fetch_tags: bool = True,
) -> dict:
    """Build the reconciliation report (pure data; no side effects)."""
    report = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "registry": str(registry_path),
            "github_owner": owner,
            "local_roots": [str(root) for root in local_roots],
        },
        "github_only": [],
        "registry_only": [],
        "stale_fields": [],
        "missing_local": [],
        "local_only": [],
        "errors": [],
    }

    registry = load_registry(registry_path)

    try:
        github = fetch_github_repos(owner)
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired,
            json.JSONDecodeError) as exc:
        report["errors"].append(f"github source unavailable: {exc}")
        github = {}

    gh_names = set(github)
    reg_names = {name for name, entry in registry.items() if _is_repository_entry(name, entry)}

    # Archived GitHub repos are deliberately retired (e.g. absorbed into
    # another repo), not drift — never report them as missing from the
    # registry.
    report["github_only"] = sorted(
        (
            {
                "name": name,
                "visibility": str(github[name].get("visibility") or "").lower(),
                "ecosystem_shaped": name.startswith("devin-"),
            }
            for name in gh_names - reg_names
            if not github[name].get("isArchived")
        ),
        key=lambda item: item["name"],
    )
    report["registry_only"] = sorted(reg_names - gh_names)

    # Field-level drift for entries present on both sides.
    for name in sorted(reg_names & gh_names):
        entry, repo = registry[name], github[name]
        gh_visibility = str(repo.get("visibility") or "").lower()
        if gh_visibility and entry.get("visibility") != gh_visibility:
            report["stale_fields"].append({
                "name": name,
                "field": "visibility",
                "registry": entry.get("visibility"),
                "github": gh_visibility,
            })

        release = (repo.get("latestRelease") or {}).get("tagName")
        release_v = _norm_version(release) if release else None
        reg_version = entry.get("version")
        if release_v and not reg_version:
            report["stale_fields"].append({
                "name": name,
                "field": "version",
                "registry": None,
                "github": release,
                "detail": "GitHub release exists but registry has no version",
            })
        elif (
            release_v
            and reg_version
            and release_v != reg_version
            and _norm_version(entry.get("tag", "")) != reg_version
        ):
            report["stale_fields"].append({
                "name": name,
                "field": "version",
                "registry": reg_version,
                "github": release,
                "detail": "GitHub latest release differs from registry version",
            })

        if not fetch_tags or (not entry.get("version") and not entry.get("tag")):
            continue
        try:
            tags = fetch_github_tags(owner, name)
        except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError) as exc:
            report["errors"].append(f"{name}: tag fetch failed: {exc}")
            continue
        if entry.get("tag") and entry["tag"] not in tags:
            report["stale_fields"].append({
                "name": name,
                "field": "tag",
                "registry": entry["tag"],
                "github": tags[:5],
                "detail": "registry tag not found among GitHub tags",
            })
        tagged_versions = [v for v in (_norm_version(t) for t in tags) if v]
        if tagged_versions and reg_version:
            newest = max(tagged_versions, key=_version_key)
            if _version_key(newest) > _version_key(reg_version):
                report["stale_fields"].append({
                    "name": name,
                    "field": "version",
                    "registry": reg_version,
                    "github": f"v{newest}",
                    "detail": "GitHub has a newer tag than the registry version",
                })

    # Local clones.
    clones = find_local_clones(local_roots)
    for name in sorted(reg_names):
        if name in clones:
            continue
        local_dir = registry[name].get("local_dir")
        # local_dir is maintained relative to the ecosystem root (the hub's
        # parent); check the hub dir too for forward compatibility.
        if local_dir and any(
            (base / local_dir).resolve().is_dir() for base in (HUB.parent, HUB)
        ):
            continue
        report["missing_local"].append(name)
    report["local_only"] = sorted(set(clones) - reg_names)

    report["summary"] = {
        "registry_entries": len(registry),
        "github_repos": len(github),
        "local_clones": len(clones),
        "github_only": len(report["github_only"]),
        "registry_only": len(report["registry_only"]),
        "stale_fields": len(report["stale_fields"]),
        "missing_local": len(report["missing_local"]),
        "local_only": len(report["local_only"]),
        "errors": len(report["errors"]),
    }
    return report


def render_text(report: dict) -> str:
    """Human-readable summary of the reconciliation report."""
    lines = [
        f"registry reconcile — {report['generated']}",
        f"  registry: {report['sources']['registry']}",
        f"  github:   owner={report['sources']['github_owner']}",
        f"  locals:   {', '.join(report['sources']['local_roots'])}",
        "",
        f"summary: {json.dumps(report['summary'])}",
        "",
    ]
    sections = (
        ("on GitHub but missing from registry", "github_only"),
        ("in registry but missing on GitHub", "registry_only"),
        ("in registry but no local clone found", "missing_local"),
        ("local clones not in registry", "local_only"),
    )
    for title, key in sections:
        items = report[key]
        lines.append(f"{title} ({len(items)}):")
        if items:
            for item in items:
                if isinstance(item, dict):
                    suffix = " [devin-*]" if item.get("ecosystem_shaped") else ""
                    lines.append(f"  - {item['name']} ({item['visibility']}){suffix}")
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append("  (none)")
    lines.append(f"stale fields ({len(report['stale_fields'])}):")
    if report["stale_fields"]:
        for item in report["stale_fields"]:
            detail = f" — {item['detail']}" if item.get("detail") else ""
            lines.append(
                f"  - {item['name']}.{item['field']}: "
                f"registry={item['registry']!r} github={item['github']!r}{detail}"
            )
    else:
        lines.append("  (none)")
    if report["errors"]:
        lines.append(f"errors ({len(report['errors'])}):")
        for error in report["errors"]:
            lines.append(f"  - {error}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", default=str(HUB / "registry.json"))
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--local-root", action="append", dest="local_roots",
                        help="root to scan for local clones (repeatable; "
                             "default: the ecosystem dir and its parent)")
    parser.add_argument("--skip-tags", action="store_true",
                        help="skip per-repo `gh api .../tags` calls")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report to stdout")
    parser.add_argument("--out", metavar="FILE",
                        help="also write the JSON report to FILE")
    parser.add_argument("--fail-on-drift", action="store_true",
                        help="exit 1 when any discrepancy is found")
    args = parser.parse_args(argv)

    local_roots = (
        [Path(p).expanduser().resolve() for p in args.local_roots]
        if args.local_roots
        else [HUB.parent, HUB.parent.parent]
    )

    try:
        report = reconcile(
            Path(args.registry),
            owner=args.owner,
            local_roots=local_roots,
            fetch_tags=not args.skip_tags,
        )
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2) if args.json else render_text(report))

    drift = (
        report["github_only"]
        or report["registry_only"]
        or report["stale_fields"]
        or report["missing_local"]
    )
    if args.fail_on_drift and drift:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

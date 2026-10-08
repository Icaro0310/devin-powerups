#!/usr/bin/env python3
"""refresh_devkit_refs.py — move devkit tool pins forward to current upstream.

For each ``devkit.tools`` entry in ``registry.json``:

* ``source == "github"``: resolve the repo's default-branch HEAD via the
  GitHub API and update ``ref``; if the repo's newest semver tag is higher than
  the recorded ``version``, bump it too.
* ``source == "pypi"``: query the PyPI JSON API for the newest released
  ``version`` and bump it when newer.

When any entry changes, ``version`` (registry counter) is incremented and
``generated`` refreshed. The manifest itself is re-exported by the
``manifest-sync`` workflow in the devin-devkit repository.

Usage:
    python tools/refresh_devkit_refs.py [--registry registry.json] [--check]

Exit codes: 0 = refreshed (or already fresh), 1 = --check found stale pins,
2 = input/tool problem.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent

_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
GH_TIMEOUT = 30
HTTP_TIMEOUT = 15


def _norm_version(tag: str) -> str | None:
    match = _TAG_RE.match(str(tag).strip())
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}" if match else None


def _version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))


def _gh_json(path: str) -> dict | list:
    proc = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, timeout=GH_TIMEOUT
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else "no stderr"
        raise RuntimeError(f"gh api {path} failed: {detail[:200]}")
    return json.loads(proc.stdout)


def _github_head(owner: str, repo: str) -> str:
    meta = _gh_json(f"repos/{owner}/{repo}")
    branch = meta.get("default_branch") or "main"
    commit = _gh_json(f"repos/{owner}/{repo}/commits/{branch}")
    sha = commit.get("sha") if isinstance(commit, dict) else None
    if not sha:
        raise RuntimeError(f"{repo}: no SHA on {branch}")
    return sha


def _github_newest_tag(owner: str, repo: str) -> str | None:
    tags = _gh_json(f"repos/{owner}/{repo}/tags?per_page=100")
    versions = [
        v for v in (_norm_version(t.get("name", "")) for t in tags if isinstance(t, dict)) if v
    ]
    return max(versions, key=_version_key) if versions else None


def _pypi_newest_version(package: str) -> str | None:
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    version = data.get("info", {}).get("version")
    return _norm_version(str(version)) if version else None


def refresh(registry_path: Path, owner: str) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    changes: list[str] = []
    errors: list[str] = []

    repo_entries = {e["name"]: e for e in registry.get("repositories", [])}

    for name, tool in registry.get("devkit", {}).get("tools", {}).items():
        newest = None
        source = tool.get("source")
        if source == "github":
            try:
                head = _github_head(owner, name)
            except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                errors.append(f"{name}: {exc}")
                continue
            if tool.get("ref") != head:
                changes.append(f"{name}.ref: {str(tool.get('ref'))[:8]} -> {head[:8]}")
                tool["ref"] = head
            try:
                newest = _github_newest_tag(owner, name)
            except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                errors.append(f"{name}: tag check failed: {exc}")
        elif source == "pypi":
            newest = _pypi_newest_version(tool.get("package", name))
        # The per-repo `version` field must track the tool's resulting
        # pin — it drifted to 0.1.0 for poordjaevin while devkit.tools
        # said 0.1.1 (devin-powerups#30). Sync the entry to the pin even
        # when the fetch failed, so the two never diverge.
        current = _norm_version(tool.get("version", ""))
        if newest is not None and (
            current is None or _version_key(newest) > _version_key(current)
        ):
            changes.append(f"{name}.version: {tool.get('version')} -> {newest}")
            tool["version"] = newest
        target = _norm_version(tool.get("version", ""))
        entry = repo_entries.get(name)
        if entry is not None and target is not None:
            entry_version = _norm_version(entry.get("version", ""))
            if entry_version is None or _version_key(target) > _version_key(entry_version):
                changes.append(
                    f"{name} (repo entry).version: {entry.get('version')} -> {target}"
                )
                entry["version"] = target

    report = {"changes": changes, "errors": errors}
    if changes:
        registry["version"] = int(registry.get("version", 0)) + 1
        registry["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        report["registry_version"] = registry["version"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path, default=HUB / "registry.json")
    parser.add_argument("--owner", default="Icaro0310")
    parser.add_argument("--check", action="store_true",
                        help="report staleness without writing the registry")
    args = parser.parse_args(argv)

    if args.check:
        before = args.registry.read_text(encoding="utf-8")
    try:
        report = refresh(args.registry, args.owner)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    for line in report["changes"]:
        print(f"updated: {line}")
    for line in report["errors"]:
        print(f"::warning::{line}", file=sys.stderr)
    if not report["changes"]:
        print("all devkit pins are current")

    if args.check:
        args.registry.write_text(before, encoding="utf-8")
        return 1 if report["changes"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

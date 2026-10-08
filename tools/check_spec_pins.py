#!/usr/bin/env python3
"""Check that consumer pins allow the latest devin-internals-spec release.

Reads each cloned repo's pyproject.toml, extracts the
``devin-internals-spec`` requirement, fetches the latest published
version from PyPI, and reports any consumer whose constraint excludes it.

Dependabot opens the actual bump PRs (every consumer has a weekly pip
schedule); this check is the hub-side alarm: it fails loudly when a pin
drifts behind a released spec version, e.g. ``>=0.3.0,<0.4.0`` still in
place after ``0.4.0`` ships.

Usage:
    python3 tools/check_spec_pins.py --root <workspace-root> [--json]
    python3 tools/check_spec_pins.py --root <root> --latest 0.4.0  # offline

Exit code is non-zero when any consumer pin excludes the latest release.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

SPEC = "devin-internals-spec"
PYPI_URL = f"https://pypi.org/pypi/{SPEC}/json"
REQ_RE = re.compile(r'devin-internals-spec\s*([<>=!~][^"\']*)?')

BOUNDS_RE = re.compile(r"(>=|<=|==|>|<|~=)\s*([0-9][0-9A-Za-z.\-]*)")


def parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split(".") if p.isdigit())


def latest_pypi_version() -> str:
    with urllib.request.urlopen(PYPI_URL, timeout=15) as resp:
        return json.load(resp)["info"]["version"]


def spec_constraint(pyproject: Path) -> str | None:
    """Return the devin-internals-spec constraint string, or None."""
    for line in pyproject.read_text().splitlines():
        if SPEC in line:
            m = REQ_RE.search(line)
            if m:
                return (m.group(1) or "").strip()
    return None


def version_allowed(constraint: str, version: str) -> bool:
    """True when `version` satisfies every bound in `constraint`."""
    v = parse_version(version)
    for op, bound_text in BOUNDS_RE.findall(constraint):
        b = parse_version(bound_text)
        width = max(len(v), len(b))
        vp, bp = v + (0,) * (width - len(v)), b + (0,) * (width - len(b))
        if op == ">=" and not vp >= bp:
            return False
        if op == ">" and not vp > bp:
            return False
        if op == "<=" and not vp <= bp:
            return False
        if op == "<" and not vp < bp:
            return False
        if op == "==" and not vp == bp:
            return False
        if op == "~=" and not (vp >= bp and vp[:1] == bp[:1]):
            return False
    return True


def public_repo_names(root: Path) -> set[str] | None:
    """Names of public registry entries, or None when no registry is found."""
    registry = root / "devin-powerups" / "registry.json"
    if not registry.is_file():
        return None
    reg = json.loads(registry.read_text())
    return {
        e["name"]
        for e in reg["repositories"]
        if e.get("visibility") == "public"
    }


def check(root: Path, latest: str) -> list[dict]:
    public = public_repo_names(root)
    results = []
    for pyproject in sorted(root.glob("*/pyproject.toml")):
        repo = pyproject.parent.name
        if public is not None and repo not in public:
            continue
        constraint = spec_constraint(pyproject)
        if constraint is None:
            continue
        ok = version_allowed(constraint, latest)
        results.append(
            {
                "repo": repo,
                "constraint": constraint or "(none)",
                "latest": latest,
                "allows_latest": ok,
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        default="..",
        help="directory containing the cloned repos (default: %(default)s)",
    )
    ap.add_argument("--latest", help="spec version to check (default: PyPI)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    latest = args.latest or latest_pypi_version()
    results = check(Path(args.root), latest)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"{SPEC} latest: {latest}")
        for r in results:
            mark = "ok" if r["allows_latest"] else "DRIFT"
            print(f"  {mark:5} {r['repo']}: '{r['constraint']}'")
    stale = [r["repo"] for r in results if not r["allows_latest"]]
    if stale:
        print(
            f"error: pins exclude {SPEC} {latest}: {stale}", file=sys.stderr
        )
        return 1
    print(f"ok: {len(results)} consumer pin(s) allow {SPEC} {latest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

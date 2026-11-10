#!/usr/bin/env python3
"""Audit ``pr-approve.yml`` callers for the ``statuses: read`` contract.

``pr-approve.yml`` (devin-powerups) is a reusable ``workflow_call`` gate.
From **v1.16** it declares ``statuses: read`` internally so the approve job
can read commit statuses (``Devin Review`` / ``devin-judge/review``) and the
``arm-auto-merge`` job can inspect check state. ``workflow_call`` caps the
called workflow's permissions by the *caller's*, so a caller job that does
not grant ``statuses: read`` is rejected at workflow startup — a silent
``startup_failure`` before any job or step runs, with no log output.

That is exactly what took down devin-state's gate: the v1.16 bump (#120)
landed without ``statuses: read`` on the caller, and every auto-approve
run failed as ``startup_failure`` (26/26) until devin-state#123 added the
grant. The website, devin-explore, devin-control and devin-internals-spec
were found in the same state by this audit.

This script walks every repo in ``registry.json`` (plus ``--extra-repo``
entries such as the personal site), finds workflows that call
``pr-approve.yml``, and fails for any caller pinned at **v1.16 or later**
whose calling job does not grant ``statuses: read``. Callers on older pins
are reported but do not fail — they are not yet exposed to the v1.16
requirement, though they must add the grant before bumping.

Run from anywhere; it resolves checkouts under ``--root`` (the directory
that contains the cloned ``devin-powerups`` workspace) the same way
``check_required_checks.py`` does.

    python3 tools/check_pr_approve_callers.py --root /path/to/workspace
    python3 tools/check_pr_approve_callers.py --root .. \
        --extra-repo Icaro0310.github.io:../site
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
USES_RE = re.compile(r"uses:\s*\S*?/pr-approve\.yml@v(\d+)\.(\d+)")
VERSION_RE = re.compile(r"pr-approve\.yml@v(\d+)\.(\d+)")
MIN_MAJOR, MIN_MINOR = 1, 16
STATUSES_READ_RE = re.compile(r"^\s*statuses:\s*read\s*$", re.MULTILINE)


def _slug(entry: dict) -> tuple[str, str] | None:
    url = entry.get("url") or ""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if m:
        return m.group(1), m.group(2)
    name = entry.get("name")
    return ("Icaro0310", name) if name else None


def registry_checkouts(root: Path) -> dict[Path, str]:
    """checkout path -> ``owner/repo`` for each distinct registry checkout.

    Several registry entries (members) share one physical checkout via
    ``local_dir`` (e.g. devin-history/devin-pm/devin-search/devin-graph all
    live under ``devin-explore``). The audit runs once per physical checkout,
    and the ``owner/repo`` used for report links is the entry whose own
    ``name`` matches the checkout basename — that is the holder repo that
    actually owns ``.github/workflows``. Falling back to the first claimant
    keeps paths with no self-named entry (e.g. ``../qwenpaw-suite``) covered.
    """
    registry = HUB / "registry.json"
    if not registry.is_file():
        registry = root / "devin-powerups" / "registry.json"
    if not registry.is_file():
        return {}
    reg = json.loads(registry.read_text())
    out: dict[Path, str] = {}
    for e in reg["repositories"]:
        slug = _slug(e)
        if not slug:
            continue
        path = (root / (e.get("local_dir") or e["name"])).resolve()
        owner_repo = f"{slug[0]}/{slug[1]}"
        # a self-named entry (name == checkout dir) is the authoritative owner
        if path.name == e["name"] or path not in out:
            out[path] = owner_repo
    return out


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _top_level_permissions(lines: list[str], jobs_idx: int) -> str:
    """Text of the workflow-level ``permissions:`` block (before ``jobs:``)."""
    start = None
    for i, line in enumerate(lines[:jobs_idx]):
        if re.match(r"^permissions:\s*$", line):
            start = i
            break
    if start is None:
        return ""
    block = []
    for line in lines[start + 1 : jobs_idx]:
        if line.strip() and _indent(line) == 0:
            break
        block.append(line)
    return "\n".join(block)


def _job_block(lines: list[str], job_idx: int) -> tuple[int, int]:
    """(start, end) line range of the job that contains line ``job_idx``.

    Jobs live under ``jobs:`` at two-space indent; a job block runs from its
    ``  <id>:`` line to the next same-indent key or a dedented top-level key.
    """
    # find the jobs: line
    jobs_idx = next(
        (i for i, l in enumerate(lines) if re.match(r"^jobs:\s*$", l)), len(lines)
    )
    # walk back to the enclosing ``  <job_id>:`` header
    start = job_idx
    while start > jobs_idx and not re.match(r"^  \S[^:]*:\s*$", lines[start]):
        start -= 1
    # walk forward to the next job header or end of jobs block
    end = len(lines)
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if l.strip() == "" :
            continue
        if re.match(r"^  \S[^:]*:\s*$", l):  # next job header
            end = i
            break
        if _indent(l) == 0 and not l.lstrip().startswith("#"):
            end = i  # dedented top-level key ends the jobs block
            break
    return start, end


def _job_permissions(lines: list[str], uses_lineno: int) -> str:
    """Effective ``permissions:`` text for the job containing ``uses_lineno``.

    A job-level ``permissions:`` block replaces the workflow-level one for
    that job entirely; only when the job declares none does the top-level
    block apply. We return the job block when present, else the top-level.
    """
    start, end = _job_block(lines, uses_lineno)
    block = lines[start:end]
    # locate a ``permissions:`` key inside this job block (indent > job header)
    job_indent = _indent(lines[start])
    for i, line in enumerate(block):
        if re.match(r"^\s*permissions:\s*$", line) and _indent(line) > job_indent:
            # collect the block body (deeper indent than the permissions key)
            pindent = _indent(line)
            body = []
            for l in block[i + 1 :]:
                if l.strip() and _indent(l) <= pindent:
                    break
                body.append(l)
            return "\n".join(body)
    # no job-level permissions -> workflow-level applies
    return _top_level_permissions(lines, _jobs_index(lines))


def _jobs_index(lines: list[str]) -> int:
    return next(
        (i for i, l in enumerate(lines) if re.match(r"^jobs:\s*$", l)), len(lines)
    )


def audit_workflow(path: Path) -> list[dict]:
    """Return one finding per pr-approve caller in ``path`` that needs a grant.

    Each finding: {version, needs_statuses_read, ok, detail}.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    findings = []
    for i, line in enumerate(lines):
        m = USES_RE.search(line)
        if not m:
            continue
        major, minor = int(m.group(1)), int(m.group(2))
        gated = (major, minor) >= (MIN_MAJOR, MIN_MINOR)
        perms = _job_permissions(lines, i)
        has_statuses = STATUSES_READ_RE.search(perms) is not None
        findings.append(
            {
                "line": i + 1,
                "version": f"v{major}.{minor}",
                "gated": gated,
                "has_statuses_read": has_statuses,
                "ok": (not gated) or has_statuses,
            }
        )
    return findings


def iter_workflows(repo_dir: Path):
    wf_dir = repo_dir / ".github" / "workflows"
    if not wf_dir.is_dir():
        return
    for p in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="workspace root containing devin-powerups + cloned repos",
    )
    ap.add_argument(
        "--extra-repo",
        action="append",
        default=[],
        metavar="OWNER/REPO:PATH",
        help="additional repo to audit (repeatable), e.g. Icaro0310.github.io:../site",
    )
    args = ap.parse_args()
    root = args.root.resolve()

    checkouts = registry_checkouts(root)  # path -> owner/repo
    for spec in args.extra_repo:
        slug, _, rel = spec.partition(":")
        checkouts[(root / rel).resolve()] = slug

    failures: list[str] = []
    warnings: list[str] = []
    scanned = 0
    for repo_dir, owner_repo in sorted(checkouts.items(), key=lambda kv: str(kv[0])):
        if not repo_dir.is_dir():
            continue
        for wf in iter_workflows(repo_dir):
            scanned += 1
            for f in audit_workflow(wf):
                link = (
                    f"https://github.com/{owner_repo}/blob/HEAD/"
                    f".github/workflows/{wf.name}"
                )
                tag = f"{owner_repo} {wf.name}:{f['line']} -> pr-approve@{f['version']}"
                if not f["gated"]:
                    warnings.append(f"note: {tag} (pre-v1.16, add statuses:read before bump) {link}")
                elif not f["has_statuses_read"]:
                    failures.append(
                        f"FAIL: {tag} missing statuses:read -> startup_failure risk {link}"
                    )
                else:
                    pass  # ok

    for w in warnings:
        print(f"::warning::{w}")
    for f_ in failures:
        print(f"::error::{f_}")
    print(
        f"pr-approve callers audit: {scanned} workflow files scanned, "
        f"{len(failures)} failing, {len(warnings)} pre-v1.16 notes"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

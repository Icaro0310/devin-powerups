#!/usr/bin/env python3
"""Detect required status-check contexts that no check run can produce.

Branch protection is invisible until it bites: a renamed job leaves the
required context behind as a ghost — a PR shows every check green yet
stays ``mergeable_state: blocked`` forever. Hit three times in this
ecosystem: required ``secrets-scan`` while the real run reported
``secrets-scan / secrets-scan`` (reusable-call naming) in 13 repos on
2026-10-08, again in devin-devkit on 2026-10-09, plus the earlier
scorecard context drift. Wired into ``registry-drift.yml`` so the next
rename is caught before it blocks a merge.

Three legs per audited repo — all public-data endpoints, so a plain
``GITHUB_TOKEN`` suffices and no admin scope is needed:

1. **required contexts** — ``GET /repos/{o}/{r}/branches/{default}``
   exposes ``protection.required_status_checks.contexts`` (and
   ``.checks[].context``) on public repos; ``active`` rulesets add the
   ``required_status_checks`` rule contexts that target the default
   branch (``~ALL`` / ``~DEFAULT_BRANCH`` / explicit ref).
2. **observed names** — ``check-runs`` plus commit ``status`` contexts
   on the default-branch head and on the head SHAs of the last ``--prs``
   pull requests (pull_request-only jobs never run on the default head).
3. **declared contexts** — statically parsed from the local checkout's
   ``.github/workflows/*.yml``: a job produces ``name:`` or its job id;
   a job-level ``uses:`` (reusable call) produces ``<caller> / <job>``
   for every job in the called file when it resolves locally (``./`` or
   an ecosystem repo under ``--root``), else the wildcard
   ``<caller> / *``. ``${{ expr }}`` inside a name becomes ``.*``.
   Bare job names only count when the file triggers its own runs — a
   ``workflow_call``-only file's jobs exist solely as the inner half of
   ``caller / callee`` names (declaring them bare would mask exactly the
   rename-class orphan this tool exists to catch).

A required context with no producer in either leg is an orphan and fails
the check. The tool also verifies
``actions/permissions/workflow.can_approve_pull_request_reviews`` — the
same drift class (hit qwenpaw-suite, Icaro0310.github.io, Icaro0310).
That endpoint is auth-gated, so an unreadable value is a warning, never
a verdict.

Usage:
    python3 tools/check_required_checks.py [--root DIR] [--prs N] [--json]
    python3 tools/check_required_checks.py --repo devin-devkit \
        --repo Icaro0310.github.io:../site
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
OWNER = "Icaro0310"

# A workflow job name containing a GitHub expression reports check runs
# with the expression evaluated per matrix leg (`Analyze (python)` from
# `Analyze (${{ matrix.language }})`) — the literal parts anchor a regex.
EXPR_RE = re.compile(r"\$\{\{.*?\}\}")
KEY_RE = re.compile(r"^\s*(?:-\s*)?['\"]?([\w.-]+)['\"]?\s*:")
REUSABLE_RE = re.compile(r"^([^/]+)/([^/]+)/(\.github/workflows/\S+)$")


def _standalone(path: Path) -> bool:
    """True when the workflow's `on:` triggers runs of its own.

    A `workflow_call`-only file is a reusable interface: its jobs never
    produce bare check-run names here, only ``<caller> / <job>`` under a
    calling job. Every other trigger (push, pull_request, schedule,
    workflow_dispatch, ...) runs the file itself, so the bare job names
    are produced contexts. A missing/unparseable `on:` keeps the jobs
    declared — under-declaring would hide real orphans.
    """
    events: set[str] | None = None
    child_indent: int | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if events is None:
            if indent != 0:
                continue
            m = KEY_RE.match(stripped)
            if m is None or m.group(1) != "on":
                continue
            inline = stripped[m.end():].strip()
            if inline:
                # `on: push` / `on: [push, pull_request]` / flow mapping —
                # word tokens are the event names in any of these forms.
                events = set(re.findall(r"[A-Za-z_]+", inline))
            else:
                events = set()
            continue
        if indent == 0:
            break  # next top-level key ends the on: block
        # Only first-level children of `on:` are events — deeper keys are
        # per-event config (`workflow_call: inputs: package-dir:` must not
        # count as an event or a call-only file would read as standalone).
        if child_indent is None:
            child_indent = indent
        if indent == child_indent:
            m = KEY_RE.match(stripped)
            if m:
                events.add(m.group(1))
    if not events:
        return True
    return bool(events - {"workflow_call"})


def gh_api(path: str, errors: list[str]) -> dict | list:
    try:
        out = subprocess.run(
            ["gh", "api", path], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        errors.append(f"gh api {path}: {exc}")
        return {}
    if out.returncode != 0:
        errors.append(f"gh api {path}: {out.stderr.strip()[:160]}")
        return {}
    try:
        return json.loads(out.stdout or "{}")
    except json.JSONDecodeError as exc:
        errors.append(f"gh api {path}: bad JSON ({exc})")
        return {}


# ---------------------------------------------------------------------------
# Leg 3 — declared contexts (local checkout parse)
# ---------------------------------------------------------------------------

def parse_jobs(path: Path) -> dict[str, dict[str, str | None]]:
    """Minimal YAML-subset scan: {job_id: {"name": ..., "uses": ...}}.

    Only the two job-level keys required-context naming needs are read.
    Job ids are the first-level children of the top-level ``jobs:`` key;
    ``name:``/``uses:`` are accepted only at the job's own child indent —
    a ``uses:`` inside ``steps:`` is deeper and a ``name:`` inside
    ``strategy.matrix`` never aligns with the job level either.
    """
    jobs: dict[str, dict[str, str | None]] = {}
    jobs_indent = job_indent = field_indent = None
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if jobs_indent is None:
            if indent == 0 and re.match(r"jobs\s*:", stripped):
                jobs_indent = indent
            continue
        if indent <= jobs_indent:
            break  # next top-level key ends the jobs block
        if job_indent is None:
            job_indent = indent
        if indent == job_indent:
            m = KEY_RE.match(stripped)
            if m is None or stripped.startswith("- "):
                continue
            current = m.group(1).strip("'\"")
            jobs[current] = {"name": None, "uses": None}
            field_indent = None
            continue
        if current is None:
            continue
        if field_indent is None:
            field_indent = indent
        if indent != field_indent:
            continue
        m = KEY_RE.match(stripped)
        if m is None:
            continue
        key = m.group(1)
        if key not in ("name", "uses"):
            continue
        value = stripped[m.end():].strip().split(" #", 1)[0].strip().strip("'\"")
        if jobs[current][key] is None:
            jobs[current][key] = value
    return jobs


def _slug(entry: dict) -> tuple[str, str] | None:
    """(owner, repo) from an entry's `url`, falling back to OWNER/name."""
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", entry.get("url") or "")
    if m:
        return m.group(1), m.group(2)
    if entry.get("name"):
        return OWNER, entry["name"]
    return None


def registry_dirs(root: Path) -> dict[str, Path]:
    """owner/repo (lowercase) -> local checkout for every registry entry."""
    registry = HUB / "registry.json"
    if not registry.is_file():
        registry = root / "devin-powerups" / "registry.json"
    if not registry.is_file():
        return {}
    reg = json.loads(registry.read_text())
    dirs = {}
    for e in reg["repositories"]:
        slug = _slug(e)
        if slug:
            dirs[f"{slug[0]}/{slug[1]}".lower()] = (
                root / (e.get("local_dir") or e["name"])
            ).resolve()
    return dirs


def resolve_called_workflow(
    uses: str, repo_dir: Path, dirs: dict[str, Path]
) -> Path | None:
    """Resolve a job-level `uses:` to a local workflow file, or None."""
    target = uses.split("@", 1)[0].strip()
    if target.startswith("./"):
        return (repo_dir / target[2:]).resolve()
    m = REUSABLE_RE.match(target)
    if m:
        checkout = dirs.get(f"{m.group(1)}/{m.group(2)}".lower())
        if checkout:
            return (checkout / m.group(3)).resolve()
    return None


def _add_context(value: str, exact: set[str], patterns: list[str]) -> None:
    if "${{" in value:
        patterns.append(
            "^" + ".*".join(re.escape(p) for p in EXPR_RE.split(value)) + "$"
        )
    else:
        exact.add(value)


def declared_contexts(
    repo_dir: Path, dirs: dict[str, Path]
) -> tuple[set[str], list[str]]:
    """Check-run contexts this repo's workflows can produce.

    Returns (exact names, regex patterns). Reusable-call jobs produce
    ``<caller name|id> / <callee job name|id>`` — one extra level only,
    matching GitHub's actual naming (`fanout / publish-pypi`, never
    three-deep). An unresolvable callee yields the ``<caller> / *``
    wildcard so a foreign reusable still covers its contexts.
    """
    exact: set[str] = set()
    patterns: list[str] = []
    wf_dir = repo_dir / ".github" / "workflows"
    if not wf_dir.is_dir():
        return exact, patterns
    workflows = sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml"))
    for wf in workflows:
        standalone = _standalone(wf)
        for job_id, meta in parse_jobs(wf).items():
            display = meta["name"] or job_id
            uses = meta["uses"]
            if uses:
                called = resolve_called_workflow(uses, repo_dir, dirs)
                if called is not None and called.is_file():
                    for inner_id, inner in parse_jobs(called).items():
                        inner_display = inner["name"] or inner_id
                        _add_context(f"{display} / {inner_display}", exact, patterns)
                else:
                    exact.add(f"{display} / *")
            elif standalone:
                _add_context(display, exact, patterns)
    return exact, patterns


def covered(
    context: str, observed: set[str], exact: set[str], patterns: list[str]
) -> bool:
    if context in observed or context in exact:
        return True
    for d in exact:
        if d.endswith(" / *") and context.startswith(d[:-1]):
            return True
    return any(re.fullmatch(p, context) for p in patterns)


# ---------------------------------------------------------------------------
# Legs 1+2 — required and observed contexts (gh api)
# ---------------------------------------------------------------------------

def _rsc_contexts(rsc: dict) -> set[str]:
    """Contexts from a required_status_checks block (classic or ruleset)."""
    out = set(rsc.get("contexts") or [])
    for c in rsc.get("checks") or []:
        if c.get("context"):
            out.add(c["context"])
    return out


def ruleset_contexts(
    owner: str, repo: str, default_branch: str, errors: list[str]
) -> set[str]:
    """Required contexts from `active` rulesets targeting the default branch."""
    out: set[str] = set()
    listing = gh_api(
        f"repos/{owner}/{repo}/rulesets?includes_parents=true", errors
    )
    if not isinstance(listing, list):
        return out
    for rs in listing:
        rid = rs.get("id")
        if rid is None:
            continue
        detail = gh_api(f"repos/{owner}/{repo}/rulesets/{rid}", errors)
        if not isinstance(detail, dict) or not detail:
            continue
        # `evaluate`/`disabled` do not gate merges — only active rulesets
        # can hold a merge-blocking required context.
        if detail.get("enforcement") != "active":
            continue
        ref = (detail.get("conditions") or {}).get("ref_name") or {}
        include = ref.get("include") or []
        exclude = ref.get("exclude") or []
        targets_default = (
            not include
            or "~ALL" in include
            or "~DEFAULT_BRANCH" in include
            or f"refs/heads/{default_branch}" in include
        )
        if not targets_default:
            continue
        if "~ALL" in exclude or "~DEFAULT_BRANCH" in exclude or (
            f"refs/heads/{default_branch}" in exclude
        ):
            continue
        for rule in detail.get("rules") or []:
            if rule.get("type") != "required_status_checks":
                continue
            params = rule.get("parameters") or {}
            out |= _rsc_contexts(
                {"contexts": [c.get("context")
                              for c in params.get("required_status_checks") or []]}
            )
    return {c for c in out if c}


def collect_repo(owner: str, repo: str, prs: int) -> dict:
    """Fetch the API legs for one repo: required + observed contexts.

    Every endpoint is public data for a public repo, so failures land in
    ``errors`` — a repo whose state cannot be read is an audit failure,
    never silently clean.
    """
    errors: list[str] = []
    notes: list[str] = []
    meta = gh_api(f"repos/{owner}/{repo}", errors)
    result: dict = {
        "repo": repo,
        "required": [],
        "orphans": [],
        "can_approve": None,
        "errors": errors,
        "notes": notes,
    }
    if not meta:
        return result
    if meta.get("archived"):
        notes.append("archived — skipped")
        result["skipped"] = True
        return result
    default = meta.get("default_branch") or "main"

    branch = gh_api(f"repos/{owner}/{repo}/branches/{default}", errors)
    required: set[str] = set()
    if branch.get("protected"):
        rsc = (branch.get("protection") or {}).get("required_status_checks") or {}
        required |= _rsc_contexts(rsc)
        if not rsc:
            # Public repos normally expose the block on the branch
            # endpoint; fall back to the admin endpoint before concluding
            # there are no classic required contexts.
            prot = gh_api(
                f"repos/{owner}/{repo}/branches/{default}/protection", errors
            )
            if prot:
                required |= _rsc_contexts(prot.get("required_status_checks") or {})
    elif branch:
        notes.append("no branch protection on default branch")
    required |= ruleset_contexts(owner, repo, default, errors)
    result["required"] = sorted(required)

    observed: set[str] = set()

    def add_commit_contexts(sha: str) -> None:
        runs = gh_api(
            f"repos/{owner}/{repo}/commits/{sha}/check-runs?per_page=100",
            errors,
        )
        for r in (runs or {}).get("check_runs") or []:
            if r.get("name"):
                observed.add(r["name"])
        status = gh_api(f"repos/{owner}/{repo}/commits/{sha}/status", errors)
        for s in (status or {}).get("statuses") or []:
            if s.get("context"):
                observed.add(s["context"])

    add_commit_contexts(default)
    if prs > 0:
        pulls = gh_api(
            f"repos/{owner}/{repo}/pulls?state=all&per_page={prs}"
            "&sort=updated&direction=desc",
            errors,
        )
        for pr in pulls if isinstance(pulls, list) else []:
            sha = (pr.get("head") or {}).get("sha")
            if sha:
                add_commit_contexts(sha)
    result["observed_names"] = sorted(observed)

    # Secondary signal, and the only endpoint here that is auth-gated on
    # public repos: unreadable under a foreign-repo token is a note, not
    # an audit error — only an explicit `false` is a finding.
    perm_errors: list[str] = []
    perm = gh_api(
        f"repos/{owner}/{repo}/actions/permissions/workflow", perm_errors
    )
    if isinstance(perm, dict) and "can_approve_pull_request_reviews" in perm:
        result["can_approve"] = bool(perm["can_approve_pull_request_reviews"])
    elif perm_errors:
        notes.append(
            f"can_approve_pull_request_reviews unreadable: {perm_errors[0]}"
        )
    return result


def audit_repo(
    owner: str,
    repo: str,
    repo_dir: Path | None,
    dirs: dict[str, Path],
    prs: int,
) -> dict:
    result = collect_repo(owner, repo, prs)
    if result.get("skipped") or not result["required"]:
        return result
    observed = set(result.get("observed_names") or [])
    exact: set[str] = set()
    patterns: list[str] = []
    if repo_dir is not None and repo_dir.is_dir():
        exact, patterns = declared_contexts(repo_dir, dirs)
    else:
        result["notes"].append("no local checkout — declared-context leg skipped")
    result["orphans"] = [
        c for c in result["required"] if not covered(c, observed, exact, patterns)
    ]
    return result


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def registry_repos(root: Path) -> list[tuple[str, str, Path]]:
    """Unique (owner, repo, local checkout) per public registry entry.

    Registry rows are product-level: absorbed packages (devin-history,
    devin-pm, ...) keep their product name but their `url` points at the
    monorepo that now hosts them. Auditing `name` would 404 dead repos
    and repeat monorepos, so the repo slug comes from `url` and dupes
    collapse to one target.
    """
    registry = HUB / "registry.json"
    if not registry.is_file():
        registry = root / "devin-powerups" / "registry.json"
    if not registry.is_file():
        return []
    reg = json.loads(registry.read_text())
    out: list[tuple[str, str, Path]] = []
    seen: set[str] = set()
    for e in reg["repositories"]:
        if e.get("visibility") != "public":
            continue
        slug = _slug(e)
        if slug is None:
            continue
        key = f"{slug[0]}/{slug[1]}".lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            (slug[0], slug[1],
             (root / (e.get("local_dir") or e["name"])).resolve())
        )
    return out


def parse_repo_spec(spec: str, root: Path) -> tuple[str, str, Path]:
    """`NAME[:DIR]` or `OWNER/NAME[:DIR]`; DIR resolves against --root."""
    name, _, local = spec.partition(":")
    owner = OWNER
    if "/" in name:
        owner, name = name.split("/", 1)
    repo_dir = (root / local).resolve() if local else (root / name).resolve()
    return owner, name, repo_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=HUB.parent,
        help="ecosystem root; local_dir paths resolve against it "
        "(default: %(default)s)",
    )
    ap.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="NAME[:DIR]",
        help="audit this repo instead of the registry (repeatable; "
        "accepts OWNER/NAME and a :LOCAL_DIR override under --root)",
    )
    ap.add_argument(
        "--extra-repo",
        action="append",
        default=[],
        metavar="NAME[:DIR]",
        help="audit this repo in addition to the registry set "
        "(repeatable; same spec as --repo) — for repos outside the "
        "registry like Icaro0310/Icaro0310.github.io that carry the "
        "same drift class",
    )
    ap.add_argument(
        "--prs",
        type=int,
        default=5,
        help="scan check-runs on the heads of the last N PRs too — "
        "pull_request-only jobs never run on the default branch "
        "(default: %(default)s)",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    if args.repo:
        targets = [parse_repo_spec(s, root) for s in args.repo]
    else:
        targets = registry_repos(root)
    targets += [parse_repo_spec(s, root) for s in args.extra_repo]
    dirs = registry_dirs(root)
    if not targets:
        print(
            "error: nothing to audit — no --repo given and no public "
            "registry entries found",
            file=sys.stderr,
        )
        return 2

    results = []
    for owner, name, repo_dir in targets:
        results.append(audit_repo(owner, name, repo_dir, dirs, args.prs))

    orphan_map = {r["repo"]: r["orphans"] for r in results if r["orphans"]}
    flag_map = {
        r["repo"]: r["can_approve"]
        for r in results
        if r.get("can_approve") is False
    }
    error_map = {r["repo"]: r["errors"] for r in results if r["errors"]}

    if args.json:
        print(
            json.dumps(
                {
                    "repos": results,
                    "orphans": orphan_map,
                    "can_approve_false": sorted(flag_map),
                    "errors": error_map,
                },
                indent=2,
            )
        )
    else:
        print(f"required-checks audit — {len(results)} repo(s)")
        for r in results:
            if r["errors"]:
                print(f"  ERROR   {r['repo']}: {'; '.join(r['errors'])}")
                continue
            if r.get("skipped"):
                print(f"  SKIP    {r['repo']}: {'; '.join(r['notes'])}")
                continue
            for orphan in r["orphans"]:
                print(
                    f"  ORPHAN  {r['repo']}: required '{orphan}' has no "
                    "producer — no observed check-run, no declared job"
                )
            if r.get("can_approve") is False:
                print(
                    f"  FLAG    {r['repo']}: can_approve_pull_request_reviews"
                    " is false — Actions cannot approve PRs"
                )
            for note in r["notes"]:
                print(f"  note    {r['repo']}: {note}")
            if not r["orphans"] and r.get("can_approve") is not False:
                if r["required"]:
                    print(
                        f"  ok      {r['repo']}: {len(r['required'])} required "
                        f"context(s), all produced"
                    )
                else:
                    print(f"  ok      {r['repo']}: no required contexts")

    findings = len(orphan_map) + len(flag_map) + len(error_map)
    if findings:
        if not args.json:
            print(
                f"error: {len(orphan_map)} repo(s) with orphaned required "
                f"contexts, {len(flag_map)} with can_approve=false, "
                f"{len(error_map)} with audit errors",
                file=sys.stderr,
            )
        # Every repo failing means the audit itself ran on nothing —
        # gh missing/auth broken — distinct from real findings.
        if len(error_map) == len(results):
            return 2
        return 1
    if not args.json:
        print(f"ok: no orphaned required checks across {len(results)} repo(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

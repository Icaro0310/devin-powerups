"""Tests for check_pr_approve_callers.py — pure filesystem, no live API.

Pins the statuses:read caller contract introduced by pr-approve v1.15:
a caller job that omits the grant is rejected at reusable-workflow
startup (silent ``startup_failure``), so the audit must flag it before
the bump ships. The load-bearing case is a job-level ``permissions:``
block that drops ``statuses: read`` even when the workflow-level block
has it — job permissions replace the top-level ones wholesale.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_pr_approve_callers as audit  # noqa: E402


def write_wf(tmp_path: Path, name: str, body: str) -> Path:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    p = wf / name
    p.write_text(body)
    return p


def single(tmp_path: Path, body: str, name: str = "auto-approve.yml") -> dict:
    wf = write_wf(tmp_path, name, body)
    findings = audit.audit_workflow(wf)
    assert len(findings) == 1
    return findings[0]


HEADER = """name: auto-approve
on:
  pull_request_target: {}
permissions:
  contents: write
  pull-requests: write
jobs:
  approve:
"""


def test_v16_job_grant_is_ok(tmp_path):
    body = (
        HEADER
        + """    permissions:
      contents: write
      pull-requests: write
      statuses: read
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_v16_missing_job_grant_fails(tmp_path):
    """The devin-state#123 / website#53 shape: job permissions list
    contents+pull-requests but not statuses -> startup_failure risk."""
    body = (
        HEADER
        + """    permissions:
      contents: write
      pull-requests: write
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and not f["has_statuses_read"] and not f["ok"]


def test_v16_top_level_grant_does_not_save_job_override(tmp_path):
    """Job-level ``permissions:`` replaces top-level wholesale: a top-level
    ``statuses: read`` does NOT rescue a job that omits it."""
    body = (
        """name: auto-approve
on:
  pull_request_target: {}
permissions:
  contents: write
  pull-requests: write
  statuses: read
jobs:
  approve:
    permissions:
      contents: write
      pull-requests: write
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and not f["has_statuses_read"] and not f["ok"]


def test_v16_no_job_permissions_inherits_top_level(tmp_path):
    """A job with no ``permissions:`` block inherits the workflow-level
    grant, so top-level ``statuses: read`` is sufficient."""
    body = (
        """name: auto-approve
on:
  pull_request_target: {}
permissions:
  contents: write
  pull-requests: write
  statuses: read
jobs:
  approve:
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_v16_job_grant_without_top_level_is_ok(tmp_path):
    body = (
        """name: auto-approve
on:
  pull_request_target: {}
permissions:
  contents: write
jobs:
  approve:
    permissions:
      contents: write
      pull-requests: write
      statuses: read
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_v14_missing_grant_is_not_gated(tmp_path):
    """Pre-v1.15 pins predate the statuses:read requirement: reported as a
    note, never a failure — they are not yet exposed to the break."""
    body = HEADER + (
        "    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.14\n"
    )
    f = single(tmp_path, body)
    assert not f["gated"] and f["ok"]


def test_v15_missing_grant_is_gated(tmp_path):
    """v1.15 already declares statuses:read (D-2026-11-09): a caller
    without the grant hits the same startup cap as v1.16."""
    body = HEADER + (
        "    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.15\n"
    )
    f = single(tmp_path, body)
    assert f["gated"] and not f["has_statuses_read"] and not f["ok"]


def test_v15_with_grant_is_ok(tmp_path):
    body = HEADER + (
        """    permissions:
      contents: write
      pull-requests: write
      statuses: read
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.15
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_statuses_write_counts_as_read(tmp_path):
    """``statuses: write`` implies read — must not false-positive."""
    body = HEADER + (
        """    permissions:
      contents: write
      pull-requests: write
      statuses: write
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_read_all_scalar_counts_as_read(tmp_path):
    """``permissions: read-all`` grants statuses read at job level."""
    body = (
        """name: auto-approve
on:
  pull_request_target: {}
permissions:
  contents: write
jobs:
  approve:
    permissions: read-all
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_trailing_comment_after_statuses_read(tmp_path):
    """``statuses: read  # note`` is still a grant."""
    body = HEADER + (
        """    permissions:
      contents: write
      pull-requests: write
      statuses: read  # needed by the judge gate
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_inline_job_permissions_map_drops_statuses(tmp_path):
    """A flow-map ``permissions: {contents: read}`` on the job replaces the
    top-level block — top-level ``statuses: read`` does NOT rescue it."""
    body = (
        """name: auto-approve
on:
  pull_request_target: {}
permissions:
  contents: write
  pull-requests: write
  statuses: read
jobs:
  approve:
    permissions: {contents: read, pull-requests: write}
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and not f["has_statuses_read"] and not f["ok"]


def test_inline_job_permissions_map_with_statuses_ok(tmp_path):
    body = HEADER + (
        """    permissions: {contents: write, pull-requests: write, statuses: read}
    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16
"""
    )
    f = single(tmp_path, body)
    assert f["gated"] and f["has_statuses_read"] and f["ok"]


def test_commented_uses_line_ignored(tmp_path):
    """A ``# uses:`` comment is not an active call — no finding at all."""
    body = HEADER + (
        "    # uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.16\n"
        "    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.14\n"
    )
    wf = write_wf(tmp_path, "auto-approve.yml", body)
    findings = audit.audit_workflow(wf)
    assert len(findings) == 1
    assert findings[0]["version"] == "v1.14" and not findings[0]["gated"]


def test_v17_missing_grant_still_gated(tmp_path):
    """The gate applies to v1.16 AND later — a future v1.17 bump without
    the grant must fail here too."""
    body = HEADER + (
        "    uses: Icaro0310/devin-powerups/.github/workflows/pr-approve.yml@v1.17\n"
    )
    f = single(tmp_path, body)
    assert f["gated"] and not f["has_statuses_read"] and not f["ok"]


def test_non_pr_approve_workflow_ignored(tmp_path):
    body = HEADER + (
        "    uses: Icaro0310/devin-powerups/.github/workflows/other.yml@v1.16\n"
    )
    wf = write_wf(tmp_path, "other.yml", body)
    assert audit.audit_workflow(wf) == []


def test_iter_workflows_finds_caller(tmp_path):
    write_wf(tmp_path, "auto-approve.yml", HEADER + "    uses: x\n")
    write_wf(tmp_path, "ci.yaml", "name: ci\non: push\njobs: {}\n")
    names = sorted(p.name for p in audit.iter_workflows(tmp_path))
    assert names == ["auto-approve.yml", "ci.yaml"]


def test_registry_checkouts_maps_physical_paths(tmp_path):
    """registry_checkouts resolves each distinct checkout path to the
    holder owner/repo, deduplicating members that share a local_dir."""
    import json

    hub = Path(audit.__file__).resolve().parent.parent
    reg = hub / "registry.json"
    if not reg.is_file():
        return  # running outside a full checkout — nothing to assert
    data = json.loads(reg.read_text())
    checkouts = audit.registry_checkouts(tmp_path)
    # every registry entry's checkout must be represented exactly once per path
    seen_paths = set()
    for entry in data["repositories"]:
        slug = audit._slug(entry)
        if not slug:
            continue
        path = (tmp_path / (entry.get("local_dir") or entry["name"])).resolve()
        seen_paths.add(path)
        # the holder repo (name == checkout basename) owns the path when present
        assert path in checkouts
        owner_repo = checkouts[path]
        assert owner_repo.startswith("Icaro0310/")
    # member entries sharing a local_dir collapse to a single physical path
    assert len(checkouts) == len(seen_paths)

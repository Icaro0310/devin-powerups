"""Static regression tests for the AI review fallback workflows.

These pin the security boundaries as executable assertions: SHA-pinned
actions only, no Devin-context spoofing, no PR-head checkout in jobs
that carry Tailscale credentials, and the pr-approve evidence rules.
Stdlib only — the tools suite installs pytest alone.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
TEXT = (WF / "ai-review-fallback.yml").read_text()
APPROVE = (WF / "pr-approve.yml").read_text()
SHA40 = re.compile(r"^[a-f0-9]{40}$")


def _job_block(name: str) -> str:
    m = re.search(rf"\n  {name}:\n(.*?)(?=\n  \w|\Z)", TEXT, re.S)
    return m.group(1) if m else ""


def test_every_action_pinned_to_full_sha():
    uses = re.findall(r"uses: ([^\s@]+)@([^\s]+)", TEXT)
    assert uses, "no actions found"
    for name, ref in uses:
        assert SHA40.match(ref), f"{name}@{ref} is not a full SHA pin"


def test_fallback_never_posts_devin_context():
    assert "context=Devin Review" not in TEXT
    assert '"Review Coverage"' in TEXT


def test_fallback_runs_on_pull_request_target():
    assert "pull_request_target:" in TEXT


def test_no_checkout_of_pr_head():
    """Jobs carrying tailnet creds must never materialize PR-controlled
    code: no actions/checkout may pin the PR head ref."""
    for m in re.finditer(r"uses: actions/checkout@[a-f0-9]{40}(.*?)(?=\n      - |\Z)",
                         TEXT, re.S):
        assert "head" not in m.group(1), f"checkout references PR head: {m.group(1)}"


def test_fallback_jobs_gate_on_classifier():
    for name in ("review-a", "review-b"):
        block = _job_block(name)
        needs_line = next(l for l in block.splitlines() if "needs:" in l)
        assert "classify" in needs_line, needs_line
        assert "EXECUTED" in block


def test_review_b_runs_parallel_to_review_a():
    """Lane B is deterministic static analysis on the runner — no shared
    Ollama slot exists anymore, so it must NOT serialize behind A;
    always() keeps its own outcome honest when classify flaked."""
    block = _job_block("review-b")
    needs_line = next(l for l in block.splitlines() if "needs:" in l)
    assert "review-a" not in needs_line, needs_line
    assert "always()" in block


def test_coverage_runs_always_and_posts_own_status():
    block = _job_block("coverage")
    assert "always()" in block
    assert "statuses: write" in block
    assert "checks: write" in block  # the check run is the source of truth
    assert "publish-review-coverage.py" in block


def test_pr_approve_reads_coverage_check_run_not_status_mirror():
    """v1.9: the gate must read the check run (Checks API, where
    action_required exists) — never the mirrored commit status, which
    cannot express degraded coverage honestly."""
    assert "check-runs?check_name=Review%20Coverage" in APPROVE
    # coverage evidence is never drawn from the status mirror anymore
    assert '.statuses[] | select(.context == "Review Coverage"' not in APPROVE


def test_tailscale_jobs_have_id_token_write_only_where_needed():
    # Lane B is static analysis on the runner — no tailnet, no id-token.
    assert "id-token: write" in _job_block("review-a")
    assert "id-token" not in _job_block("review-b")
    assert "id-token" not in _job_block("coverage")


def test_pr_approve_requires_completed_analysis_not_bare_success():
    """The false-success hole: a credit-exhausted skip posts
    state=success. Adoption must match the completed-analysis marker."""
    assert "ompleted\\ analysis" in APPROVE
    assert "Review Coverage" in APPROVE
    assert "FALLBACK_COVERED" in APPROVE


def test_pr_approve_status_trigger_accepts_coverage():
    assert "github.event.context == 'Review Coverage'" in APPROVE


def test_pr_approve_counts_fallback_blocking_reviews():
    """reviewer B's request_changes reviews must hold the gate."""
    assert 'github-actions[bot]' in APPROVE
    assert 'CHANGES_REQUESTED' in APPROVE

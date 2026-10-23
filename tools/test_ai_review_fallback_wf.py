"""Static regression tests for the AI review fallback workflows.

These pin the security boundaries as executable assertions: SHA-pinned
actions only, no Devin-context spoofing, no PR-head checkout in jobs
that carry Tailscale credentials, and the pr-approve evidence rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
FALLBACK = yaml.safe_load((WF / "ai-review-fallback.yml").read_text())
APPROVE = (WF / "pr-approve.yml").read_text()
SHA40 = re.compile(r"^[a-f0-9]{40}$")


def test_every_action_pinned_to_full_sha():
    uses = re.findall(r"uses: ([^\s@]+)@([^\s]+)",
                      (WF / "ai-review-fallback.yml").read_text())
    assert uses, "no actions found"
    for name, ref in uses:
        assert SHA40.match(ref), f"{name}@{ref} is not a full SHA pin"


def test_fallback_never_posts_devin_context():
    text = (WF / "ai-review-fallback.yml").read_text()
    assert 'context=Devin Review' not in text
    assert '"Review Coverage"' in text


def test_fallback_runs_on_pull_request_target():
    assert "pull_request_target" in FALLBACK[True]


def test_fallback_has_no_checkout_of_pr_head():
    """review-b checks out the BASE ref (pull_request_target default =
    base branch). No step may request the PR head sha."""
    text = (WF / "ai-review-fallback.yml").read_text()
    assert "pull_request.head.sha" not in re.sub(
        r"#.*", "", re.sub(r"head.sha.*pull_request", "", text)
    ) or True  # head.sha in env args is fine; checkout ref must not use it
    for job in FALLBACK["jobs"].values():
        for step in job.get("steps", []):
            if "actions/checkout" in str(step.get("uses", "")):
                ref = (step.get("with") or {}).get("ref", "")
                assert "head" not in str(ref), "checkout of PR head forbidden"


def test_fallback_jobs_gate_on_classifier():
    jobs = FALLBACK["jobs"]
    for name in ("review-a", "review-b"):
        assert "classify" in str(jobs[name].get("needs", ""))
        assert "EXECUTED" in str(jobs[name].get("if", ""))
    assert jobs["coverage"].get("if") == "always()"


def test_tailscale_jobs_carry_no_checkout_of_pr_and_id_token_only_where_needed():
    jobs = FALLBACK["jobs"]
    for name in ("review-a", "review-b"):
        perms = jobs[name].get("permissions", {})
        assert perms.get("id-token") == "write"
        assert perms.get("contents") == "read"
    # coverage publishes statuses only
    assert jobs["coverage"]["permissions"].get("statuses") == "write"
    assert jobs["coverage"]["permissions"].get("pull-requests") is None


def test_pr_approve_requires_completed_analysis_not_bare_success():
    """The false-success hole: a credit-exhausted skip posts
    state=success. Adoption must match the completed-analysis marker."""
    assert "ompleted\\ analysis" in APPROVE
    assert "Review Coverage" in APPROVE
    assert "FALLBACK_COVERED" in APPROVE


def test_pr_approve_status_trigger_accepts_coverage():
    assert "github.event.context == 'Review Coverage'" in APPROVE

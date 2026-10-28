"""Tests for scripts/publish-review-coverage.py — verdict matrix."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "publish_review_coverage",
    ROOT / "scripts" / "publish-review-coverage.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_devin_executed_needs_no_fallback():
    conclusion, desc, verdict = mod.compute_verdict("EXECUTED", "SKIPPED", "SKIPPED")
    assert conclusion == "success" and verdict == "EXECUTED"
    assert "fallback not needed" in desc


def test_both_reviewers_executed_is_covered():
    conclusion, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "EXECUTED", "EXECUTED")
    assert conclusion == "success" and verdict == "COVERED"
    assert "devin=SKIPPED_CREDITS" in desc


def test_a_only_is_degraded():
    """DEGRADED is action_required — never success. Partial coverage
    means a human decides; green would repeat the skipped-as-success
    bug one layer down."""
    conclusion, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "EXECUTED", "FAILED")
    assert conclusion == "action_required" and verdict == "DEGRADED"
    assert desc.startswith("DEGRADED a-only")
    assert "requires human review" in desc


def test_b_only_is_covered():
    # Lane B alone (direct Ollama, always posts a real review) covers the
    # PR — b-only=success is the documented acceptance rule. Reviewer A
    # flaking must not hold the gate hostage to infra outside the review.
    conclusion, desc, verdict = mod.compute_verdict("UNVERIFIED", "FAILED", "EXECUTED")
    assert conclusion == "success" and verdict == "COVERED"
    assert "b-only" in desc


def test_both_failed_is_failure():
    conclusion, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "FAILED", "FAILED")
    assert conclusion == "failure" and verdict == "FAILURE"


def test_tailscale_unavailable_is_failure_never_success():
    """Tailscale down → reviewers UNAVAILABLE → honest FAILURE."""
    conclusion, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "UNAVAILABLE", "UNAVAILABLE")
    assert conclusion == "failure" and verdict == "FAILURE"


def test_findings_are_execution_not_failure():
    """A reviewer that ran and returned findings reports EXECUTED —
    findings are a review result, not an infra failure."""
    conclusion, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "EXECUTED", "EXECUTED")
    assert verdict == "COVERED"


def test_unverified_devin_still_uses_fallback():
    _, _, verdict = mod.compute_verdict("UNVERIFIED", "EXECUTED", "EXECUTED")
    assert verdict == "COVERED"


def test_failed_before_review_uses_fallback():
    _, _, verdict = mod.compute_verdict("FAILED_BEFORE_REVIEW", "EXECUTED", "EXECUTED")
    assert verdict == "COVERED"


def test_critical_findings_mark_description_blocking():
    """A's critical findings are execution data, not infra failure:
    coverage stays success but carries the blocking marker the merge
    gate reads."""
    conclusion, desc, verdict = mod.compute_verdict(
        "SKIPPED_CREDITS", "EXECUTED", "EXECUTED", a_critical=2)
    assert conclusion == "success" and verdict == "COVERED"
    assert "findings=blocking(critical=2)" in desc


def test_degraded_with_critical_still_degraded_and_blocking():
    """Degraded coverage with a real finding: action_required (partial),
    and the summary still carries the blocking marker."""
    conclusion, desc, verdict = mod.compute_verdict(
        "SKIPPED_CREDITS", "EXECUTED", "FAILED", a_critical=1)
    assert conclusion == "action_required" and verdict == "DEGRADED"
    assert "findings=blocking" in desc


def test_mirror_state_never_greens_degraded():
    """The compatibility status mirror: action_required maps to pending
    (waiting on a human), never to a green that automation could adopt."""
    assert mod._mirror_state("success") == "success"
    assert mod._mirror_state("action_required") == "pending"
    assert mod._mirror_state("failure") == "failure"

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
    state, desc, verdict = mod.compute_verdict("EXECUTED", "SKIPPED", "SKIPPED")
    assert state == "success" and verdict == "EXECUTED"
    assert "fallback not needed" in desc


def test_both_reviewers_executed_is_covered():
    state, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "EXECUTED", "EXECUTED")
    assert state == "success" and verdict == "COVERED"
    assert "devin=SKIPPED_CREDITS" in desc


def test_a_only_is_degraded():
    state, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "EXECUTED", "FAILED")
    assert verdict == "DEGRADED"
    assert desc.startswith("DEGRADED a-only")


def test_b_only_is_degraded():
    state, desc, verdict = mod.compute_verdict("UNVERIFIED", "FAILED", "EXECUTED")
    assert verdict == "DEGRADED"
    assert "b-only" in desc


def test_both_failed_is_failure():
    state, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "FAILED", "FAILED")
    assert state == "failure" and verdict == "FAILURE"


def test_tailscale_unavailable_is_failure_never_success():
    """Tailscale down → reviewers UNAVAILABLE → honest FAILURE."""
    state, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "UNAVAILABLE", "UNAVAILABLE")
    assert state == "failure" and verdict == "FAILURE"


def test_findings_are_execution_not_failure():
    """A reviewer that ran and returned findings reports EXECUTED —
    findings are a review result, not an infra failure."""
    state, desc, verdict = mod.compute_verdict("SKIPPED_CREDITS", "EXECUTED", "EXECUTED")
    assert verdict == "COVERED"


def test_unverified_devin_still_uses_fallback():
    state, _, verdict = mod.compute_verdict("UNVERIFIED", "EXECUTED", "EXECUTED")
    assert verdict == "COVERED"


def test_failed_before_review_uses_fallback():
    state, _, verdict = mod.compute_verdict("FAILED_BEFORE_REVIEW", "EXECUTED", "EXECUTED")
    assert verdict == "COVERED"


def test_critical_findings_mark_description_blocking():
    """A's critical findings are execution data, not infra failure:
    coverage stays success but carries the blocking marker the merge
    gate reads."""
    state, desc, verdict = mod.compute_verdict(
        "SKIPPED_CREDITS", "EXECUTED", "EXECUTED", a_critical=2)
    assert state == "success" and verdict == "COVERED"
    assert "findings=blocking(critical=2)" in desc


def test_degraded_with_critical_still_degraded_and_blocking():
    state, desc, verdict = mod.compute_verdict(
        "SKIPPED_CREDITS", "EXECUTED", "FAILED", a_critical=1)
    assert verdict == "DEGRADED" and "findings=blocking" in desc

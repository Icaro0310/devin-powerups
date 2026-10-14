#!/usr/bin/env python3
"""Bidirectional parity check: devin-redact (Python) vs the TS port.

G1(c) condition 1 — parity is fixture-based and bidirectional:

  * Corpus cases are replayed through BOTH engines; every field must be
    byte-identical (input -> redact_text output+edits, scan_text findings).
  * The *pattern surface* is compared too: the set of
    (category, pattern_name) each engine knows. A pattern present on only
    one side — including TS-only additions — is drift and fails.

Modes:
  --golden   compare Python + TS against the committed corpus AND each
             other (PR gate; Python resolved via PYTHONPATH or the pinned
             install).
  --drift    same checks but against the *latest* devin-redact on PyPI
             (weekly job — the accepted 7-day window).

Usage:
  python3 tools/check_redact_parity.py --golden
      PYTHONPATH=<redact src>   OR  devin-redact installed in the env
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "packages/agent-sessions/test/redact-corpus.jsonl"
RUNNER = ROOT / "packages/agent-sessions/tools/redact_parity_runner.mjs"


def py_engine():
    from devin_redact.engine import redact_text, scan_text  # noqa: PLC0415
    from devin_redact.patterns import PATTERNS, pattern_name  # noqa: PLC0415

    def surface() -> set[str]:
        return {
            f"{cat}:{pattern_name(cat, i)}"
            for cat, regexes in PATTERNS.items()
            for i in range(len(regexes))
        }

    def run(text: str) -> dict:
        out, edits = redact_text(text)
        return {
            "redact_text": {"output": out, "edits": edits},
            "scan_text": scan_text(text, file="<corpus>", location="corpus"),
        }

    return run, surface


def ts_engine() -> tuple:
    """Run the TS port over every corpus input in one node process."""

    def run_batch(inputs: list[str]) -> list[dict]:
        proc = subprocess.run(
            ["node", str(RUNNER)],
            input=json.dumps(inputs),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)

    proc = subprocess.run(
        ["node", str(RUNNER), "--surface"], capture_output=True, text=True, check=True
    )
    surface = set(json.loads(proc.stdout))
    return run_batch, surface


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", action="store_true", help="PR gate mode")
    ap.add_argument("--drift", action="store_true", help="latest-PyPI mode")
    args = ap.parse_args()
    if not (args.golden or args.drift):
        ap.error("pass --golden or --drift")

    try:
        py_run, py_surface_fn = py_engine()
        py_surface = py_surface_fn()
    except ImportError as e:
        print(f"FAIL: devin_redact not importable ({e}) — set PYTHONPATH to "
              f"the pinned source or pip install devin-redact", file=sys.stderr)
        return 2

    cases = [json.loads(l) for l in CORPUS.read_text().splitlines() if l.strip()]
    ts_batch, ts_surface = ts_engine()
    ts_results = ts_batch([c["input"] for c in cases])

    failures: list[str] = []

    # Leg 1 — corpus replay on both sides (golden = frozen truth)
    for case, ts in zip(cases, ts_results):
        py = py_run(case["input"])
        golden = {"redact_text": case["redact_text"], "scan_text": case["scan_text"]}
        for side, got in (("python", py), ("ts", ts)):
            if got != golden:
                failures.append(
                    f"case {case['name']}: {side} diverges from corpus\n"
                    f"  golden: {json.dumps(golden, sort_keys=True)[:400]}\n"
                    f"  got:    {json.dumps(got, sort_keys=True)[:400]}"
                )
        if py != ts:
            failures.append(f"case {case['name']}: python vs ts direct diff")

    # Leg 2 — pattern surface, bidirectional
    only_py = py_surface - ts_surface
    only_ts = ts_surface - py_surface
    if only_py:
        failures.append(f"patterns only in Python (TS missing): {sorted(only_py)}")
    if only_ts:
        failures.append(f"patterns only in TS (drift!): {sorted(only_ts)}")

    mode = "drift(latest)" if args.drift else "golden(pinned)"
    if failures:
        print(f"PARITY FAIL [{mode}] — {len(failures)} divergence(s):")
        for f in failures[:15]:
            print(" -", f)
        return 1
    print(f"PARITY OK [{mode}] — {len(cases)} cases, "
          f"{len(py_surface & ts_surface)} shared patterns, both directions clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

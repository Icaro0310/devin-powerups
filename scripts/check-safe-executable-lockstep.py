#!/usr/bin/env python3
"""Check that every distributed ``safe-executable.cjs`` copy is
byte-identical to the canonical implementation.

``safe-executable.cjs`` is vendored into each adapter that ships a VS
Code extension or daemon launcher. The copies drift silently — a fix
landed in the canonical ``adapters/shared/`` file while two of nine
copies carried the older revision, and nothing noticed until runtime.
This sensor fails red the moment any copy diverges.

The canonical file resolves in order:

1. ``adapters/shared/safe-executable.cjs`` inside the scanned root —
   this is devin-powerups itself (or a PR checkout of it), where the
   canonical file lives and copies must match *this* version;
2. ``.powerups-sensor/adapters/shared/safe-executable.cjs`` — the
   sensor checkout the reusable workflow performs at the ``v1`` tag
   when the calling repo does not ship the script (script and workflow
   move together on retag, D-2026-10-13i).

Resolution failure is fail-closed: a caller that vendors copies but
cannot present a canonical file errors out rather than passing.

Usage:

    python3 scripts/check-safe-executable-lockstep.py --root .
    python3 scripts/check-safe-executable-lockstep.py --selftest
"""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

COPY_NAME = "safe-executable.cjs"
CANONICAL_REL = Path("adapters/shared") / COPY_NAME
SENSOR_CANONICAL_REL = Path(".powerups-sensor") / CANONICAL_REL

# Directories that never count as distributed copies: VCS internals,
# vendored trees, and the sensor checkout itself (it *contains* the
# canonical file — counting it would pin the check to pass trivially).
SKIP_DIRS = {".git", ".powerups-sensor", "node_modules", "dist", "out"}


def find_copies(root: Path) -> list[Path]:
    """All ``safe-executable.cjs`` files under ``root``, excluding the
    canonical location and vendored/generated trees."""
    copies = []
    canonical = (root / CANONICAL_REL).resolve()
    for path in sorted(root.rglob(COPY_NAME)):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.resolve() == canonical:
            continue
        copies.append(path)
    return copies


def resolve_canonical(root: Path) -> Path | None:
    for rel in (CANONICAL_REL, SENSOR_CANONICAL_REL):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: Path) -> int:
    canonical = resolve_canonical(root)
    if canonical is None:
        print(
            f"lockstep: canonical {CANONICAL_REL} not found under {root} "
            "or .powerups-sensor/ — refusing to pass",
            file=sys.stderr,
        )
        return 2
    want = sha256(canonical)
    drifted = [
        (copy, sha256(copy)) for copy in find_copies(root) if sha256(copy) != want
    ]
    if not drifted:
        total = len(find_copies(root))
        print(f"lockstep: {total} cop{'y' if total == 1 else 'ies'} match canonical")
        return 0
    print(
        f"lockstep: {len(drifted)} cop{'y' if len(drifted) == 1 else 'ies'} "
        f"drifted from {canonical.relative_to(root)}:",
        file=sys.stderr,
    )
    for copy, digest in drifted:
        print(f"  {copy.relative_to(root)} sha256={digest}", file=sys.stderr)
    return 1


def selftest() -> int:
    """Fixture-driven check: matching copies pass, drifted or missing
    canonical fail, and the canonical file itself is never counted."""
    failures = []

    def expect(name: str, got: int, want: int) -> None:
        if got != want:
            failures.append(f"{name}: exit {got}, want {want}")

    blob = b"// canonical implementation\n"
    drifted_blob = b"// older revision\n"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / CANONICAL_REL.parent).mkdir(parents=True)
        (root / CANONICAL_REL).write_bytes(blob)
        good = root / "packages/a/adapters/vscode" / COPY_NAME
        good.parent.mkdir(parents=True)
        good.write_bytes(blob)
        # nested vendored tree must be ignored
        vendored = root / "node_modules/x" / COPY_NAME
        vendored.parent.mkdir(parents=True)
        vendored.write_bytes(drifted_blob)
        expect("clean", check(root), 0)

        bad = root / "packages/b/adapters/vscode" / COPY_NAME
        bad.parent.mkdir(parents=True)
        bad.write_bytes(drifted_blob)
        expect("drifted copy", check(root), 1)

        (root / CANONICAL_REL).unlink()
        sensor = root / SENSOR_CANONICAL_REL
        sensor.parent.mkdir(parents=True)
        sensor.write_bytes(blob)
        expect("sensor canonical fallback", check(root), 1)

        bad.unlink()
        good.unlink()
        expect("sensor canonical, copies match", check(root), 0)

        sensor.unlink()
        expect("no canonical anywhere", check(root), 2)

    if failures:
        for failure in failures:
            print(f"selftest: {failure}", file=sys.stderr)
        return 1
    print("selftest: all cases passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="run the fixture self-check instead of scanning",
    )
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return check(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())

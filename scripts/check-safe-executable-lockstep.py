#!/usr/bin/env python3
"""Check that every distributed ``safe-executable.cjs`` copy is
byte-identical to the canonical implementation.

``safe-executable.cjs`` is vendored into each adapter that ships a VS
Code extension or daemon launcher. The copies drift silently — a fix
landed in the canonical ``adapters/shared/`` file while two of nine
copies carried the older revision, and nothing noticed until runtime.
This sensor fails red the moment any copy diverges.

The canonical file resolves in order:

1. ``.powerups-sensor/adapters/shared/safe-executable.cjs`` — the
   sensor checkout the reusable workflow performs at the ``v1`` tag
   when the calling repo does not ship the script or the canonical
   file itself (script and workflow move together on retag,
   D-2026-10-13i). Preferred because it is the published contract —
   a caller retaining a stale local ``adapters/shared/`` copy must
   not self-certify against it;
2. ``adapters/shared/safe-executable.cjs`` inside the scanned root —
   this is devin-powerups itself (or a PR checkout of it), where the
   sensor checkout is never performed and the canonical file lives;
   copies must match *this* version.

Resolution failure is fail-closed: a caller that vendors copies but
cannot present a canonical file errors out rather than passing.

Copy discovery mirrors the hygiene scanner's explicit roots — only
files under the shipped adapter/skill directories count as
distributed copies (a fixture named ``safe-executable.cjs`` in
``tests/`` or ``docs/`` is none of this check's business).

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

# Same explicit scan roots as scripts/check-adapters-hygiene.py — no
# recursive root-wide search, so vendored checkouts, fixtures and
# unrelated trees never count as distributed copies.
SCAN_ROOT_GLOBS = ("adapters", "packages/*/adapters", ".devin/skills", "packages/*/.devin/skills")


def find_copies(root: Path) -> list[Path]:
    """All ``safe-executable.cjs`` files under the shipped adapter/skill
    roots, excluding the canonical location itself."""
    copies = []
    canonical = (root / CANONICAL_REL).resolve()
    for glob in SCAN_ROOT_GLOBS:
        for scan_root in root.glob(glob):
            if not scan_root.is_dir():
                continue
            for path in sorted(scan_root.rglob(COPY_NAME)):
                if path.resolve() == canonical:
                    continue
                copies.append(path)
    return sorted(set(copies))


def resolve_canonical(root: Path) -> Path | None:
    for rel in (SENSOR_CANONICAL_REL, CANONICAL_REL):
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
    canonical fail, the canonical file itself is never counted, the
    sensor canonical wins over a stale local one, and helper files
    outside the adapter roots are ignored."""
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
        # same-named file outside the shipped roots is a fixture, not a copy
        fixture = root / "tests/fixtures" / COPY_NAME
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(drifted_blob)
        expect("clean; fixture ignored", check(root), 0)

        bad = root / "adapters/vscode_ext" / COPY_NAME
        bad.parent.mkdir(parents=True)
        bad.write_bytes(drifted_blob)
        expect("drifted copy", check(root), 1)

        # sensor checkout at v1 is the published contract — it wins
        # over a stale local adapters/shared/ in a caller
        sensor = root / SENSOR_CANONICAL_REL
        sensor.parent.mkdir(parents=True)
        sensor.write_bytes(blob)
        bad.write_bytes(blob)
        expect("sensor canonical preferred over local", check(root), 0)

        (root / CANONICAL_REL).unlink()
        good.write_bytes(drifted_blob)
        bad.write_bytes(drifted_blob)
        expect("sensor canonical, copies drifted", check(root), 1)

        good.write_bytes(blob)
        bad.write_bytes(blob)
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

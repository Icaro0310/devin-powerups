#!/usr/bin/env python3
"""Block personal-machine paths from entering the repo through a diff.

Incident class this sensor covers: ``git add -A`` sweeps local state
files (automation snapshots, doctor output, .env dumps) carrying the
author's absolute home path — username, machine layout, cron schedules
— into a public repository. secrets-scan never sees it (a path is not a
token); the block has to happen at the boundary where files enter the
commit.

Default mode reads the staged file list
(``git diff --cached --name-only --diff-filter=ACM``) and scans only
the lines that diff *adds* to the staged blob — run it as a pre-commit
gate locally. ``--pr-base <ref>`` switches to ``git diff <ref>...HEAD``
added lines for CI. Added-lines scoping is deliberate: a pre-existing
doc example of a banned path shape is not this diff's leak, and
flagging it would block every unrelated edit of that file. ``--all``
scans every tracked text file end to end — the fallback when no merge
base exists (first push of a branch, tag events); it is whole-tree by
design, so repos carrying legitimate path examples should not rely on
it passing.

Findings report ``file:line: rule`` and never echo the line: copying
the match into CI logs or annotations would re-leak the path (and
whatever sits next to it on the line).

Patterns — built from fragments on purpose, so this file stays clean
under its own scan:

* ``/home/<owner>/`` — the machine owner's literal home dir.
  Deliberately NOT ``/home/*``: CI runners legitimately carry
  ``/home/runner/`` and docs may show ``/home/user/``.
* macOS home dirs (``/`` + ``Users/`` + name) — never legitimate on
  Linux CI or in ecosystem code.
* Windows profile dirs (``?:\\Users\\<name>`` / forward-slash form) —
  any drive letter, case-insensitive.

Only these text extensions are scanned: ``.json .yaml .yml .txt .md
.env .cfg .ini .toml .csv .log`` — the file class of the incident. A
``.py`` fixture or a binary blob is out of scope by design.

There is deliberately no allowlist: unlike secrets-scan fixtures, a
personal path is never legitimate — the fix is sanitize or gitignore,
not pin.

Usage:
    python3 scripts/check-internal-paths.py [--root <repo>]
    python3 scripts/check-internal-paths.py --pr-base origin/main
    python3 scripts/check-internal-paths.py --all
    python3 scripts/check-internal-paths.py --selftest

Exit codes: 0 clean, 1 findings, 2 the diff could not be computed
(not a git repo, unresolvable ref — fail closed, never silent).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# The real machine owner's login — also the public GitHub org handle, so
# embedding it is not itself a leak. Joined into the patterns at runtime;
# the literal ``/home/<owner>`` path must never sit in this source file.
OWNER = "ikaros"

TEXT_SUFFIXES = (
    ".json", ".yaml", ".yml", ".txt", ".md", ".env",
    ".cfg", ".ini", ".toml", ".csv", ".log",
)

# (rule-name, compiled regex). Names are stable — they appear in the
# failure report.
RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "personal-path/home-owner",
        re.compile("/home/" + OWNER + r"(?![\w-])"),
    ),
    (
        "personal-path/macos-users",
        re.compile("/" + "Users" + r"/\S"),
    ),
    (
        "personal-path/windows-users",
        re.compile(r"[A-Za-z]:[\\/]+Users[\\/]", re.IGNORECASE),
    ),
]

# Hunk header of a ``git diff -U0`` — captures the new-side start and
# count of each added run.
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@",
                     re.MULTILINE)


class GitError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def is_text_file(name: str) -> bool:
    # endswith (not Path.suffix) so a dotfile like ``.env`` matches —
    # Path(".env").suffix is "".
    return name.lower().endswith(TEXT_SUFFIXES)


def target_files(repo: Path, mode: str, base: str | None) -> list[str]:
    if mode == "staged":
        out = _git(repo, "diff", "--cached", "--name-only",
                   "--diff-filter=ACM", "-z")
    elif mode == "pr":
        out = _git(repo, "diff", f"{base}...HEAD", "--name-only",
                   "--diff-filter=ACM", "-z")
    else:  # all
        out = _git(repo, "ls-files", "-z")
    return [p for p in out.split("\0") if p and is_text_file(p)]


def read_target(repo: Path, mode: str, rel: str) -> bytes | None:
    """The content that would be committed: index blob for staged mode,
    HEAD blob for pr/all. ``None`` when the blob is unreadable."""
    spec = f":{rel}" if mode == "staged" else f"HEAD:{rel}"
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", spec],
        capture_output=True, check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def added_lines(repo: Path, mode: str, base: str | None,
                rel: str) -> set[int] | None:
    """New-side line numbers the diff adds inside ``rel`` — the scan
    scope for staged/pr modes, so a changed file's pre-existing content
    (an old doc example the PR only edits near) is not flagged. ``None``
    means whole-file: ``--all`` has no diff to scope by."""
    if mode == "all":
        return None
    if mode == "staged":
        out = _git(repo, "diff", "--cached", "-U0",
                   "--diff-filter=ACM", "--", rel)
    else:  # pr
        out = _git(repo, "diff", f"{base}...HEAD", "-U0",
                   "--diff-filter=ACM", "--", rel)
    lines: set[int] = set()
    for m in HUNK_RE.finditer(out):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        lines.update(range(start, start + count))
    return lines


def scan_text(rel: str, text: str,
              only: set[int] | None = None) -> list[str]:
    findings: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if only is not None and lineno not in only:
            continue
        for name, rx in RULES:
            if rx.search(line):
                # No excerpt: the match itself is the leak. file:line:
                # rule is everything a fix needs.
                findings.append(f"{rel}:{lineno}: {name}")
    return findings


def run(repo: Path, mode: str, base: str | None) -> tuple[list[str], int]:
    """Return (findings, scanned-file-count)."""
    files = target_files(repo, mode, base)
    findings: list[str] = []
    scanned = 0
    for rel in files:
        blob = read_target(repo, mode, rel)
        if blob is None or b"\0" in blob[:8192]:
            continue
        scanned += 1
        findings += scan_text(rel, blob.decode("utf-8", errors="replace"),
                              added_lines(repo, mode, base, rel))
    return findings, scanned


# --- selftest ---------------------------------------------------------------


def _init_repo(repo: Path) -> None:
    def g(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True, capture_output=True, text=True,
        )

    repo.mkdir(parents=True)
    g("init", "-q", "-b", "main")
    g("-c", "user.email=t@t", "-c", "user.name=t",
      "commit", "-qm", "init", "--allow-empty")


def selftest() -> int:
    failures: list[str] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"  {status} {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    # Leak strings are assembled from fragments — the literals must never
    # sit in this source file or the sensor flags itself.
    leak_home = "/home/" + OWNER + "/test"
    leak_mac = "/" + "Users" + "/alice/x"
    leak_win_bs = "C:" + "\\Users\\bob"
    leak_win_fs = "C:" + "/" + "Users/bob"
    ok_runner = "/home/runner/work/x"
    ok_user = "/home/user/docs"
    ok_home_sibling = "/home/" + OWNER + "-other/x"

    hits = scan_text("a.json", "snapshot: " + leak_home + "\n")
    expect("unit: owner home path flagged",
           any("home-owner" in h for h in hits), "; ".join(hits))
    hits = scan_text("b.md", "see " + leak_mac + "\n")
    expect("unit: macOS users path flagged",
           any("macos-users" in h for h in hits), "; ".join(hits))
    hits = scan_text("c.ini", "d=" + leak_win_bs + "\n")
    expect("unit: windows backslash path flagged",
           any("windows-users" in h for h in hits), "; ".join(hits))
    hits = scan_text("c2.ini", "d=" + leak_win_fs + "\n")
    expect("unit: windows forward-slash path flagged",
           any("windows-users" in h for h in hits), "; ".join(hits))
    hits = scan_text("d.yaml", "work: " + ok_runner + "\n"
                   "docs: " + ok_user + "\n"
                   "alt: " + ok_home_sibling + "\n")
    expect("unit: runner/other homes pass", hits == [], "; ".join(hits))
    expect("unit: finding is file:line: rule, no excerpt",
           scan_text("x.json", "a\n" + leak_home + "\n")
           == ["x.json:2: personal-path/home-owner"])
    all_hits = (scan_text("x.json", leak_home + "\n")
                + scan_text("y.md", leak_mac + "\n")
                + scan_text("z.ini", leak_win_bs + "\n"))
    expect("unit: findings never echo the matched path",
           all_hits != []
           and not any(leak in h for h in all_hits
                       for leak in (leak_home, leak_mac, leak_win_bs)))
    expect("unit: only= scopes the scan to added lines",
           scan_text("x.json", leak_home + "\nclean\n", only={2}) == [])

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # ---- staged mode ------------------------------------------
        repo = base / "staged"
        _init_repo(repo)
        (repo / "clean.json").write_text('{"ok": true}\n')
        (repo / "doctor").mkdir()
        (repo / "doctor/snapshot.json").write_text(
            '{"cwd": "' + leak_home + '"}\n')
        (repo / "notes.txt").write_text("workdir " + ok_runner + "\n")
        (repo / "skip.py").write_text("P = '" + leak_home + "'\n")
        (repo / "unstaged.json").write_text('{"p": "' + leak_home + '"}\n')
        _git(repo, "add", "clean.json", "doctor/snapshot.json",
             "notes.txt", "skip.py")
        findings, _ = run(repo, "staged", None)
        expect("staged: dirty staged file flagged",
               any("doctor/snapshot.json:1:" in f for f in findings),
               "; ".join(findings))
        expect("staged: clean staged files pass",
               not any(f.startswith(("clean.json", "notes.txt"))
                       for f in findings))
        expect("staged: non-listed extension ignored",
               not any(f.startswith("skip.py") for f in findings))
        expect("staged: unstaged file ignored",
               not any(f.startswith("unstaged.json") for f in findings))
        # staged blob wins over the worktree: clean the worktree copy
        # after staging and the staged content still flags.
        (repo / "clean.json").write_text('{"p": "' + leak_home + '"}\n')
        _git(repo, "add", "clean.json")
        (repo / "clean.json").write_text('{"ok": true}\n')
        findings, _ = run(repo, "staged", None)
        expect("staged: index blob scanned, not worktree",
               any(f.startswith("clean.json:") for f in findings),
               "; ".join(findings))

        # ---- staged mode: only lines the diff adds are scanned ------
        repo = base / "staged-partial"
        _init_repo(repo)
        (repo / "guide.md").write_text(
            "intro\nold example " + leak_win_bs + "\noutro\n")
        _git(repo, "add", "guide.md")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "base")
        # Unrelated edit on line 1: the pre-existing example on line 2
        # is context, not an addition — it must not fail the gate.
        (repo / "guide.md").write_text(
            "intro edited\nold example " + leak_win_bs + "\noutro\n")
        _git(repo, "add", "guide.md")
        findings, _ = run(repo, "staged", None)
        expect("staged: pre-existing example not flagged",
               findings == [], "; ".join(findings))
        # A newly staged line carrying a path still flags.
        (repo / "guide.md").write_text(
            "intro edited\nold example " + leak_win_bs + "\noutro\n"
            "new " + leak_home + "\n")
        _git(repo, "add", "guide.md")
        findings, _ = run(repo, "staged", None)
        expect("staged: newly added path line flagged",
               findings == ["guide.md:4: personal-path/home-owner"],
               "; ".join(findings))

        # ---- pr-base mode ------------------------------------------
        repo = base / "pr"
        _init_repo(repo)
        (repo / "README.md").write_text("docs: " + ok_user + "\n")
        _git(repo, "add", "README.md")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "base")
        _git(repo, "checkout", "-qb", "feat")
        (repo / "automation-snapshot.json").write_text(
            '{"cron": "0 6 * * *", "log": "' + leak_win_bs + '"}\n')
        (repo / "env.md").write_text("export HOME=" + leak_mac + "\n")
        _git(repo, "add", "automation-snapshot.json", "env.md")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "feat")
        findings, _ = run(repo, "pr", "main")
        expect("pr-base: PR diff files flagged",
               any("automation-snapshot.json:1:" in f for f in findings)
               and any("env.md:1:" in f for f in findings),
               "; ".join(findings))
        expect("pr-base: untouched base file not flagged",
               not any(f.startswith("README.md") for f in findings))
        findings, _ = run(repo, "pr", "feat")
        expect("pr-base: empty diff is clean", findings == [])

        # ---- pr-base mode: pre-existing content is not rescanned ----
        repo = base / "pr-partial"
        _init_repo(repo)
        (repo / "guide.md").write_text(
            "l1\nexample " + leak_win_bs + "\nl3\n")
        _git(repo, "add", "guide.md")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "base")
        _git(repo, "checkout", "-qb", "feat")
        (repo / "guide.md").write_text(
            "l1\nexample " + leak_win_bs + "\nl3 edited\n")
        _git(repo, "add", "guide.md")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "doc tweak")
        findings, _ = run(repo, "pr", "main")
        expect("pr-base: untouched pre-existing example passes",
               findings == [], "; ".join(findings))

        # ---- all mode -----------------------------------------------
        repo = base / "all"
        _init_repo(repo)
        (repo / "tracked.log").write_text("path " + leak_win_fs + "\n")
        _git(repo, "add", "tracked.log")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "add log")
        (repo / "untracked.log").write_text("path " + leak_home + "\n")
        findings, _ = run(repo, "all", None)
        expect("all: tracked file flagged",
               any("tracked.log:1:" in f for f in findings),
               "; ".join(findings))
        expect("all: untracked file ignored",
               not any(f.startswith("untracked.log") for f in findings))

        # ---- dotfile + git errors -------------------------------------
        repo = base / "dotenv"
        _init_repo(repo)
        (repo / ".env").write_text("HOME=" + leak_home + "\n")
        _git(repo, "add", ".env")
        findings, _ = run(repo, "staged", None)
        expect("staged: .env dotfile flagged",
               any(f.startswith(".env:1:") for f in findings),
               "; ".join(findings))
        try:
            run(base / "not-a-repo", "staged", None)
            expect("git error propagates", False, "no error raised")
        except GitError:
            expect("git error propagates", True)

    if failures:
        print(f"selftest: {len(failures)} failure(s)")
        return 1
    print("selftest: all fixtures behaved as expected")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".",
                    help="repo root / worktree to scan (default: %(default)s)")
    mode_group = ap.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--pr-base", metavar="REF",
        help="scan `git diff REF...HEAD` (CI mode) instead of the index")
    mode_group.add_argument(
        "--all", action="store_true",
        help="scan every tracked text file, not just the diff")
    ap.add_argument("--selftest", action="store_true",
                    help="run the scanner against synthetic fixtures and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    repo = Path(args.root).resolve()
    mode = "pr" if args.pr_base else ("all" if args.all else "staged")
    try:
        findings, scanned = run(repo, mode, args.pr_base)
    except GitError as exc:
        print(f"check-internal-paths: {exc}", file=sys.stderr)
        return 2

    annotate = os.environ.get("GITHUB_ACTIONS") == "true"
    for finding in findings:
        print(finding)
        if annotate:
            # rpartition: filenames may contain ':' — the rule name and
            # the line number are the two right-hand fields.
            head, _, rule = finding.rpartition(": ")
            file_part, _, line_part = head.rpartition(":")
            print(f"::error file={file_part},line={line_part}::{rule}")
    if findings:
        print(f"check-internal-paths: {len(findings)} personal-path "
              f"finding(s) in {scanned} scanned file(s) — a machine path "
              "is never part of the public contract. Sanitize the file or "
              "gitignore it; do not commit.", file=sys.stderr)
        return 1
    print(f"check-internal-paths: {scanned} file(s) scanned, clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

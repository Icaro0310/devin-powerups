"""Contract test for the <pkg> skill face.

Skeleton — copy next to the SKILL.md it guards (or into the package's
tests/ dir) and adjust SKILL_PATH / the banned-flag list to the
package's real mutating surface.
"""

import re
from pathlib import Path

SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"

# Flags/commands of the package's mutating half. AI surfaces must not
# name them anywhere — not even to describe them.
BANNED = [
    r"--apply\b",
    r"--restore\b",
    r"\bdelete\b",
    r"\bapprove\b",
    r"\bspawn\b",
    r"\bkill\b",
]


def _text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_skill_md_exists_with_frontmatter():
    text = _text()
    assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
    frontmatter = text.split("---", 2)[1]
    assert re.search(r"^name:\s*\S+", frontmatter, re.M)
    assert re.search(r"^description:\s*\S+", frontmatter, re.M)


def test_skill_declares_read_only():
    assert "read-only" in _text().lower()


def test_skill_names_no_mutating_flags():
    text = _text()
    for pattern in BANNED:
        assert not re.search(pattern, text, re.I), (
            f"mutating flag matching {pattern!r} reached the skill surface"
        )

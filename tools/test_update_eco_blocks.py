"""Tests for update_eco_blocks.py — marker replacement and insertion."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import update_eco_blocks as ueb


def test_find_insert_after_div():
    lines = ["<div>\n", "badges\n", "</div>\n", "\n", "# tool\n"]
    assert ueb.find_insert(lines) == 3


def test_find_insert_falls_back_to_heading():
    lines = ["intro\n", "# tool\n", "body\n"]
    assert ueb.find_insert(lines) == 2


BLOCK = f"{ueb.BEGIN}\nBLOCK\n{ueb.END}"


def test_update_inserts_block(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("<div>\nx\n</div>\n\n# tool\n", encoding="utf-8")
    assert ueb.update_readme(readme, BLOCK)
    text = readme.read_text()
    assert f"</div>\n\n{BLOCK}\n\n# tool" in text


def test_update_replaces_marked_region(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        f"top\n{ueb.BEGIN}\nOLD\n{ueb.END}\nbottom\n", encoding="utf-8"
    )
    assert ueb.update_readme(readme, BLOCK.replace("BLOCK", "NEW"))
    text = readme.read_text()
    assert "OLD" not in text and "NEW" in text and "bottom" in text


def test_update_idempotent(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(f"{ueb.BEGIN}\nSAME\n{ueb.END}\n", encoding="utf-8")
    assert not ueb.update_readme(readme, f"{ueb.BEGIN}\nSAME\n{ueb.END}")


def test_check_missing_returns_nonzero(tmp_path, capsys):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"repositories": [
        {"name": "ghost", "artifact": "tool", "visibility": "public",
         "public": True},
    ]}), encoding="utf-8")
    sys.argv = ["x", "--root", str(tmp_path), "--registry", str(reg),
                "--check"]
    assert ueb.main() == 1
    assert "missing-clone ghost" in capsys.readouterr().err

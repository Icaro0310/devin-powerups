from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import render_llms


REGISTRY = TOOLS.parent / "registry.json"


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_index_lists_every_track_and_all_grouped_tools():
    rendered = render_llms.render_index(_registry())

    assert "## What do you want to do?" in rendered
    for verb in ("Understand", "Verify", "Control", "Build"):
        assert f"- {verb} (" in rendered
    for name in _registry()["devkit"]["tools"]:
        assert name in rendered


def test_index_journeys_match_registry_order():
    registry = _registry()
    rendered = render_llms.render_index(registry)

    for audience, steps in registry["journeys"].items():
        chain = " → ".join(s["repo"] for s in steps)
        assert chain in rendered, audience


def test_full_covers_tools_environments_and_related():
    registry = _registry()
    rendered = render_llms.render_full(registry)

    assert rendered.index("## Tool-by-tool") < rendered.index(
        "## Execution environments"
    ) < rendered.index("## Related artifacts")
    for env in registry["environments"].values():
        assert env["label"] in rendered
    assert "qwenpaw-suite" in rendered
    # private/non-public entries never leak into LLM surfaces
    assert "personal-agent-system" not in rendered
    assert "devin-dashboard" not in rendered


def test_patch_check_detects_drift(tmp_path: Path):
    target = tmp_path / "llms.txt"
    target.write_text(
        "# header\n\n"
        "<!-- LLMS:BEGIN -->\nstale\n<!-- LLMS:END -->\n\n"
        "## Key facts\nkept\n"
    )
    registry_path = str(REGISTRY)

    assert render_llms.main(
        ["index", "--registry", registry_path, "--check", str(target)]
    ) == 1
    assert render_llms.main(
        ["index", "--registry", registry_path, "--patch", str(target)]
    ) == 0
    assert render_llms.main(
        ["index", "--registry", registry_path, "--check", str(target)]
    ) == 0
    # narrative outside the markers is preserved
    assert target.read_text().endswith("## Key facts\nkept\n")


def test_check_fails_when_markers_missing(tmp_path: Path):
    target = tmp_path / "llms.txt"
    target.write_text("# no markers\n")
    assert render_llms.main(
        ["index", "--registry", str(REGISTRY), "--check", str(target)]
    ) == 2

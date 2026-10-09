from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import render_catalog


REGISTRY = TOOLS.parent / "registry.json"


def test_catalog_counts_match_registry_and_separate_tools_from_hub():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    tools, hubs, distributions, related = render_catalog.catalog_sections(registry)

    assert len(tools) == 19
    assert [item["name"] for item in hubs] == ["devin-powerups"]
    assert [item["name"] for item in distributions] == ["devin-devkit"]
    assert {item["name"] for item in related} == {
        "qwenpaw-suite", "awesome-devin"
    }


def test_profile_catalog_is_public_and_has_explicit_totals():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rendered = render_catalog.render_profile_catalog(registry)

    assert "19 first-party tools · 1 distribution layer · 1 registry hub · 2 related artifacts (23 entries)" in rendered
    assert "devin-devkit" in rendered
    assert "devin-dashboard" not in rendered
    assert "personal-agent-system" not in rendered
    assert "devin-learning" not in rendered
    assert "devin-powerups" in rendered
    assert "devin-office" in rendered


def test_catalog_labels_related_artifacts_instead_of_calling_them_tools():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rendered = render_catalog.render_profile_catalog(registry)

    assert "| **Control** | [`devin-judge`]" in rendered
    assert "| **Related Suite** | [`qwenpaw-suite`]" in rendered
    assert "| **Related Resource** | [`awesome-devin`]" in rendered


def test_public_executable_artifacts_declare_platforms_and_environments():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    executable = {"tool", "service", "suite", "distribution", "infrastructure"}
    environments = {"linux", "personal_windows", "corporate_windows"}

    for repo in registry["repositories"]:
        if repo["visibility"] == "public" and repo["artifact"] in executable:
            assert repo.get("platforms"), repo["name"]
            assert set(repo.get("environments", {})) == environments, repo["name"]
            assert repo["environments"]["corporate_windows"]["runtime"] in {"local-only", "unavailable"}


def test_catalog_table_uses_registry_descriptions_and_urls():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rendered = render_catalog.render_profile_catalog(registry)
    repo = next(r for r in registry["repositories"] if r["name"] == "devin-assure")

    assert f"[`devin-assure`]({repo['url']})" in rendered
    assert repo["description"].replace("|", "\\|") in rendered


def test_patch_profile_catalog_only_replaces_marked_block():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rendered = render_catalog.render_profile_catalog(registry)
    current = "before\n<!-- DEVIN-CATALOG:BEGIN -->\nstale\n<!-- DEVIN-CATALOG:END -->\nafter\n"

    patched = render_catalog.patch_profile_catalog(current, rendered)

    assert patched.startswith("before\n")
    assert patched.endswith("after\n")
    assert "stale" not in patched
    assert rendered in patched

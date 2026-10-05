from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import export_devkit_manifest as exporter


REGISTRY = TOOLS.parent / "registry.json"


def load_registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_manifest_is_repeatable_and_counts_tools_separately_from_hub():
    registry = load_registry()
    first = exporter.build_manifest(registry)
    second = exporter.build_manifest(registry)

    assert first == second
    assert first["catalog"] == {
        "tool_count": 19,
        "distribution_count": 1,
        "hub_count": 1,
        "related_count": 3,
        "entry_count": 24,
    }
    assert len(first["tools"]) == 20


def test_manifest_does_not_include_private_or_non_tool_repositories():
    manifest = exporter.build_manifest(load_registry())
    ids = {tool["id"] for tool in manifest["tools"]}

    assert "personal-agent-system" not in ids
    assert "devin-dashboard" not in ids
    assert "devin-learning" not in ids
    assert "devin-powerups" not in ids
    assert "awesome-devin" not in ids
    assert "qwenpaw-suite" not in ids
    assert "poordjaevin" in ids
    descriptions = " ".join(tool["description"] for tool in manifest["tools"])
    assert "personal-agent-system" not in descriptions
    assert "devin-dashboard" not in descriptions
    assert "devin-learning" not in descriptions


def test_manifest_uses_pypi_names_and_real_cli_entrypoints():
    manifest = exporter.build_manifest(load_registry())
    tools = {tool["id"]: tool for tool in manifest["tools"]}

    assert tools["devin-internals-spec"]["install_spec"] == "devin-internals-spec==0.3.0"
    assert tools["devin-memory"]["install_spec"] == "devin-memory[mcp]==0.3.0"
    assert tools["devin-qa-pack"]["commands"] == ["devin-qa-pack"]
    assert tools["devin-orchestrator"]["package"] == "devin-fanout"
    assert tools["devin-orchestrator"]["commands"] == ["devin-orchestrator"]
    assert tools["devin-bridge"]["manager"] == "npm"
    assert tools["devin-bridge"]["runtime"] == "node>=20"
    assert tools["devin-bridge"]["install_spec"].startswith("https://github.com/Icaro0310/devin-bridge/archive/")
    assert tools["devin-bridge"]["requires_git"] is False
    assert tools["devin-doctor"]["install_spec"].startswith("https://github.com/Icaro0310/devin-doctor/archive/")
    assert tools["devin-doctor"]["requires_git"] is False
    assert manifest["git_required_tools"] == []
    assert tools["devin-office"]["install_spec"] is None
    assert tools["devin-office"]["status"] == "manual"


def test_profiles_only_reference_known_tools():
    manifest = exporter.build_manifest(load_registry())
    tools = {tool["id"] for tool in manifest["tools"]}

    for profile in manifest["profiles"].values():
        assert set(profile.get("tools", [])) <= tools
        assert set(profile.get("manual", [])) <= tools


def test_unknown_profile_tool_is_rejected():
    registry = copy.deepcopy(load_registry())
    registry["devkit"]["profiles"]["qa"]["tools"].append("private-tool")

    with pytest.raises(exporter.ManifestError, match="unknown tool"):
        exporter.build_manifest(registry)


def test_github_sources_are_pinned_to_immutable_commits():
    registry = load_registry()
    for tool in registry["devkit"]["tools"].values():
        if tool["source"] == "github":
            assert len(tool["ref"]) == 40
            assert all(char in "0123456789abcdef" for char in tool["ref"])

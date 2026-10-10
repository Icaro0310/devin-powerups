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
        "related_count": 2,
        "entry_count": 23,
    }
    assert len(first["tools"]) == 19


def test_manifest_does_not_include_private_or_non_tool_repositories():
    manifest = exporter.build_manifest(load_registry())
    ids = {tool["id"] for tool in manifest["tools"]}

    assert "personal-agent-system" not in ids
    assert "devin-dashboard" not in ids
    assert "devin-learning" not in ids
    assert "devin-powerups" not in ids
    assert "awesome-devin" not in ids
    assert "qwenpaw-suite" not in ids
    assert "devin-judge" in ids
    descriptions = " ".join(tool["description"] for tool in manifest["tools"])
    assert "personal-agent-system" not in descriptions
    assert "devin-dashboard" not in descriptions
    assert "devin-learning" not in descriptions


def test_manifest_uses_pypi_names_and_real_cli_entrypoints():
    registry = load_registry()
    manifest = exporter.build_manifest(registry)
    tools = {tool["id"]: tool for tool in manifest["tools"]}

    assert tools["devin-assure"]["commands"] == ["devin-qa-pack"]
    assert tools["devin-orchestrator"]["package"] == "devin-fanout"
    assert tools["devin-orchestrator"]["commands"] == ["devin-orchestrator"]
    assert tools["devin-control"]["manager"] == "npm"
    assert tools["devin-control"]["runtime"] == "node>=20"
    assert tools["devin-brain"]["install_spec"].startswith("devin-memory[mcp]==")
    git_tools = {t["id"] for t in manifest["tools"] if t["requires_git"]}
    assert manifest["git_required_tools"] == sorted(git_tools)
    assert all(tools[name]["install_spec"].startswith("git+") for name in git_tools)
    assert tools["devin-office"]["install_spec"] is None
    assert tools["devin-office"]["status"] == "manual"


def test_install_spec_follows_the_registry_source():
    # The PyPI/npm flip jobs change `source` on their own, so the channel of a
    # given tool must not be frozen here; the spec shape must follow the source.
    registry = load_registry()
    manifest = exporter.build_manifest(registry)
    repos = {repo["name"]: repo for repo in registry["repositories"]}
    seen = set()
    for tool in manifest["tools"]:
        declared = registry["devkit"]["tools"][tool["id"]]
        seen.add(declared["source"])
        spec = tool["install_spec"]
        if declared["source"] == "pypi":
            assert spec.startswith(declared["package"]) and spec.endswith(f"=={declared['version']}")
        elif declared["source"] == "npm":
            assert spec == f"{declared['package']}@{declared['version']}"
        elif declared["source"] == "github":
            pkg_path = (repos[tool["id"]].get("package") or {}).get("path")
            if pkg_path:
                assert spec == f"git+{repos[tool['id']]['url']}.git@{declared['ref']}#subdirectory={pkg_path}"
            else:
                assert spec == f"{repos[tool['id']]['url']}/archive/{declared['ref']}.tar.gz"
        else:
            assert spec is None
    assert {"pypi", "npm", "manual"} <= seen


def test_profiles_only_reference_known_tools():
    manifest = exporter.build_manifest(load_registry())
    tools = {tool["id"] for tool in manifest["tools"]}

    for profile in manifest["profiles"].values():
        assert set(profile.get("tools", [])) <= tools
        assert set(profile.get("manual", [])) <= tools


def test_manifest_carries_artifact_interfaces_audiences_and_platforms():
    manifest = exporter.build_manifest(load_registry())
    tools = {tool["id"]: tool for tool in manifest["tools"]}

    assert tools["devin-office"]["artifact"] == "tool"
    assert tools["devin-office"]["interfaces"] == ["service", "dashboard"]
    assert tools["devin-control"]["artifact"] == "tool"
    assert "bridge" in tools["devin-control"]["interfaces"]
    assert "ai-engineers" in tools["devin-control"]["audiences"]
    assert tools["devin-assure"]["audiences"] == ["qa", "developers"]
    assert tools["devin-assure"]["platforms"] == ["windows", "linux"]
    assert tools["devin-assure"]["environments"]["corporate_windows"]["runtime"] == "local-only"
    assert tools["devin-control"]["environments"]["corporate_windows"]["delegation"] == "forbidden"
    assert tools["devin-judge"]["artifact"] == "tool"


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

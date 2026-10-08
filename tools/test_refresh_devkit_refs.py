"""Tests for refresh_devkit_refs.py repo-entry version sync (#30)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import refresh_devkit_refs as r  # noqa: E402


def registry(tools: dict, repos: list[dict]) -> dict:
    return {
        "version": 1,
        "generated": "2026-10-08",
        "devkit": {"tools": tools},
        "repositories": repos,
    }


def test_repo_entry_version_tracks_pypi(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: "0.1.1")
    reg = registry(
        {"poordjaevin": {"source": "pypi", "package": "poordjaevin", "version": "0.1.1"}},
        [{"name": "poordjaevin", "version": "0.1.0"}],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    report = r.refresh(path, "owner")
    out = json.loads(path.read_text())
    assert out["repositories"][0]["version"] == "0.1.1"
    assert any("repo entry" in c for c in report["changes"])


def test_repo_entry_without_version_field_gets_set(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: "0.2.0")
    reg = registry(
        {"devin-x": {"source": "pypi", "package": "devin-x", "version": "0.2.0"}},
        [{"name": "devin-x"}],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    r.refresh(path, "owner")
    assert json.loads(path.read_text())["repositories"][0]["version"] == "0.2.0"


def test_repo_entry_never_downgrades(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: "0.1.0")
    reg = registry(
        {"poordjaevin": {"source": "pypi", "package": "poordjaevin", "version": "0.1.0"}},
        [{"name": "poordjaevin", "version": "9.9.9"}],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    report = r.refresh(path, "owner")
    assert json.loads(path.read_text())["repositories"][0]["version"] == "9.9.9"
    assert not any("repo entry" in c for c in report["changes"])


def test_repo_entry_syncs_to_pin_ahead_of_upstream(tmp_path, monkeypatch):
    # Tool pin ahead of the fetched release: the repo entry still follows
    # the pin, not the (older) release.
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: "0.1.0")
    reg = registry(
        {"poordjaevin": {"source": "pypi", "package": "poordjaevin", "version": "0.1.1"}},
        [{"name": "poordjaevin", "version": "0.1.0"}],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    r.refresh(path, "owner")
    assert json.loads(path.read_text())["repositories"][0]["version"] == "0.1.1"


def test_repo_entry_syncs_when_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: None)
    reg = registry(
        {"poordjaevin": {"source": "pypi", "package": "poordjaevin", "version": "0.1.1"}},
        [{"name": "poordjaevin", "version": "0.1.0"}],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    r.refresh(path, "owner")
    assert json.loads(path.read_text())["repositories"][0]["version"] == "0.1.1"


def test_devkit_tool_without_repo_entry_is_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: "1.0.0")
    reg = registry(
        {"ghost": {"source": "pypi", "package": "ghost", "version": "0.1.0"}},
        [],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    report = r.refresh(path, "owner")
    assert json.loads(path.read_text())["devkit"]["tools"]["ghost"]["version"] == "1.0.0"
    assert "ghost.version: 0.1.0 -> 1.0.0" in report["changes"]


def test_github_tool_on_pypi_warns(tmp_path, monkeypatch):
    """A github-pinned tool whose package exists on PyPI triggers a
    warning; the declared channel itself is left alone."""
    monkeypatch.setattr(r, "_github_head", lambda o, n: "a" * 40)
    monkeypatch.setattr(r, "_github_newest_tag", lambda o, n: "0.1.0")
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: "0.1.0")
    reg = registry(
        {"devin-search": {"source": "github", "package": "devin-search",
                          "version": "0.1.0", "ref": "a" * 40}},
        [{"name": "devin-search", "version": "0.1.0"}],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    report = r.refresh(path, "owner")
    tool = json.loads(path.read_text())["devkit"]["tools"]["devin-search"]
    assert tool["source"] == "github"
    assert any("PyPI" in e for e in report["errors"])


def test_github_outage_still_warns_about_pypi(tmp_path, monkeypatch):
    """The publication watchdog runs even when GitHub lookups fail."""
    def boom(o, n):
        raise RuntimeError("api down")
    monkeypatch.setattr(r, "_github_head", boom)
    monkeypatch.setattr(r, "_pypi_newest_version", lambda pkg: "0.1.0")
    reg = registry(
        {"devin-graph": {"source": "github", "package": "devin-graph",
                         "version": "0.1.0", "ref": "a" * 40}},
        [{"name": "devin-graph", "version": "0.1.0"}],
    )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    report = r.refresh(path, "owner")
    assert any("PyPI" in e for e in report["errors"])

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import reconcile_registry as reconcile_module


def test_matching_tag_is_authoritative_when_release_object_lags(tmp_path: Path, monkeypatch):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({
        "repositories": [{
            "name": "devin-internals-spec",
            "visibility": "public",
            "version": "0.3.0",
            "tag": "v0.3.0",
        }]
    }), encoding="utf-8")
    monkeypatch.setattr(reconcile_module, "fetch_github_repos", lambda owner: {
        "devin-internals-spec": {
            "visibility": "public",
            "latestRelease": {"tagName": "v0.2.0"},
        }
    })
    monkeypatch.setattr(reconcile_module, "fetch_github_tags", lambda owner, name: ["v0.3.0", "v0.2.0"])
    monkeypatch.setattr(reconcile_module, "find_local_clones", lambda roots: {})

    report = reconcile_module.reconcile(registry_path, "Icaro0310", [], fetch_tags=True)

    assert report["stale_fields"] == []


def test_absorbed_system_alias_is_not_reported_as_missing_repository(tmp_path: Path, monkeypatch):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({
        "repositories": [
            {"name": "devin-powerups", "url": "https://github.com/Icaro0310/devin-powerups", "kind": "infra", "visibility": "public"},
            {"name": "devin-learning", "url": "https://github.com/Icaro0310/devin-powerups", "kind": "system", "visibility": "private", "status": "delivered"},
        ]
    }), encoding="utf-8")
    monkeypatch.setattr(reconcile_module, "fetch_github_repos", lambda owner: {
        "devin-powerups": {"visibility": "public", "latestRelease": None}
    })
    monkeypatch.setattr(reconcile_module, "fetch_github_tags", lambda owner, name: [])
    monkeypatch.setattr(reconcile_module, "find_local_clones", lambda roots: {"devin-powerups": tmp_path / "devin-powerups"})

    report = reconcile_module.reconcile(registry_path, "Icaro0310", [], fetch_tags=True)

    assert report["registry_only"] == []
    assert report["missing_local"] == []
    assert report["summary"]["registry_entries"] == 2

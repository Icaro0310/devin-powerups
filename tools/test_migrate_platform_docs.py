from __future__ import annotations

from pathlib import Path

import migrate_platform_docs as migration


def _registry() -> dict:
    return {
        "repositories": [
            {
                "name": "devin-alpha", "url": "https://github.com/TestOwner/devin-alpha",
                "kind": "project", "visibility": "public", "local_dir": "devin-alpha",
                "environments": {
                    "linux": {"supported": True, "runtime": "extended", "delegation": "optional", "external_dependencies": False},
                    "personal_windows": {"supported": True, "runtime": "extended", "delegation": "optional", "external_dependencies": False},
                    "corporate_windows": {"supported": True, "runtime": "local-only", "delegation": "forbidden", "external_dependencies": False},
                },
            },
            {
                "name": "devin-private", "url": "https://github.com/TestOwner/devin-private",
                "kind": "project", "visibility": "private", "local_dir": "devin-private",
            },
            {
                "name": "poordjaevin", "url": "https://github.com/Icaro0310/poordjaevin",
                "kind": "project", "visibility": "public",
                "local_dir": "../personal-agent-system/vendor/poordjaevin",
            },
        ],
        "devkit": {
            "git_required_tools": ["devin-alpha"],
            "tools": {
                "devin-alpha": {
                    "manager": "uv", "source": "github", "package": "devin-alpha",
                    "version": "0.1.0", "commands": ["devin-alpha"],
                    "runtime": "python>=3.10", "platforms": ["windows", "linux"],
                    "status": "source", "category": "qa", "ref": "a" * 40,
                }
            }
        },
    }


def test_dry_run_does_not_write_or_delete(tmp_path: Path):
    repo = tmp_path / "devin-alpha"
    repo.mkdir()
    (repo / "README.md").write_text("# devin-alpha\n", encoding="utf-8")
    (repo / "README.pt-BR.md").write_text("Português antigo\n", encoding="utf-8")
    before = (repo / "README.md").read_bytes()

    plan = migration.migrate(_registry(), tmp_path, apply=False)

    assert len(plan) == 1
    assert (repo / "README.md").read_bytes() == before
    assert (repo / "README.pt-BR.md").is_file()
    assert not (repo / "README.windows.md").exists()
    assert not (repo / "README.linux.md").exists()


def test_apply_creates_os_guides_and_removes_legacy_translation(tmp_path: Path):
    repo = tmp_path / "devin-alpha"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# devin-alpha\n\n**[Português (BR)](README.pt-BR.md)** · English\n",
        encoding="utf-8",
    )
    (repo / "README.pt-BR.md").write_text("Português antigo\n", encoding="utf-8")

    migration.migrate(_registry(), tmp_path, apply=True)

    assert not (repo / "README.pt-BR.md").exists()
    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "README.windows.md" in readme
    assert "awesome-devin" in readme
    windows = (repo / "README.windows.md").read_text(encoding="utf-8")
    corporate = (repo / "README.corporate-windows.md").read_text(encoding="utf-8")
    linux = (repo / "README.linux.md").read_text(encoding="utf-8")
    assert "uv tool install" in windows and "powershell" in windows
    assert "https://github.com/TestOwner/devin-alpha/archive/" in windows
    assert "Git on `PATH` for a Git dependency" in windows
    assert "## Troubleshooting" in windows and "reopen PowerShell" in windows
    assert "%APPDATA%" in windows
    assert "Personal Windows" in windows and "extended runtime" in windows
    assert "Corporate Windows" in corporate and "local-only environment" in corporate
    assert "## Corporate Windows specifics" in corporate
    assert "TLS inspection" in corporate and "No admin rights" in corporate
    assert "Offline/air-gapped" in corporate
    assert "## Personal Windows specifics" in windows
    assert "Microsoft Store" in windows and "Uninstall" in windows
    assert "uv tool install" in linux and "XDG_DATA_HOME" in linux
    assert "## Linux specifics" in linux and "Distros" in linux
    assert "systemd" in linux
    assert "## Troubleshooting" in linux and "uv` tools directory" in linux
    assert "https://github.com/TestOwner/devin-alpha/archive/" in linux
    migration.migrate(_registry(), tmp_path, apply=True)
    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert readme.count("README.windows.md") == 1
    assert readme.count("Part of the [awesome-devin]") == 1
    assert migration.check_platform_docs(_registry(), tmp_path) == []
    (repo / "README.windows.md").write_text("stale\n", encoding="utf-8")
    assert any("README.windows.md is missing or stale" in item for item in migration.check_platform_docs(_registry(), tmp_path))
    (repo / "README.corporate-windows.md").write_text("stale\n", encoding="utf-8")
    assert any("README.corporate-windows.md is missing or stale" in item for item in migration.check_platform_docs(_registry(), tmp_path))


def test_bridge_archive_guides_need_node_but_not_git():
    entry = {"name": "devin-bridge", "url": "https://github.com/Icaro0310/devin-bridge"}
    tool = {"manager": "npm", "source": "github", "package": "@icaro0310/devin-bridge", "version": "0.1.0", "ref": "a" * 40, "requires_git": False}
    windows = migration.render_guide(entry, tool, "windows")
    linux = migration.render_guide(entry, tool, "linux")

    assert "Node.js 20 or newer and npm" in windows
    assert "Git on `PATH`" not in windows
    assert "npm install --global" in linux
    assert "archive/" in linux


def test_office_guides_use_native_python_commands():
    entry = {"name": "devin-office", "description": "Dashboard"}
    windows = migration.render_guide(entry, {"manager": "manual"}, "windows")
    linux = migration.render_guide(entry, {"manager": "manual"}, "linux")

    assert "py -3 daemon.py --port 8788" in windows
    assert "python3 daemon.py --port 8788" in linux


def test_corporate_guide_uses_explicit_unsupported_reason():
    entry = {
        "name": "qwenpaw-suite",
        "environments": {
            "corporate_windows": {
                "supported": False,
                "runtime": "unavailable",
                "reason": "requires an external model runtime",
            }
        },
    }

    guide = migration.render_guide(entry, None, "windows", "corporate_windows")

    assert "not supported in Corporate Windows" in guide
    assert "requires an external model runtime" in guide

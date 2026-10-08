"""Tests for check_spec_pins.py (devin-powerups#25)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from check_spec_pins import (  # noqa: E402
    check,
    main,
    spec_constraint,
    version_allowed,
)


def write_pyproject(root: Path, name: str, dep: str | None) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    dep_line = f'    "{dep}",\n' if dep else ""
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\ndependencies = [\n{dep_line}]\n'
    )
    return repo


def write_registry(root: Path, names: dict[str, str]) -> None:
    hub = root / "devin-powerups"
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "registry.json").write_text(
        json.dumps(
            {
                "repositories": [
                    {"name": n, "visibility": v} for n, v in names.items()
                ]
            }
        )
    )


class TestConstraintParsing:
    def test_extracts_bounds(self, tmp_path):
        p = write_pyproject(tmp_path, "a", "devin-internals-spec>=0.3.0,<0.4.0")
        assert spec_constraint(p / "pyproject.toml") == ">=0.3.0,<0.4.0"

    def test_no_dependency_returns_none(self, tmp_path):
        p = write_pyproject(tmp_path, "a", None)
        assert spec_constraint(p / "pyproject.toml") is None


class TestVersionAllowed:
    @pytest.mark.parametrize(
        "constraint,version,expected",
        [
            (">=0.3.0,<0.4.0", "0.3.0", True),
            (">=0.3.0,<0.4.0", "0.3.9", True),
            (">=0.3.0,<0.4.0", "0.4.0", False),
            (">=0.3.0", "0.4.0", True),
            ("==0.3.0", "0.3.0", True),
            ("==0.3.0", "0.3.1", False),
            ("~=0.3.0", "0.3.5", True),
            ("~=0.3.0", "0.4.0", False),
            ("~=0.3", "0.4.0", True),
            ("", "99.0.0", True),
        ],
    )
    def test_bounds(self, constraint, version, expected):
        assert version_allowed(constraint, version) is expected


class TestCheck:
    def test_skips_repos_without_dependency(self, tmp_path):
        write_pyproject(tmp_path, "plain", "requests>=2")
        write_registry(tmp_path, {"plain": "public"})
        assert check(tmp_path, "9.9.9") == []

    def test_skips_non_registry_repos(self, tmp_path):
        write_pyproject(tmp_path, "dead-repo", "devin-internals-spec<0.1.0")
        write_registry(tmp_path, {"dead-repo": "private"})
        assert check(tmp_path, "9.9.9") == []

    def test_local_dir_outside_glob_is_checked(self, tmp_path):
        # poordjaevin layout: entry name resolves via local_dir, not glob.
        hub = tmp_path / "devin-powerups"
        hub.mkdir()
        outside = tmp_path.parent / "poordjaevin-clone"
        write_pyproject(outside.parent, "poordjaevin-clone",
                        "devin-internals-spec<0.1.0")
        (hub / "registry.json").write_text(json.dumps({"repositories": [
            {"name": "poordjaevin", "visibility": "public",
             "local_dir": "../poordjaevin-clone"},
        ]}))
        [r] = check(tmp_path, "9.9.9")
        assert r["repo"] == "poordjaevin" and r["allows_latest"] is False

    def test_flags_excluded_latest(self, tmp_path):
        write_pyproject(tmp_path, "a", "devin-internals-spec>=0.3.0,<0.4.0")
        write_registry(tmp_path, {"a": "public"})
        [r] = check(tmp_path, "0.4.0")
        assert r["repo"] == "a" and r["allows_latest"] is False


class TestMain:
    def test_exit_one_on_drift(self, tmp_path, capsys):
        write_pyproject(tmp_path, "a", "devin-internals-spec>=0.3.0,<0.4.0")
        write_registry(tmp_path, {"a": "public"})
        rc = main(["--root", str(tmp_path), "--latest", "0.4.0"])
        assert rc == 1
        assert "DRIFT" in capsys.readouterr().out

    def test_exit_zero_when_clean(self, tmp_path, capsys):
        write_pyproject(tmp_path, "a", "devin-internals-spec>=0.3.0")
        write_registry(tmp_path, {"a": "public"})
        assert main(["--root", str(tmp_path), "--latest", "0.4.0"]) == 0
        assert "ok:" in capsys.readouterr().out

    def test_json_output(self, tmp_path, capsys):
        write_pyproject(tmp_path, "a", "devin-internals-spec>=0.3.0")
        write_registry(tmp_path, {"a": "public"})
        main(["--root", str(tmp_path), "--latest", "0.4.0", "--json"])
        [r] = json.loads(capsys.readouterr().out)
        assert r == {
            "repo": "a",
            "constraint": ">=0.3.0",
            "latest": "0.4.0",
            "allows_latest": True,
        }

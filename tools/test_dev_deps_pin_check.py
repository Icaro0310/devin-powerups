"""Tests for dev-deps-pin-check.py — synthetic fixtures only.

The real ``dev-deps-pin-check.py`` filename contains hyphens, so it is
loaded via importlib (same convention as ``test_new_repo.py``).
"""

import importlib.util
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location(
    "dev_deps_pin_check", TOOLS / "dev-deps-pin-check.py"
)
ddp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ddp)

TOOLSET = {ddp.normalize(t) for t in ddp.DEFAULT_TOOLS}


def write_pyproject(root: Path, body: str) -> Path:
    p = root / "pyproject.toml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


def write_workflow(root: Path, body: str, name: str = "ci.yml") -> Path:
    p = root / ".github/workflows" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


class TestSpecClassification:
    @pytest.mark.parametrize(
        "spec,floating",
        [
            ("", True),
            ("*", True),
            (">=0.9", True),          # the drift-class canonical float
            (">0.9", True),
            ("!=0.9", True),
            (">=0.9,!=0.9.1", True),  # still no ceiling
            ("==*", True),
            ("==0.9.0", False),
            ("===0.9.0", False),
            ("~=0.9", False),
            ("~=0.9.0", False),
            (">=0.9,<0.10", False),   # bounded range
            (">=0.9,<=0.10", False),
            ("<=0.9", False),         # has a ceiling: cannot jump newer
            ("==0.9.*", False),
        ],
    )
    def test_spec_is_floating(self, spec, floating):
        assert ddp.spec_is_floating(spec) is floating

    @pytest.mark.parametrize(
        "ref,floating",
        [
            ("latest", True),
            ("main", True),
            ("master", True),
            ("", True),
            ("fix-some-bug", True),   # a moving branch, not a pin
            ("0.9.0", False),
            ("v0.9.0", False),
            ("278981a28ce3188b1e39527901f38254bf3aac89", False),
        ],
    )
    def test_ref_is_floating(self, ref, floating):
        assert ddp.ref_is_floating(ref) is floating


class TestPyproject:
    def test_bare_ruff_optional_deps_fails(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[project.optional-dependencies]\ndev = ["ruff"]\n',
        )
        findings = ddp.check_pyproject(p, TOOLSET)
        assert any("'ruff'" in f for f in findings)

    def test_pinned_ruff_passes(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[project.optional-dependencies]\ndev = ["ruff==0.9.0"]\n',
        )
        assert ddp.check_pyproject(p, TOOLSET) == []

    def test_bare_lower_bound_in_dependency_groups_fails(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[dependency-groups]\ndev = ["pytest>=8", "ruff>=0.9"]\n',
        )
        joined = "\n".join(ddp.check_pyproject(p, TOOLSET))
        assert "'pytest>=8'" in joined and "'ruff>=0.9'" in joined

    def test_bounded_range_passes(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[dependency-groups]\ndev = ["ruff>=0.9,<0.10", "pytest~=9.0"]\n',
        )
        assert ddp.check_pyproject(p, TOOLSET) == []

    def test_build_system_requires_checked(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[build-system]\nrequires = ["hatchling"]\n',
        )
        assert any("hatchling" in f for f in ddp.check_pyproject(p, TOOLSET))

    def test_tool_uv_dev_dependencies_checked(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[tool.uv]\ndev-dependencies = ["mypy"]\n',
        )
        assert any("mypy" in f for f in ddp.check_pyproject(p, TOOLSET))

    def test_hatch_env_deps_checked(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[tool.hatch.envs.default]\ndependencies = ["coverage>=7"]\n',
        )
        assert any("coverage" in f for f in ddp.check_pyproject(p, TOOLSET))

    def test_runtime_deps_whitelisted(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[project]\nname = "x"\n'
            'dependencies = ["requests", "flask>=2", "typer"]\n',
        )
        assert ddp.check_pyproject(p, TOOLSET) == []

    def test_markers_and_extras_stripped(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[project.optional-dependencies]\n'
            'dev = ["pytest[all]; python_version >= \'3.10\'"]\n',
        )
        assert ddp.check_pyproject(p, TOOLSET) != []

    def test_unparseable_pyproject_fails_closed(self, tmp_path):
        p = write_pyproject(tmp_path, "[project\nname = !!!\n")
        assert any("cannot parse" in f for f in ddp.check_pyproject(p, TOOLSET))

    def test_pep735_include_group_ignored(self, tmp_path):
        p = write_pyproject(
            tmp_path,
            '[dependency-groups]\ndev = [{include-group = "lint"}]\n'
            'lint = ["ruff==0.9.0"]\n',
        )
        assert ddp.check_pyproject(p, TOOLSET) == []


class TestRequirementsFiles:
    def test_bare_tool_fails(self, tmp_path):
        req = tmp_path / "requirements-dev.txt"
        req.write_text("bandit\n")
        assert any("bandit" in f for f in ddp.check_requirements_file(req, TOOLSET))

    def test_pinned_tool_passes(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("ruff==0.9.0\n")
        assert ddp.check_requirements_file(req, TOOLSET) == []

    def test_options_and_comments_skipped(self, tmp_path):
        req = tmp_path / "requirements-dev.txt"
        req.write_text(
            "# comment\n"
            "-r base.txt\n"
            "-e .\n"
            "--index-url https://example.com\n"
            "requests>=2  # runtime dep, whitelisted\n"
        )
        assert ddp.check_requirements_file(req, TOOLSET) == []

    def test_hash_continuation_joined(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text(
            "ruff \\\n    --hash=sha256:abcd \\\n    --hash=sha256:ef01\n"
        )
        findings = ddp.check_requirements_file(req, TOOLSET)
        assert len(findings) == 1 and ":1:" in findings[0]


class TestWorkflows:
    def test_pip_install_bare_tool_fails(self, tmp_path):
        wf = write_workflow(tmp_path, "steps:\n  - run: pip install ruff\n")
        assert any("'ruff'" in f for f in ddp.check_workflow(wf, TOOLSET))

    def test_pip_install_pinned_tool_passes(self, tmp_path):
        wf = write_workflow(
            tmp_path, "steps:\n  - run: pip install 'ruff==0.9.0' 'pytest~=9.0'\n"
        )
        assert ddp.check_workflow(wf, TOOLSET) == []

    def test_python_m_pip_continuation(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "steps:\n  - run: |\n      python -m pip install --upgrade \\\n"
            "        build twine\n",
        )
        joined = "\n".join(ddp.check_workflow(wf, TOOLSET))
        assert "'build'" in joined and "'twine'" in joined

    def test_uv_tool_run_without_version_fails(self, tmp_path):
        wf = write_workflow(
            tmp_path, "steps:\n  - run: uv tool run ruff check .\n"
        )
        assert any("'ruff'" in f for f in ddp.check_workflow(wf, TOOLSET))

    def test_uvx_at_version_passes(self, tmp_path):
        wf = write_workflow(tmp_path, "steps:\n  - run: uvx ruff@0.9.0 check .\n")
        assert ddp.check_workflow(wf, TOOLSET) == []

    def test_uvx_at_main_fails(self, tmp_path):
        wf = write_workflow(tmp_path, "steps:\n  - run: uvx ruff@main check .\n")
        assert ddp.check_workflow(wf, TOOLSET) != []

    def test_uvx_from_spec_pins_run(self, tmp_path):
        wf = write_workflow(
            tmp_path, "steps:\n  - run: uvx --from 'ruff==0.9.0' ruff check .\n"
        )
        assert ddp.check_workflow(wf, TOOLSET) == []

    def test_pipx_install_and_run(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "steps:\n  - run: pipx install ruff\n"
            "  - run: pipx run --spec 'mypy==1.15.0' mypy src/\n",
        )
        findings = ddp.check_workflow(wf, TOOLSET)
        assert len(findings) == 1 and "'ruff'" in findings[0]

    def test_ruff_action_without_version_fails(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "steps:\n"
            "  - uses: astral-sh/ruff-action@278981a28ce3188b1e39527901f38254bf3aac89 # v4.1.0\n"
            "    with:\n"
            "      args: check .\n"
            "  - run: pytest -q\n",
        )
        findings = ddp.check_workflow(wf, TOOLSET)
        assert len(findings) == 1 and "version" in findings[0]

    def test_ruff_action_with_version_passes(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "steps:\n"
            "  - uses: astral-sh/ruff-action@abc123\n"
            "    name: lint\n"
            "    with:\n"
            "      version: \"0.9.0\"\n"
            "      args: check .\n"
            "  - run: pytest -q\n",
        )
        assert ddp.check_workflow(wf, TOOLSET) == []

    def test_ruff_action_latest_version_fails(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "steps:\n"
            "  - uses: astral-sh/ruff-action@abc123\n"
            "    with:\n"
            "      version: latest\n",
        )
        assert ddp.check_workflow(wf, TOOLSET) != []

    def test_variable_and_non_tool_args_skipped(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "steps:\n  - run: pip install $PRE_INSTALL\n"
            "  - run: pip install -e \"${PACKAGE_DIR}[dev]\"\n"
            "  - run: pip install -U devin-redact requests\n",
        )
        assert ddp.check_workflow(wf, TOOLSET) == []


class TestMain:
    def test_exit_one_on_float(self, tmp_path, capsys):
        write_pyproject(tmp_path, '[project.optional-dependencies]\ndev = ["ruff"]\n')
        assert ddp.main([str(tmp_path)]) == 1
        assert "floating" in capsys.readouterr().err

    def test_exit_zero_when_clean(self, tmp_path, capsys):
        write_pyproject(tmp_path, '[project.optional-dependencies]\ndev = ["ruff==0.9.0"]\n')
        assert ddp.main([str(tmp_path)]) == 0
        assert "ok:" in capsys.readouterr().out

    def test_exit_two_on_missing_root(self):
        assert ddp.main(["/no/such/dir"]) == 2

    def test_tools_override(self, tmp_path):
        write_pyproject(
            tmp_path,
            '[project.optional-dependencies]\ndev = ["uv", "ruff==0.9.0"]\n',
        )
        assert ddp.main([str(tmp_path)]) == 0
        assert ddp.main([str(tmp_path), "--tools", "ruff,uv"]) == 1

    def test_selftest_passes(self):
        assert ddp.main(["--selftest"]) == 0


class TestTreeScan:
    def test_nested_pyproject_found(self, tmp_path):
        pkg = tmp_path / "packages/demo"
        write_pyproject(pkg, '[dependency-groups]\ndev = ["ruff"]\n')
        findings, nfiles = ddp.check_tree(tmp_path, TOOLSET)
        assert nfiles == 1 and len(findings) == 1

    def test_skip_dirs_pruned(self, tmp_path):
        cache = tmp_path / ".powerups-sensor/x"
        write_pyproject(cache, '[project.optional-dependencies]\ndev = ["ruff"]\n')
        findings, nfiles = ddp.check_tree(tmp_path, TOOLSET)
        assert nfiles == 0 and findings == []

    def test_template_dir_workflows_scanned(self, tmp_path):
        tmpl = tmp_path / "template"
        write_workflow(tmpl, "steps:\n  - run: uvx ruff check .\n")
        findings, _ = ddp.check_tree(tmp_path, TOOLSET)
        assert any("ruff" in f for f in findings)


class TestSelftestFixtures:
    """The --selftest path is exercised by ci.yml like adapters-check;
    these tests pin the classifier behavior selftest asserts on."""

    def test_clean_fixture_has_every_site(self, tmp_path):
        (tmp_path / ".github/workflows").mkdir(parents=True)
        write_pyproject(
            tmp_path,
            '[build-system]\nrequires = ["setuptools>=77,<82"]\n'
            '[project.optional-dependencies]\ndev = ["ruff~=0.9.0", "pytest==8.3.5"]\n'
            '[dependency-groups]\nlint = ["mypy>=1,<2"]\n',
        )
        write_workflow(
            tmp_path,
            "steps:\n"
            "  - run: uvx ruff@0.9.0 check .\n"
            "  - uses: astral-sh/ruff-action@abc123\n"
            "    with:\n      version: \"0.9.0\"\n",
        )
        findings, nfiles = ddp.check_tree(tmp_path, TOOLSET)
        assert findings == [] and nfiles == 2

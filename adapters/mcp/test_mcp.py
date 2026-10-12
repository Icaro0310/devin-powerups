"""Contract tests for the <pkg> MCP face.

Skeleton — copy into the package's tests/ dir. Assertions every MCP
adapter must pass, in order of importance:

1. payload parity: do_<verb>() == json.loads(`<pkg-cli> <verb> --json`)
   on the package's synthetic fixtures (the same devin_internals.fixtures
   conftest data the CLI tests use — never real user data);
2. failure paths the CLI maps to a non-zero exit -> {error, detail} dicts;
3. pyproject exposes the `<pkg>-mcp` entry point and the `mcp` extra.
"""

import importlib
import json
import tomllib
from pathlib import Path

import pytest

# Fix to the real module, e.g. `from devin_janitor import mcp_server` or
# importlib.import_module("devin_janitor.mcp_server"). As shipped this
# raises ModuleNotFoundError — loud, never silently green.
mcp_server = importlib.import_module("<pkg_mod>.mcp_server")

PKG_DIR = Path(__file__).resolve().parents[1]


def test_do_status_matches_cli_json(cli_runner):
    # cli_runner: the package's own fixture that runs the CLI and returns
    # parsed --json output on synthetic fixtures.
    assert mcp_server.do_status() == cli_runner("status", "--json")


def test_failure_returns_error_dict(cli_runner):
    # Point the tool at a fixture the CLI must reject (missing input dir,
    # bad id — whatever makes `check` exit non-zero in this package).
    # The assert is unconditional: a passing payload here means the
    # fixture was not actually failing, which is itself a bug.
    payload = mcp_server.do_status("<invalid-or-missing-fixture>")
    assert set(payload) == {"error", "detail"}


def test_build_server_registers_tools():
    # CI installs [dev] only, not [mcp] — skip instead of failing when the
    # mcp package is absent. Accepted fallback, not the target state: one
    # job installing .[dev,mcp] SHOULD run this registration smoke test.
    pytest.importorskip("mcp")
    app = mcp_server.build_server()
    # Existence is not enough — the declared tool must be registered and
    # reachable through the server API. The listing entry point varies
    # across MCP SDK versions (app.list_tools(), @app.list_tools
    # decorator, server.tools); use whichever this package's SDK exposes.
    tools = getattr(app, "tools", None) or getattr(app, "_tools", {})
    assert "<pkg>_status" in {getattr(t, "name", t) for t in tools}


def test_pyproject_exposes_mcp_entry_point_and_extra():
    pyproject = tomllib.loads((PKG_DIR / "pyproject.toml").read_text())
    scripts = pyproject["project"]["scripts"]
    assert "<pkg-cli>-mcp" in scripts
    assert "mcp" in pyproject["project"]["optional-dependencies"]


# For packages with a mutating half (Rule 1), also assert the module
# source never references the mutating core function:
#
#   def test_mcp_never_imports_mutating_core():
#       src = Path(mcp_server.__file__).read_text()
#       assert "do_mutate" not in src

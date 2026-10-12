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


def _call(fn, *args, **kwargs):
    """Apply the same exception -> {error, detail} mapping the tool layer
    wraps every do_* in (mirrors devin-janitor's _call helper)."""
    try:
        return fn(*args, **kwargs)
    except Exception as error:  # noqa: BLE001 — mirrors the tool boundary
        return mcp_server._err(error)


def test_failure_returns_error_dict(monkeypatch):
    # ARRANGE a failing fixture before calling — required, not optional:
    # the assert is unconditional, so a passing payload means the fixture
    # was not actually failing, which is itself a bug in this test.
    # Shipped default: patch the tool callable to raise — deterministic on
    # every adapter, no signature knowledge needed.
    # Alternatives the real adapters use (pick what do_<verb> supports):
    #   * corrupt the synthetic fixture — devin-janitor writes
    #     b"not sqlite" into sessions_db, then calls
    #     _call(do_classify, data_dir=str(devin_dir.root));
    #   * pass an unreadable path arg when do_<verb> accepts one, e.g.
    #     _call(do_dry_run, data_dir=str(tmp_path / "missing")) —
    #     re-add tmp_path to the signature if you take that route.
    def _raise(*_args, **_kwargs):
        raise RuntimeError("arranged failure — exercises the error mapping")

    monkeypatch.setattr(mcp_server, "do_status", _raise)
    payload = _call(mcp_server.do_status)
    assert set(payload) == {"error", "detail"}


def _registered_tool_names(server) -> set:
    # Listing entry point the ecosystem's MCP tests use (devin-memory's
    # test_mcp_server.py): FastMCP (mcp 1.x) and MCPServer (mcp 2.x) both
    # hold registered tools at _tool_manager._tools, keyed by tool name —
    # synchronous, unlike the SDKs' async list_tools().
    manager = getattr(server, "_tool_manager", None)
    return set(getattr(manager, "_tools", {}) or {})


def test_build_server_registers_tools():
    # CI installs [dev] only, not [mcp] — skip instead of failing when the
    # mcp package is absent. Accepted fallback, not the target state: one
    # job installing .[dev,mcp] SHOULD run this registration smoke test.
    pytest.importorskip("mcp")
    app = mcp_server.build_server()
    # Existence is not enough — the declared tool must be registered under
    # the name the SDK derives from the def in mcp_server.py (pkg_status
    # here; keep this literal in sync when the tool is renamed).
    assert "pkg_status" in _registered_tool_names(app)


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

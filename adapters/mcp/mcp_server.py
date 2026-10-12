"""<pkg> MCP adapter — thin shell over <pkg_mod>'s core API.

Skeleton — canonical location: packages/<pkg>/src/<pkg_mod>/mcp_server.py
(inside src/ so it ships in the wheel; the plugin manifest launches it
via `uvx --from '<pkg>[mcp]' <pkg>-mcp`).

Rule 1 (docs/adapter-checklist.md): only read/dry-run surfaces are
exposed here. Mutating CLI commands are never registered as tools and
mutating core functions are never imported — restricted packages add a
source-scan test asserting exactly that.
"""

from __future__ import annotations

# do_<verb> functions are pure logic: each returns the same payload as
# `<pkg-cli> <verb> --json`, as a dict. Unit-test them without the mcp
# package or a running server. Injectable seams (now_ms=, which=,
# runner=) stay keyword-only and are NOT exposed as tool parameters.
# Optional path args use "" defaults (MCP clients send empty strings
# more reliably than null) and resolve to None -> platform default.


def do_status() -> dict:
    """Return the `<pkg-cli> status --json` payload as a dict."""
    from .core import status  # the package's own logic — never reimplemented

    return status()


def _err(error: Exception) -> dict:
    """Failure contract: errors are data, never raised across the wire."""
    return {"error": type(error).__name__, "detail": str(error)[:500]}


def _make_app(name: str):
    """MCP server app across SDK versions — mcp 2.x renamed FastMCP to
    MCPServer; both expose .tool() and .run(transport="stdio").

    Adapt the registration call in build_server() to whichever API the
    installed mcp version exposes (@app.tool() vs app.add_tool(...)).
    """
    try:  # mcp 2.x
        from mcp.server.mcpserver import MCPServer

        return MCPServer(name)
    except ImportError:
        pass
    try:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP

        return FastMCP(name)
    except ImportError as e:
        raise ImportError(
            "The MCP server needs the 'mcp' extra: "
            "pip install '<pkg>[mcp]'"
        ) from e


def build_server():
    """Register the read-only tools; each wraps a do_* in try/except."""
    app = _make_app("<pkg>")

    @app.tool()
    def pkg_status() -> dict:
        """Read-only: <pkg> status payload (same as `status --json`)."""
        try:
            return do_status()
        except Exception as e:  # contract: errors are returned, not raised
            return _err(e)

    return app


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()

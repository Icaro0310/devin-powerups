"""Contract test for the <pkg> plugin manifest.

Skeleton — the manifest lives at
packages/<pkg>/adapters/.devin-plugin/plugin.json; copy this test into
the package's tests/ dir (or next to the manifest) and fix MANIFEST_PATH.
"""

import json
from pathlib import Path

MANIFEST_PATH = (
    Path(__file__).resolve().parent / ".devin-plugin" / "plugin.json"
)


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_is_valid_json_with_identity():
    m = _manifest()
    assert m["name"] == "<pkg>"
    assert m["description"]
    assert m["repository"].startswith("https://github.com/Icaro0310/")


def test_mcp_server_points_at_mcp_entry_point():
    # Omit `mcpServers` entirely when the package has no MCP surface —
    # never stub a server that does not exist.
    server = _manifest().get("mcpServers", {}).get("<pkg>")
    assert server is None or server["args"][-1].endswith("-mcp")


# When the manifest sits at its canonical location
# (adapters/.devin-plugin/plugin.json), also assert the skill face is
# shipped alongside it:
#
#   root = MANIFEST_PATH.parent.parent
#   assert (root / "skills" / "<pkg>" / "SKILL.md").is_file()

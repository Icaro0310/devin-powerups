from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HUB = ROOT.parent
sys.path.insert(0, str(ROOT))

import render_compatibility


REGISTRY = HUB / "registry.json"


def test_matrix_uses_registry_environment_metadata():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rendered = render_compatibility.render_compatibility_matrix(registry)

    assert "| Artifact | Linux | Personal Windows | Corporate Windows |" in rendered
    assert "`devin-history`](https://github.com/Icaro0310/devin-explore) | Extended | Extended | Local only |" in rendered
    assert "`qwenpaw-suite`](https://github.com/Icaro0310/qwenpaw-suite) | Extended | Extended | Unsupported |" in rendered


def test_matrix_excludes_non_executable_resources():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rendered = render_compatibility.render_compatibility_matrix(registry)

    assert "awesome-devin" not in rendered


def test_check_reports_stale_matrix(tmp_path):
    path = tmp_path / "COMPATIBILITY.md"
    path.write_text("stale\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "render_compatibility.py"), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "stale compatibility matrix" in result.stderr

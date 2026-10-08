"""Tests for analyze_baseline.py (devin-powerups#22)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_baseline import (  # noqa: E402
    ci_attribution,
    funnel,
    main,
    per_repo,
    to_markdown,
)


def snap(date: str, repos: dict) -> dict:
    return {"date": date, "repos": repos}


def repo(**kw):
    base = {
        "stars": 0,
        "forks": 0,
        "open_issues": 0,
        "open_prs": 0,
        "views_14d": 0,
        "unique_visitors_14d": 0,
        "clones_14d": 0,
        "unique_cloners_14d": 0,
        "ci": {"runs_14d": 0, "pass_rate_14d": 1.0},
    }
    base.update(kw)
    return base


class TestPerRepo:
    def test_deltas(self):
        a = snap("2026-10-08", {"x": repo(stars=1, clones_14d=10)})
        b = snap("2026-12-03", {"x": repo(stars=4, clones_14d=30)})
        [r] = per_repo(a, b)
        assert r["stars"] == 3 and r["clones_14d"] == 20

    def test_added_and_removed(self):
        a = snap("2026-10-08", {"gone": repo()})
        b = snap("2026-12-03", {"new": repo()})
        rows = {r["repo"]: r["status"] for r in per_repo(a, b)}
        assert rows == {"gone": "removed", "new": "added"}


class TestFunnel:
    def test_clone_rate(self):
        r = repo(unique_visitors_14d=10, unique_cloners_14d=4)
        assert funnel(r)["clone_rate"] == 0.4

    def test_no_visitors(self):
        assert funnel(repo()) == {}


class TestAttribution:
    def test_ci_dominated(self):
        r = repo(clones_14d=500, unique_cloners_14d=20)
        r["ci"]["runs_14d"] = 50
        assert ci_attribution(r) == "ci-dominated?"

    def test_human_driven(self):
        r = repo(clones_14d=30, unique_cloners_14d=25)
        assert ci_attribution(r) == "human-driven"

    def test_unclear(self):
        r = repo(clones_14d=40, unique_cloners_14d=20)
        r["ci"]["runs_14d"] = 30
        assert ci_attribution(r) == "mixed/unclear"


class TestMain:
    def test_markdown_and_json(self, tmp_path, capsys):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps(snap("2026-10-08", {"x": repo(stars=1)})))
        b.write_text(json.dumps(snap("2026-12-03", {"x": repo(stars=3)})))
        assert main([str(a), str(b)]) == 0
        md = capsys.readouterr().out
        assert "2026-10-08 -> 2026-12-03" in md and "| x |" in md
        assert main([str(a), str(b), "--json"]) == 0
        [r] = json.loads(capsys.readouterr().out)
        assert r["repo"] == "x" and r["stars"] == 2

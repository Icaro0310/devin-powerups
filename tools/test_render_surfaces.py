#!/usr/bin/env python3
"""Tests for render_surfaces.py — the semantic-surface generator."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_surfaces as rs  # noqa: E402


def repo(**kw) -> dict:
    base = {
        "name": "devin-x",
        "url": "https://github.com/Icaro0310/devin-x",
        "description": "Does x.",
        "visibility": "public",
        "public": True,
        "artifact": "tool",
    }
    base.update(kw)
    return base


REGISTRY = {
    "version": 99,
    "repositories": [
        repo(name="devin-metrics", track="observe", nature="product",
             audiences=["qa", "operations"], interfaces=["cli", "dashboard"]),
        repo(name="devin-evals", track="assure", nature="product",
             audiences=["qa"], interfaces=["cli", "library"]),
        repo(name="devin-redact", track="guard", nature="product",
             audiences=["security"], interfaces=["cli"]),
        repo(name="devin-devkit", track="platform", nature="distribution",
             audiences=["maintainers"], interfaces=["installer"]),
        repo(name="awesome-devin", track="navigation", nature="surface",
             artifact="resource", audiences=["end-users"], interfaces=["docs"]),
        repo(name="private-thing", visibility="private", public=False,
             track="observe", nature="product"),
    ],
}


class TestPublicEntries(unittest.TestCase):
    def test_private_excluded(self):
        names = [r["name"] for r in rs.public_entries(REGISTRY)]
        self.assertNotIn("private-thing", names)
        self.assertEqual(len(names), 5)


class TestIntentMap(unittest.TestCase):
    def test_tracks_in_intent_order(self):
        out = rs.render_intent_map(REGISTRY)
        order = [out.index(v) for v in ("**Understand**", "**Verify**", "**Control**", "**Build**", "**Navigate**")]
        self.assertEqual(order, sorted(order))

    def test_tools_under_track(self):
        out = rs.render_intent_map(REGISTRY)
        self.assertIn("`devin-metrics`", out)
        self.assertIn("`devin-evals`", out)
        self.assertNotIn("private-thing", out)

    def test_empty_track_skipped(self):
        reg = {"version": 1, "repositories": [repo(track="observe")]}
        out = rs.render_intent_map(reg)
        self.assertIn("**Understand**", out)
        self.assertNotIn("**Build**", out)


class TestBrowse(unittest.TestCase):
    def test_audience_grouping(self):
        out = rs.render_browse(REGISTRY, "audiences")
        self.assertIn("**QA engineers**", out)
        self.assertIn("`devin-evals`", out)

    def test_interface_grouping(self):
        out = rs.render_browse(REGISTRY, "interfaces")
        self.assertIn("**Python library**", out)
        self.assertIn("`devin-evals`", out)

    def test_bad_axis(self):
        with self.assertRaises(ValueError):
            rs.render_browse(REGISTRY, "bogus")


class TestToolBlock(unittest.TestCase):
    def test_block_fields(self):
        r = repo(track="assure", nature="product",
                 audiences=["qa"], interfaces=["cli", "library"])
        out = rs.render_tool_block(r)
        self.assertIn("Track: Verify", out)
        self.assertIn("Nature: product", out)
        self.assertIn("For: QA engineers", out)
        self.assertIn("Interface: CLI / Python library", out)
        self.assertIn("awesome-devin", out)


class TestCounts(unittest.TestCase):
    def test_counts(self):
        c = rs.counts(REGISTRY)
        self.assertEqual(c["entries"], 6)
        self.assertEqual(c["public_entries"], 5)
        self.assertEqual(c["tracks"]["observe"], 1)
        self.assertNotIn("related", c["tracks"])


class TestMain(unittest.TestCase):
    def test_cli_block(self):
        import tempfile
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as f:
            json.dump(REGISTRY, f)
            path = f.name
        rc = rs.main(["block", "devin-evals", "--registry", path])
        self.assertEqual(rc, 0)

    def test_cli_unknown_repo(self):
        import tempfile
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as f:
            json.dump(REGISTRY, f)
            path = f.name
        rc = rs.main(["block", "nope", "--registry", path])
        self.assertEqual(rc, 2)

    def _registry_file(self) -> str:
        import tempfile
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as f:
            json.dump(REGISTRY, f)
        return f.name

    def test_cli_block_rejects_private_repo(self):
        rc = rs.main(["block", "private-thing", "--registry",
                      self._registry_file()])
        self.assertEqual(rc, 2)

    def test_cli_json_rejected_for_markdown_surfaces(self):
        rc = rs.main(["intent", "--json", "--registry",
                      self._registry_file()])
        self.assertEqual(rc, 2)

    def test_unknown_track_renders_instead_of_dropping(self):
        reg = {"version": 1, "repositories": [
            repo(name="devin-spec", track="foundation"),
        ]}
        out = rs.render_intent_map(reg)
        self.assertIn("**Foundation**", out)
        self.assertIn("`devin-spec`", out)
        c = rs.counts(reg)
        self.assertEqual(c["tracks"]["foundation"], 1)


if __name__ == "__main__":
    unittest.main()

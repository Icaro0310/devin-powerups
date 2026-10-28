#!/usr/bin/env python3
"""Tests for repo-seo-audit.py — gh is always mocked; no live calls.

The filename contains hyphens, so the module is loaded via importlib.
``subprocess.run`` is the only network edge and is patched in every test.

Run:
    python tools/test_repo_seo_audit.py
"""

import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location(
    "repo_seo_audit", TOOLS / "repo-seo-audit.py"
)
repo_seo_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repo_seo_audit)


def gh_payload(repos):
    """CompletedProcess carrying a gh repo list JSON response."""
    return subprocess.CompletedProcess(
        args=["gh"], returncode=0, stdout=json.dumps(repos), stderr=""
    )


REPOS = [
    {
        "name": "devin-beta",
        "description": "A documented repo",
        "homepageUrl": "https://example.dev",
        "repositoryTopics": [{"name": "python"}, {"name": "devin"}],
        "visibility": "PUBLIC",
    },
    {
        "name": "devin-alpha",
        "description": None,
        "homepageUrl": "",
        "repositoryTopics": None,
        "visibility": "PUBLIC",
    },
    {
        "name": "devin-private",
        "description": None,
        "homepageUrl": "",
        "repositoryTopics": None,
        "visibility": "PRIVATE",
    },
]


class AuditRepoTests(unittest.TestCase):
    def test_complete_repo_has_no_gap(self):
        finding = repo_seo_audit.audit_repo(REPOS[0])
        self.assertEqual(finding["name"], "devin-beta")
        self.assertEqual(finding["topics"], ["devin", "python"])
        self.assertEqual(finding["missing"], [])
        self.assertFalse(finding["gap"])

    def test_missing_fields_flag_a_gap(self):
        finding = repo_seo_audit.audit_repo(REPOS[1])
        self.assertTrue(finding["gap"])
        self.assertEqual(
            finding["missing"], ["description", "topics", "homepage"]
        )

    def test_topic_shapes_both_supported(self):
        rest_shape = {"name": "x", "topics": ["a", "b"], "visibility": "PUBLIC"}
        self.assertEqual(repo_seo_audit._topic_names(rest_shape), ["a", "b"])
        self.assertEqual(
            repo_seo_audit._topic_names(
                {"repositoryTopics": [{"name": "y"}, {"other": 1}, "z"]}
            ),
            ["y", "z"],
        )
        self.assertEqual(
            repo_seo_audit._topic_names({"repositoryTopics": None}), []
        )

    def test_blank_fields_count_as_missing(self):
        finding = repo_seo_audit.audit_repo(
            {
                "name": "devin-blank",
                "description": "   ",
                "homepageUrl": " ",
                "repositoryTopics": [],
            }
        )
        self.assertEqual(
            finding["missing"], ["description", "topics", "homepage"]
        )


class AuditTests(unittest.TestCase):
    def test_public_only_sorted_by_name(self):
        with mock.patch.object(
            repo_seo_audit, "_run_gh", return_value=REPOS
        ) as gh:
            findings = repo_seo_audit.audit("TestOwner")
        gh.assert_called_once()
        argv = gh.call_args.args[0]
        self.assertEqual(argv[:4], ["repo", "list", "TestOwner", "--limit"])
        self.assertIn("--json", argv)
        self.assertEqual(
            [f["name"] for f in findings], ["devin-alpha", "devin-beta"]
        )

    def test_visibility_compare_is_case_insensitive(self):
        repos = [dict(REPOS[0], name="lower", visibility="public")]
        with mock.patch.object(repo_seo_audit, "_run_gh", return_value=repos):
            findings = repo_seo_audit.audit("TestOwner")
        self.assertEqual([f["name"] for f in findings], ["lower"])


class RenderTests(unittest.TestCase):
    def test_text_report_keeps_the_pas_shape(self):
        findings = [
            {
                "name": "devin-beta",
                "description": "A documented repo",
                "topics": ["devin", "python"],
                "homepage": "https://example.dev",
                "missing": [],
                "gap": False,
            },
            {
                "name": "devin-alpha",
                "description": "",
                "topics": [],
                "homepage": "",
                "missing": ["description", "topics", "homepage"],
                "gap": True,
            },
        ]
        text = repo_seo_audit.render_text(findings)
        lines = text.splitlines()
        self.assertEqual(lines[0], "total: 2")
        self.assertEqual(
            lines[1],
            f"{'devin-beta':35} | t= 2 | A documented repo",
        )
        self.assertEqual(
            lines[2],
            f"{'devin-alpha':35} | t= 0 | -  <-- GAP "
            "(missing: description, topics, homepage)",
        )

    def test_empty_report_is_just_the_total(self):
        self.assertEqual(repo_seo_audit.render_text([]), "total: 0")


class MainTests(unittest.TestCase):
    def _run_main(self, argv, repos=REPOS):
        stdout, stderr = io.StringIO(), io.StringIO()
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return gh_payload(repos)

        with mock.patch.object(
            repo_seo_audit.subprocess, "run", side_effect=fake_run
        ), mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            rc = repo_seo_audit.main(argv)
        return rc, calls, stdout.getvalue(), stderr.getvalue()

    def test_text_report_and_gh_argv(self):
        rc, calls, out, _ = self._run_main(["--owner", "TestOwner"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0][:4], ["gh", "repo", "list", "TestOwner"]
        )
        self.assertIn("total: 2", out)
        self.assertIn("devin-alpha", out)
        self.assertIn("<-- GAP", out)
        self.assertNotIn("devin-private", out)

    def test_json_flag_prints_findings(self):
        rc, _, out, _ = self._run_main(["--json", "--owner", "T"])
        self.assertEqual(rc, 0)
        findings = json.loads(out)
        self.assertEqual([f["name"] for f in findings],
                         ["devin-alpha", "devin-beta"])
        self.assertTrue(findings[0]["gap"])
        self.assertFalse(findings[1]["gap"])

    def test_out_writes_findings_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "audit.json"
            rc, _, _, _ = self._run_main(
                ["--out", str(out_file), "--owner", "T"]
            )
            self.assertEqual(rc, 0)
            findings = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(len(findings), 2)

    def test_missing_gh_fails_loudly(self):
        stderr = io.StringIO()
        with mock.patch.object(
            repo_seo_audit.subprocess,
            "run",
            side_effect=FileNotFoundError("gh"),
        ), mock.patch("sys.stderr", stderr):
            rc = repo_seo_audit.main([])
        self.assertEqual(rc, 2)
        self.assertIn("gh", stderr.getvalue())

    def test_gh_failure_fails_loudly(self):
        stderr = io.StringIO()

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="auth required"
            )

        with mock.patch.object(
            repo_seo_audit.subprocess, "run", side_effect=fake_run
        ), mock.patch("sys.stderr", stderr):
            rc = repo_seo_audit.main([])
        self.assertEqual(rc, 2)
        self.assertIn("auth required", stderr.getvalue())

    def test_bad_json_fails_loudly(self):
        stderr = io.StringIO()
        with mock.patch.object(
            repo_seo_audit.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                args=["gh"], returncode=0, stdout="not json", stderr=""
            ),
        ), mock.patch("sys.stderr", stderr):
            rc = repo_seo_audit.main([])
        self.assertEqual(rc, 2)
        self.assertIn("error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

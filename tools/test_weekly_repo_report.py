#!/usr/bin/env python3
"""Tests for weekly_repo_report.py — all HTTP/SMTP is mocked; no live calls.

Run:
    python tools/test_weekly_repo_report.py
"""

import io
import json
import ssl
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import http.client
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import weekly_repo_report as wrr

NOW = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def commit(sha, date, message, repo="x"):
    return {
        "sha": sha,
        "html_url": f"https://github.com/Icaro0310/{repo}/commit/{sha}",
        "commit": {
            "message": message,
            "committer": {"date": date},
            "author": {"date": date},
        },
    }


def registry(tmpdir, repos):
    path = Path(tmpdir) / "registry.json"
    path.write_text(json.dumps({"repositories": repos}), encoding="utf-8")
    return path


def project(name, visibility="public", kind="project", url=None):
    return {
        "name": name,
        "url": url or f"https://github.com/Icaro0310/{name}",
        "kind": kind,
        "visibility": visibility,
    }


def opener_returning(payload):
    def opener(request, timeout):
        return FakeResponse(payload)

    return opener


class RegistryFilterTests(unittest.TestCase):
    def test_only_public_projects_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = registry(
                tmp,
                [
                    project("devin-powerups", visibility="private", kind="infra"),
                    project("devin-alpha"),
                    project("devin-beta"),
                    project("devin-hidden", visibility="private"),
                    project("devin-docs", kind="docs"),
                ],
            )
            names = [r["name"] for r in wrr.load_public_projects(path)]
        self.assertEqual(names, ["devin-alpha", "devin-beta"])

    def test_rejects_non_github_url(self):
        for bad in (
            "https://evil.example.com/o/r",
            "http://github.com/o/r",
            "javascript:alert(1)",
            "notaurl",
        ):
            with tempfile.TemporaryDirectory() as tmp:
                path = registry(tmp, [project("devin-bad", url=bad)])
                with self.assertRaises(ValueError, msg=bad):
                    wrr.load_public_projects(path)

    def test_rejects_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = registry(tmp, [{"kind": "project", "visibility": "public"}])
            with self.assertRaises(ValueError):
                wrr.load_public_projects(path)
        with tempfile.TemporaryDirectory() as tmp:
            path = registry(tmp, [{"name": "x", "kind": "project", "visibility": "public"}])
            with self.assertRaises(ValueError):
                wrr.load_public_projects(path)


class FetchTests(unittest.TestCase):
    def test_since_param_and_client_side_date_filter(self):
        repo = project("devin-alpha")
        since = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse(
                [
                    commit("a" * 40, "2026-09-29T08:00:00Z", "new commit"),
                    commit("b" * 40, "2026-09-23T09:59:00Z", "just too old"),
                ]
            )

        result = wrr.fetch_commits(repo, since, NOW, timeout=9, opener=opener)
        self.assertIsNone(result["error"])
        self.assertIn("since=2026-09-23T10%3A00%3A00Z", captured["url"])
        self.assertIn("per_page=100", captured["url"])
        self.assertIn("Icaro0310/devin-alpha/commits", captured["url"])
        self.assertEqual(captured["timeout"], 9)
        self.assertEqual([c["sha"] for c in result["commits"]], ["aaaaaaa"])
        self.assertEqual(result["commits"][0]["day"], "2026-09-29")
        self.assertEqual(result["commits"][0]["subject"], "new commit")

    def test_same_day_newest_first(self):
        repo = project("devin-alpha")

        def opener(request, timeout):
            return FakeResponse(
                [
                    commit("a" * 40, "2026-09-29T08:00:00Z", "morning"),
                    commit("b" * 40, "2026-09-29T20:00:00Z", "evening"),
                    commit("c" * 40, "2026-09-28T12:00:00Z", "yesterday"),
                ]
            )

        result = wrr.fetch_commits(repo, NOW - timedelta(days=7), NOW, opener=opener)
        self.assertEqual([c["sha"] for c in result["commits"]], ["bbbbbbb", "aaaaaaa", "ccccccc"])

    def test_pagination_follows_pages(self):
        repo = project("devin-alpha")
        seen_pages = []
        page1 = [
            commit(f"{i:040x}", "2026-09-29T08:00:00Z", f"c{i}") for i in range(100)
        ]
        page2 = [commit("f" * 40, "2026-09-28T08:00:00Z", "last")]

        def opener(request, timeout):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
            page = int(query["page"][0])
            seen_pages.append(page)
            return FakeResponse(page1 if page == 1 else page2)

        result = wrr.fetch_commits(repo, NOW - timedelta(days=7), NOW, opener=opener)
        self.assertEqual(seen_pages, [1, 2])
        self.assertEqual(result["fetched"], 101)
        self.assertFalse(result["lower_bound"])

    def test_pagination_bound_flags_lower_bound(self):
        repo = project("devin-alpha")
        full = [
            commit(f"{i:040x}", "2026-09-29T08:00:00Z", f"c{i}") for i in range(100)
        ]

        def opener(request, timeout):
            return FakeResponse(full)

        result = wrr.fetch_commits(repo, NOW - timedelta(days=7), NOW, opener=opener)
        self.assertEqual(result["fetched"], 300)  # 3 pages x 100, then stopped
        self.assertTrue(result["lower_bound"])

    def test_http_error_includes_sanitized_status_and_message(self):
        repo = project("devin-alpha")

        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                403,
                "Forbidden",
                hdrs=None,
                fp=io.BytesIO(b'{"message": "API rate limit exceeded"}'),
            )

        result = wrr.fetch_commits(repo, NOW, NOW, opener=opener)
        self.assertIn("HTTP 403", result["error"])
        self.assertIn("rate limit or forbidden", result["error"])
        self.assertIn("API rate limit exceeded", result["error"])

    def test_http_429_and_http_exception_handled(self):
        repo = project("devin-alpha")

        def opener_429(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many", hdrs=None, fp=None)

        def opener_broken(request, timeout):
            raise http.client.RemoteDisconnected("gone")

        result = wrr.fetch_commits(repo, NOW, NOW, opener=opener_429)
        self.assertIn("HTTP 429", result["error"])
        result = wrr.fetch_commits(repo, NOW, NOW, opener=opener_broken)
        self.assertIn("RemoteDisconnected", result["error"])

    def test_url_error_becomes_error_not_exception(self):
        repo = project("devin-alpha")

        def opener(request, timeout):
            raise urllib.error.URLError("boom")

        result = wrr.fetch_commits(repo, NOW, NOW, opener=opener)
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["commits"], [])

    def test_non_list_payload_is_error(self):
        repo = project("devin-alpha")
        result = wrr.fetch_commits(repo, NOW, NOW, opener=opener_returning({"message": "Not Found"}))
        self.assertEqual(result["error"], "Not Found")

    def test_multiline_message_uses_first_line(self):
        repo = project("devin-alpha")
        result = wrr.fetch_commits(
            repo,
            NOW - timedelta(days=7),
            NOW,
            opener=opener_returning(
                [commit("c" * 40, "2026-09-30T01:00:00Z", "subject line\n\nbody text")]
            ),
        )
        self.assertEqual(result["commits"][0]["subject"], "subject line")

    def test_offsite_commit_link_is_dropped(self):
        repo = project("devin-alpha")
        evil = commit("e" * 40, "2026-09-29T08:00:00Z", "click me")
        evil["html_url"] = "https://evil.example.com/phish?x=1"
        result = wrr.fetch_commits(repo, NOW - timedelta(days=7), NOW, opener=opener_returning([evil]))
        self.assertEqual(result["commits"][0]["url"], f"{repo['url']}/commit/{'e' * 40}")

        other_repo = commit("d" * 40, "2026-09-29T08:00:00Z", "x")
        other_repo["html_url"] = "https://github.com/Icaro0310/other/commit/" + "d" * 40
        result = wrr.fetch_commits(
            repo, NOW - timedelta(days=7), NOW, opener=opener_returning([other_repo])
        )
        # link outside this repo's path is replaced by the canonical URL
        self.assertEqual(result["commits"][0]["url"], f"{repo['url']}/commit/{'d' * 40}")


class CollectAndRenderTests(unittest.TestCase):
    def _report(self, tmp, payloads):
        path = registry(tmp, [project(name) for name in payloads])

        def opener(request, timeout):
            for name, payload in payloads.items():
                if f"/{name}/commits" in request.full_url:
                    if isinstance(payload, Exception):
                        raise payload
                    return FakeResponse(payload)
            raise AssertionError(f"unexpected url {request.full_url}")

        return wrr.collect_report(path, days=7, max_commits=2, now=NOW, opener=opener)

    def test_empty_error_and_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._report(
                tmp,
                {
                    "devin-empty": [],
                    "devin-broken": urllib.error.URLError("dns fail"),
                    "devin-busy": [
                        commit(f"{i:040x}", "2026-09-29T08:00:00Z", f"commit {i}", repo="devin-busy")
                        for i in range(4)
                    ],
                },
            )
            html_out = wrr.render_html(report)

        repos = {r["name"]: r for r in report["repos"]}
        self.assertEqual(len(repos["devin-empty"]["commits"]), 0)
        self.assertIsNotNone(repos["devin-broken"]["error"])
        self.assertEqual(len(repos["devin-busy"]["commits"]), 2)
        self.assertEqual(repos["devin-busy"]["truncated"], 2)

        self.assertIn("No commits in this window.", html_out)
        self.assertIn("Fetch error:", html_out)
        self.assertIn("2 more", html_out)
        # one repo failing does not suppress the others
        self.assertIn("devin-empty", html_out)
        self.assertIn("devin-busy", html_out)

    def test_subject_html_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._report(
                tmp,
                {
                    "devin-xss": [
                        commit(
                            "d" * 40,
                            "2026-09-28T08:00:00Z",
                            "fix <script>alert(1)</script> & <b>x</b>",
                            repo="devin-xss",
                        )
                    ]
                },
            )
            html_out = wrr.render_html(report)

        self.assertNotIn("<script>alert(1)</script>", html_out)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_out)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html_out)

    def test_report_does_not_include_private_hub(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = registry(
                tmp,
                [
                    project("devin-powerups", visibility="private", kind="infra"),
                    project("devin-alpha"),
                ],
            )

            def opener(request, timeout):
                self.assertIn("/devin-alpha/commits", request.full_url)
                return FakeResponse([])

            report = wrr.collect_report(path, days=7, now=NOW, opener=opener)
        self.assertEqual([r["name"] for r in report["repos"]], ["devin-alpha"])

    def test_all_failed_renders_error_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._report(
                tmp,
                {
                    "devin-a": urllib.error.URLError("down"),
                    "devin-b": urllib.error.URLError("down"),
                },
            )
            html_out = wrr.render_html(report)
            self.assertEqual(html_out.count("Fetch error:"), 2)
            self.assertIn("2 fetch error(s)", html_out)


class SendEmailTests(unittest.TestCase):
    def _env(self):
        return {
            "MAILERSEND_SMTP_HOST": "smtp.mailersend.net",
            "MAILERSEND_SMTP_PORT": "587",
            "MAILERSEND_SMTP_USER": "smtp-login@example.test",
            "MAILERSEND_SMTP_PASSWORD": "test-password",
            "REPORT_SENDER": "Report Bot <reports@example.test>",
        }

    def test_send_uses_verified_tls_and_configured_sender(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_file = Path(tmp) / "r.html"
            html_file.write_text("<html>report</html>", encoding="utf-8")
            with mock.patch.dict("os.environ", self._env(), clear=False), mock.patch(
                "smtplib.SMTP"
            ) as smtp_cls:
                smtp = smtp_cls.return_value.__enter__.return_value
                rc = wrr.send_report_email(html_file, "reports@example.com")

        self.assertEqual(rc, 0)
        # STARTTLS must use a default (verified) SSL context
        (kwargs,) = [call.kwargs for call in smtp.starttls.call_args_list]
        context = kwargs.get("context")
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        # From is a configured sender, not the SMTP login
        sent = smtp.send_message.call_args.args[0]
        self.assertEqual(sent["From"], "Report Bot <reports@example.test>")
        self.assertNotEqual(sent["From"], "smtp-login@example.test")
        self.assertEqual(sent["To"], "reports@example.com")
        smtp.login.assert_called_once_with("smtp-login@example.test", "test-password")

    def test_send_missing_env_returns_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_file = Path(tmp) / "r.html"
            html_file.write_text("<html/>", encoding="utf-8")
            with mock.patch.dict("os.environ", {}, clear=True):
                rc = wrr.send_report_email(html_file, "reports@example.com")
        self.assertEqual(rc, 2)

    def test_send_missing_sender_returns_warning(self):
        env = self._env()
        env.pop("REPORT_SENDER")
        with tempfile.TemporaryDirectory() as tmp:
            html_file = Path(tmp) / "r.html"
            html_file.write_text("<html/>", encoding="utf-8")
            with mock.patch.dict("os.environ", env, clear=True), mock.patch(
                "smtplib.SMTP"
            ) as smtp_cls:
                rc = wrr.send_report_email(html_file, "reports@example.com")
        self.assertEqual(rc, 2)
        smtp_cls.assert_not_called()

    def test_send_invalid_port_returns_warning(self):
        env = self._env()
        env["MAILERSEND_SMTP_PORT"] = "not-a-port"
        with tempfile.TemporaryDirectory() as tmp:
            html_file = Path(tmp) / "r.html"
            html_file.write_text("<html/>", encoding="utf-8")
            with mock.patch.dict("os.environ", env, clear=True), mock.patch(
                "smtplib.SMTP"
            ) as smtp_cls:
                rc = wrr.send_report_email(html_file, "reports@example.com")
        self.assertEqual(rc, 2)
        smtp_cls.assert_not_called()

    def test_send_smtp_failure_returns_nonzero(self):
        import smtplib

        with tempfile.TemporaryDirectory() as tmp:
            html_file = Path(tmp) / "r.html"
            html_file.write_text("<html/>", encoding="utf-8")
            with mock.patch.dict("os.environ", self._env(), clear=True), mock.patch(
                "smtplib.SMTP"
            ) as smtp_cls:
                smtp = smtp_cls.return_value.__enter__.return_value
                smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad creds")
                rc = wrr.send_report_email(html_file, "reports@example.com")
        self.assertEqual(rc, 1)


class GithubTokenTests(unittest.TestCase):
    def test_github_token_env_adds_auth_header(self):
        repo = project("devin-alpha")
        seen = {}

        def opener(request, timeout):
            seen["auth"] = request.get_header("Authorization")
            return FakeResponse([])

        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "synthetic-token"}):
            wrr.fetch_commits(repo, NOW - timedelta(days=7), NOW, opener=opener)
        self.assertEqual(seen["auth"], "Bearer synthetic-token")

        def opener2(request, timeout):
            seen["auth2"] = request.get_header("Authorization")
            return FakeResponse([])

        with mock.patch.dict("os.environ", {}, clear=True):
            wrr.fetch_commits(repo, NOW - timedelta(days=7), NOW, opener=opener2)
        self.assertIsNone(seen["auth2"])


class CliTests(unittest.TestCase):
    def test_rejects_non_positive_limits(self):
        for argv in (["--days", "0"], ["--max-commits", "-1"], ["--timeout", "0"]):
            with self.assertRaises(SystemExit):
                wrr.main(argv)

    def test_send_requires_to(self):
        with self.assertRaises(SystemExit):
            wrr.main(["--send", "x.html"])

    def test_all_fetch_failures_write_artifact_and_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = registry(tmp, [project("devin-a"), project("devin-b")])
            out = Path(tmp) / "r.html"
            failing = {"name": "x", "url": "u", "commits": [], "error": "boom",
                       "fetched": 0, "lower_bound": False}
            fake_report = {
                "generated": NOW,
                "since": NOW - timedelta(days=7),
                "days": 7,
                "repos": [dict(failing, name="devin-a"), dict(failing, name="devin-b")],
            }
            with mock.patch.object(wrr, "collect_report", return_value=fake_report):
                rc = wrr.main(["--registry", str(path), "--out", str(out)])
            self.assertEqual(rc, 1)
            self.assertTrue(out.exists())
            self.assertIn("Fetch error:", out.read_text(encoding="utf-8"))

    def test_collect_report_rejects_non_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = registry(tmp, [project("devin-a")])
            with self.assertRaises(ValueError):
                wrr.collect_report(path, days=0)


if __name__ == "__main__":
    unittest.main()

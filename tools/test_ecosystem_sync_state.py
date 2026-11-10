"""Tests for ecosystem_sync: --state-md snapshot, freshness/silence
sensors, heartbeat-ledger matrix and workflow freshness roll-up."""
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import ecosystem_sync as es


def _row(product, channel, local, remote, state):
    return es.Row(product=product, channel=channel, local=local,
                  remote=remote, state=state)


class WriteStateMdTests(unittest.TestCase):
    def test_writes_sections_and_rows(self):
        out = Path(self._tmpdir()) / "state.md"
        rows = [
            _row("devin-x", "pypi", "0.1.0", "0.1.0", "ok"),
            _row("devin-y", "open-vsx", "0.2.0", "0.2.1", "drift"),
        ]
        es.write_state_md(
            out, rows,
            [("ollama (via devin-vm)", "ok")],
            [("devin-state", 106, "feat: rotate")],
            datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc),
        )
        text = out.read_text()
        self.assertIn("## Published versions", text)
        self.assertIn("| devin-y | open-vsx | 0.2.0 | 0.2.1 | drift |", text)
        self.assertIn("ollama (via devin-vm): ok", text)
        self.assertIn("**devin-y** (open-vsx)", text)
        self.assertIn("devin-state#106 — feat: rotate", text)
        self.assertIn("do not edit", text)

    def test_empty_drift_and_prs(self):
        out = Path(self._tmpdir()) / "state.md"
        es.write_state_md(out, [_row("a", "pypi", "1", "1", "ok")], [], [],
                          datetime.now(timezone.utc))
        text = out.read_text()
        self.assertIn("- none", text)

    def _tmpdir(self):
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return d


class CollectOpenPrsTests(unittest.TestCase):
    def test_parses_and_sorts(self):
        payload = json.dumps([{"number": 3, "title": "t"}, {"number": 7, "title": "x"}])
        proc = mock.Mock(returncode=0, stdout=payload)
        with mock.patch.object(es.subprocess, "run", return_value=proc):
            prs = es.collect_open_prs({"devin-a": "Icaro0310"}, 10)
        self.assertEqual(prs, [("devin-a", 3, "t"), ("devin-a", 7, "x")])

    def test_failure_skips_repo(self):
        with mock.patch.object(es.subprocess, "run",
                               side_effect=OSError("no gh")):
            self.assertEqual(es.collect_open_prs({"devin-a": "o"}, 10), [])
        proc = mock.Mock(returncode=1, stdout="")
        with mock.patch.object(es.subprocess, "run", return_value=proc):
            self.assertEqual(es.collect_open_prs({"devin-a": "o"}, 10), [])


if __name__ == "__main__":
    unittest.main()


class CollectCiConfigTests(unittest.TestCase):
    def _gh(self, owner, repo, path, timeout):
        if path == "/actions/secrets":
            if repo in ("no-secret", "bare"):
                return {"secrets": []}
            return {"secrets": [{"name": "TS_AUTHKEY"}]}
        if repo == "no-secret":
            return [{"name": "review-fallback.yml"}]
        if repo in ("no-wf", "bare"):
            return [{"name": "test.yml"}]
        return [{"name": "review-fallback.yml"}, {"name": "test.yml"}]

    def test_states(self):
        repos = {"ok-r": "o", "no-wf": "o", "no-secret": "o", "bare": "o"}
        with mock.patch.object(es, "_gh_api", side_effect=self._gh):
            rows = {r.product: r for r in es.collect_ci_config(repos, 10)}
        self.assertEqual(rows["ok-r"].state, "ok")
        self.assertEqual(rows["no-wf"].state, "drift")
        self.assertEqual(rows["no-wf"].local, "secret only")
        self.assertEqual(rows["no-secret"].local, "workflow only")
        self.assertEqual(rows["bare"].local, "neither")


NOW = 1_800_000_000.0  # fixed epoch for freshness age math


class FreshnessAgeMathTests(unittest.TestCase):
    def test_ok_drift_boundary(self):
        ok = es._fresh_row("dispatcher", "r", 48,
                           (NOW - 47 * 3600, True, ""), NOW)
        self.assertEqual((ok.state, ok.local), ("ok", "47h"))
        self.assertEqual(ok.channel, "freshness")
        edge = es._fresh_row("dispatcher", "r", 48,
                             (NOW - 48 * 3600, True, ""), NOW)
        self.assertEqual(edge.state, "ok")  # <= threshold is still ok
        drift = es._fresh_row("dispatcher", "r", 48,
                              (NOW - 49 * 3600, True, ""), NOW)
        self.assertEqual((drift.state, drift.local), ("drift", "49h"))
        self.assertIn(drift.state, es.DRIFT_STATES)
        self.assertEqual(drift.remote, "<=2d")

    def test_never_and_unavailable(self):
        never = es._fresh_row("scout", "r", 96, (None, True, ""), NOW)
        self.assertEqual((never.state, never.local), ("drift", "never"))
        unavail = es._fresh_row("scout", "r", 96,
                                (None, False, "no jsonl"), NOW)
        self.assertEqual(unavail.state, "unavailable")
        self.assertEqual(unavail.note, "no jsonl")


class DispatcherProbeTests(unittest.TestCase):
    def _tmpdb(self, columns="finished_at", epoch=NOW - 3600, rows=1):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        db = Path(d) / "site" / "qwenpaw-queue" / "qwenpaw-queue.db"
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(db)
        conn.execute(f"CREATE TABLE tasks (id TEXT, {columns} REAL)")
        for i in range(rows):
            conn.execute("INSERT INTO tasks VALUES (?, ?)", (f"t{i}", epoch))
        conn.commit()
        conn.close()
        return Path(d)

    def test_sqlite_finished_at(self):
        root = self._tmpdb()
        epoch, determined, note = es._probe_dispatcher([root], 5)
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 3600)

    def test_sqlite_completed_at_variant(self):
        root = self._tmpdb(columns="completed_at")
        epoch, determined, _ = es._probe_dispatcher([root], 5)
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 3600)

    def test_empty_table_is_never(self):
        root = self._tmpdb(rows=0)
        epoch, determined, note = es._probe_dispatcher([root], 5)
        self.assertTrue(determined)
        self.assertIsNone(epoch)
        self.assertIn("no finished task", note)

    def test_nothing_found_unavailable(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        epoch, determined, _ = es._probe_dispatcher([Path(d)], 5)
        self.assertFalse(determined)
        self.assertIsNone(epoch)


class SlackLedgerProbeTests(unittest.TestCase):
    def _env(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        # HOME is patched too so the real ~/.local/state ledger can't leak in
        return d, mock.patch.dict(
            es.os.environ, {"XDG_STATE_HOME": d, "HOME": d})

    def test_missing_ledger_unavailable(self):
        d, patcher = self._env()
        with patcher:
            epoch, determined, note = es._probe_slack_output()
        self.assertFalse(determined)
        self.assertIsNone(epoch)
        self.assertIn("no send ledger", note)

    def test_old_ledger_drifts(self):
        d, patcher = self._env()
        ledger = Path(d) / "devin" / "slack-notify" / "last-sent.json"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"ts": NOW - 80 * 3600}))
        with patcher:
            probe = es._probe_slack_output()
        epoch, determined, _ = probe
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 80 * 3600)
        row = es._fresh_row("slack-output", "r", 72, probe, NOW)
        self.assertEqual((row.state, row.local), ("drift", "80h"))

    def test_fresh_ledger_ok_and_jsonl(self):
        d, patcher = self._env()
        ledger = Path(d) / "devin" / "slack-notify" / "last-sent.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            '{"ts": 1}\n' + json.dumps({"ts": NOW - 3600}) + "\n")
        with patcher:
            epoch, determined, _ = es._probe_slack_output()
        self.assertTrue(determined)
        self.assertAlmostEqual(epoch, NOW - 3600)


class OpenSilenceIssuesTests(unittest.TestCase):
    def test_dedup_by_component_name(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if cmd[1:3] == ["issue", "list"]:
                return mock.Mock(returncode=0, stdout=json.dumps(
                    [{"number": 9,
                      "title": "[silence] dispatcher: 60h without output"}]))
            return mock.Mock(returncode=0, stdout="https://x/1\n", stderr="")

        rows = [
            es.Row("dispatcher", "freshness", "60h", "<=2d", "drift", "o/r"),
            es.Row("scout", "freshness", "5d", "<=4d", "drift", "o/r"),
        ]
        with mock.patch.object(es.subprocess, "run", side_effect=fake_run):
            messages = es.open_silence_issues(rows, 5)
        created = [c for c in calls if c[1:3] == ["issue", "create"]]
        self.assertEqual(len(created), 1)  # dispatcher deduped, scout filed
        self.assertIn("[silence] scout: 5d without output", created[0])
        self.assertTrue(any("skipped" in m for m in messages))
        self.assertTrue(any("opened" in m for m in messages))

    def test_label_created_before_issue(self):
        def fake_run(cmd, **kw):
            return mock.Mock(returncode=0, stdout="[]" if "list" in cmd else "u")

        rows = [es.Row("heartbeat", "freshness", "3h", "<=1h", "drift", "o/r")]
        with mock.patch.object(es.subprocess, "run", side_effect=fake_run) as m:
            es.open_silence_issues(rows, 5)
        kinds = [(cmd[1], cmd[2]) for cmd in
                 (c[0][0] for c in m.call_args_list) if len(cmd) > 2]
        self.assertIn(("label", "create"), kinds)
        self.assertIn(("issue", "create"), kinds)


class OpenDriftIssuesTests(unittest.TestCase):
    def test_comment_timeout_does_not_abort_other_repos(self):
        # A gh issue comment that raises (timeout/OSError) must be
        # recorded per-repo and must not kill the whole --issue sweep.
        def fake_run(cmd, **kw):
            repo = cmd[cmd.index("--repo") + 1]
            if repo in {"o/bad", "o/err"} and cmd[1:3] == ["issue", "comment"]:
                if repo == "o/bad":
                    raise es.subprocess.TimeoutExpired(cmd, kw.get("timeout"))
                raise OSError("gh missing")
            if repo in {"o/bad", "o/err"}:
                if cmd[1:3] == ["issue", "list"]:
                    return mock.Mock(returncode=0, stdout=json.dumps(
                        [{"number": 3, "title": "drift report"}]))
                # issue view: body lacks the new row -> comment path
                return mock.Mock(returncode=0, stdout="old report",
                                 stderr="")
            if cmd[1:3] == ["issue", "list"]:
                return mock.Mock(returncode=0, stdout="[]")
            return mock.Mock(returncode=0, stdout="https://x/9\n",
                             stderr="")

        rows = [
            es.Row(product="prod-a", channel="pypi", local="0.1",
                   remote="0.2", state="drift", repo="o/bad"),
            es.Row(product="prod-b", channel="pypi", local="0.1",
                   remote="0.2", state="drift", repo="o/err"),
            es.Row(product="prod-c", channel="pypi", local="0.1",
                   remote="0.2", state="drift", repo="o/good"),
        ]
        with mock.patch.object(es.subprocess, "run", side_effect=fake_run):
            messages = es.open_drift_issues(rows, 5)
        self.assertTrue(any("o/bad: issue comment failed" in m
                            for m in messages))
        self.assertTrue(any("o/err: issue comment failed" in m
                            for m in messages))
        # sorted order puts o/good last — its issue was still opened
        self.assertTrue(any("o/good: opened" in m for m in messages))


class CollectFreshnessTests(unittest.TestCase):
    def _collect(self, matrix, heartbeats=None, evidence="", workflow_rows=None,
                 roots=None, probes=None):
        """collect_freshness with every probe/evidence seam mocked."""
        probe_defaults = {name: (None, False, "x") for name in
                          ("_probe_dispatcher", "_probe_slack_output",
                           "_probe_scout", "_probe_review_fallback",
                           "_probe_heartbeat")}
        probe_defaults.update(probes or {})
        stack = [mock.patch.object(es, n, return_value=v)
                 for n, v in probe_defaults.items()]
        stack += [
            mock.patch.object(es, "_load_silence_matrix",
                              return_value=matrix),
            mock.patch.object(es, "_read_heartbeats",
                              return_value=heartbeats or {}),
            mock.patch.object(es, "_install_evidence",
                              return_value=evidence),
            mock.patch.object(es, "_workflow_freshness",
                              return_value=workflow_rows or []),
        ]
        for p in stack:
            p.start()
        self.addCleanup(mock.patch.stopall)
        return es.collect_freshness(
            roots if roots is not None else [Path("/nonexistent")],
            {}, 5, now=NOW)

    def test_five_rows_one_per_component(self):
        matrix = {t: {"threshold_h": h, "repo": "o/r"}
                  for t, h, _ in es._FRESHNESS_CHECKS}
        rows = self._collect(matrix)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r.channel == "freshness" for r in rows))
        self.assertTrue(all(r.state == "unavailable" for r in rows))
        self.assertEqual(
            {r.product for r in rows},
            {"dispatcher", "slack-output", "scout", "review-fallback",
             "heartbeat"})

    def test_special_probe_wins_over_ledger(self):
        # "dispatcher" exists in the ledger AND the matrix, but the
        # bespoke probe result (unavailable) must win.
        matrix = {"dispatcher": {"threshold_h": 48, "repo": "o/r"}}
        heartbeats = {"dispatcher": {
            "last_success_at": NOW - 60, "last_failure_at": None,
            "last_detail": ""}}
        rows = self._collect(matrix, heartbeats)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].state, "unavailable")  # bespoke probe


class HeartbeatLedgerTests(unittest.TestCase):
    def _env(self, d):
        return mock.patch.dict(es.os.environ,
                               {"XDG_STATE_HOME": d, "HOME": d},
                               clear=False)

    def test_parses_success_failure_and_detail(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        ledger = Path(d) / "devin" / "heartbeats.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("\n".join([
            '{"ts": %d, "tool": "office", "event": "success", "detail": "tick"}'
            % (NOW - 7200),
            '{"ts": %d, "tool": "office", "event": "failure", "detail": "boom"}'
            % (NOW - 3600),
            '{"ts": %d, "tool": "office", "event": "success", "detail": "ok2"}'
            % (NOW - 1800),
            '{"ts": %d, "tool": "queue-api", "event": "success"}' % NOW,
        ]) + "\n")
        with self._env(d):
            beats = es._read_heartbeats([])
        self.assertEqual(set(beats), {"office", "queue-api"})
        office = beats["office"]
        self.assertAlmostEqual(office["last_success_at"], NOW - 1800)
        self.assertAlmostEqual(office["last_failure_at"], NOW - 3600)
        self.assertEqual(office["last_detail"], "ok2")  # newest event wins
        self.assertIsNone(beats["queue-api"]["last_failure_at"])

    def test_malformed_lines_skipped(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        ledger = Path(d) / "devin" / "heartbeats.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("\n".join([
            "not json at all",
            '{"tool": "no-ts"}',
            '{"ts": "not-an-epoch", "tool": "bad-ts", "event": "success"}',
            '{"ts": 40, "tool": "counter", "event": "success"}',
            '["a", "list"]',
            '{"ts": %d, "tool": "good", "event": "success"}' % NOW,
            "",
        ]) + "\n")
        with self._env(d):
            beats = es._read_heartbeats([])
        self.assertEqual(set(beats), {"good"})
        self.assertAlmostEqual(beats["good"]["last_success_at"], NOW)

    def test_merges_env_file_and_root_candidates(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        env_file = Path(d) / "elsewhere.jsonl"
        env_file.write_text(
            '{"ts": %d, "tool": "a", "event": "success"}\n' % (NOW - 100))
        root = Path(d) / "root"
        nested = (root / ".local" / "state" / "devin" /
                  "heartbeats.jsonl")
        nested.parent.mkdir(parents=True)
        nested.write_text(
            '{"ts": %d, "tool": "b", "event": "failure", "detail": "x"}\n'
            % (NOW - 200))
        env = {"XDG_STATE_HOME": str(Path(d) / "no-xdg"),
               "HOME": str(Path(d) / "no-home"),
               "DEVIN_HEARTBEAT_FILE": str(env_file)}
        with mock.patch.dict(es.os.environ, env, clear=False):
            beats = es._read_heartbeats([root])
        self.assertEqual(set(beats), {"a", "b"})
        self.assertAlmostEqual(beats["b"]["last_failure_at"], NOW - 200)

    def test_no_files_returns_empty(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        env = {"XDG_STATE_HOME": d, "HOME": d,
               "DEVIN_HEARTBEAT_FILE": str(Path(d) / "absent.jsonl")}
        with mock.patch.dict(es.os.environ, env, clear=False):
            self.assertEqual(es._read_heartbeats([Path(d)]), {})


class MatrixToolRowTests(CollectFreshnessTests):
    def test_silence_drift_and_ok(self):
        matrix = {"session-sweep": {"threshold_h": 3, "repo": "o/r"},
                  "office": {"threshold_h": 0.25, "repo": "o/r"}}
        heartbeats = {
            "session-sweep": {"last_success_at": NOW - 10 * 3600,
                              "last_failure_at": None, "last_detail": ""},
            "office": {"last_success_at": NOW - 5 * 60,
                       "last_failure_at": None, "last_detail": "tick"},
        }
        rows = {r.product: r for r in self._collect(matrix, heartbeats)}
        self.assertEqual((rows["session-sweep"].state,
                          rows["session-sweep"].local), ("drift", "10h"))
        self.assertEqual((rows["office"].state, rows["office"].local),
                         ("ok", "5m"))
        self.assertEqual(rows["office"].remote, "<=15m")

    def test_err_streak_gets_extra_row(self):
        matrix = {"session-sweep": {"threshold_h": 3, "repo": "o/r"}}
        heartbeats = {"session-sweep": {
            "last_success_at": NOW - 2 * 3600,
            "last_failure_at": NOW - 1800,
            "last_detail": "exit 1"}}
        rows = self._collect(matrix, heartbeats)
        self.assertEqual(len(rows), 2)
        base, errors = rows
        self.assertEqual(base.state, "ok")  # success still fresh
        self.assertEqual(errors.product, "session-sweep (errors)")
        self.assertEqual((errors.state, errors.local),
                         ("drift", "err streak"))
        self.assertIn(errors.state, es.DRIFT_STATES)
        self.assertIn("exit 1", errors.note)

    def test_only_failures_is_never_plus_errors(self):
        matrix = {"queue-worker": {"threshold_h": 0.25, "repo": "o/r"}}
        heartbeats = {"queue-worker": {
            "last_success_at": None,
            "last_failure_at": NOW - 600,
            "last_detail": "crash"}}
        rows = self._collect(matrix, heartbeats)
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0].state, rows[0].local), ("drift", "never"))
        self.assertEqual(rows[1].product, "queue-worker (errors)")

    def test_absent_installed_is_never_drift(self):
        matrix = {"session-janitor": {"threshold_h": 30, "repo": "o/r"}}
        rows = self._collect(
            matrix, heartbeats={},
            evidence="*/30 * * * * /home/x/bin/session-janitor --run\n")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].state, rows[0].local), ("drift", "never"))
        self.assertIn("never emitted", rows[0].note)

    def test_absent_installed_via_path_glob(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        script = Path(d) / "repo" / "scripts" / "queue-api"
        script.parent.mkdir(parents=True)
        script.write_text("#!/bin/sh\n")
        matrix = {"queue-api": {"threshold_h": 0.25, "repo": "o/r"}}
        rows = self._collect(matrix, heartbeats={}, roots=[Path(d)])
        self.assertEqual((rows[0].state, rows[0].local), ("drift", "never"))

    def test_absent_not_installed_is_unavailable(self):
        matrix = {"vm-sync": {"threshold_h": 192, "repo": "o/r"}}
        rows = self._collect(matrix, heartbeats={}, evidence="")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].state, "unavailable")
        self.assertNotIn(rows[0].state, es.DRIFT_STATES)

    def test_fractional_threshold_boundary(self):
        matrix = {"office": {"threshold_h": 0.25, "repo": "o/r"}}
        ok = self._collect(matrix, {"office": {
            "last_success_at": NOW - 14 * 60, "last_failure_at": None,
            "last_detail": ""}})[0]
        drift = self._collect(matrix, {"office": {
            "last_success_at": NOW - 16 * 60, "last_failure_at": None,
            "last_detail": ""}})[0]
        self.assertEqual(ok.state, "ok")
        self.assertEqual(drift.state, "drift")


class WorkflowFreshnessTests(unittest.TestCase):
    OWNERS = {"repo-a": "o", "repo-b": "o"}

    def _gh(self, runs_by_key, default="missing"):
        def fake(cmd, **kw):
            repo = cmd[cmd.index("--repo") + 1]
            wf = cmd[cmd.index("--workflow") + 1]
            payload = runs_by_key.get((repo, wf), default)
            if payload == "missing":
                return mock.Mock(returncode=1, stdout="",
                                 stderr="could not find any workflows "
                                        "named x")
            if payload is None:
                return mock.Mock(returncode=1, stdout="",
                                 stderr="HTTP 401 auth required")
            return mock.Mock(returncode=0, stdout=json.dumps(payload),
                             stderr="")
        return fake

    def _iso(self, epoch):
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat()

    def test_aggregates_across_repos(self):
        runs = {
            ("o/repo-a", "ci.yml"): [
                {"createdAt": self._iso(NOW - 3600), "conclusion": "success"}],
            ("o/repo-b", "ci.yml"): [
                {"createdAt": self._iso(NOW - 2 * 3600),
                 "conclusion": "success"}],
        }
        with mock.patch.object(es.subprocess, "run",
                               side_effect=self._gh(runs)):
            rows = {r.product: r for r in
                    es._workflow_freshness(self.OWNERS, 5, now=NOW)}
        self.assertEqual((rows["ci"].state,
                          rows["ci"].local), ("ok", "1h"))
        # every other workflow: queried ok (could-not-find) but no runs
        for name in ("ai-review-fallback", "pypi-publish", "release"):
            self.assertEqual((rows[name].state, rows[name].local),
                             ("drift", "never"), name)

    def test_err_streak_row(self):
        runs = {
            ("o/repo-a", "release.yml"): [
                {"createdAt": self._iso(NOW - 1800),
                 "conclusion": "failure"},
                {"createdAt": self._iso(NOW - 2 * 3600),
                 "conclusion": "failure"},
                {"createdAt": self._iso(NOW - 3 * 3600),
                 "conclusion": "failure"},
                {"createdAt": self._iso(NOW - 4 * 3600),
                 "conclusion": "success"},
            ],
        }
        with mock.patch.object(es.subprocess, "run",
                               side_effect=self._gh(runs)):
            rows = {r.product: r for r in
                    es._workflow_freshness(self.OWNERS, 5, now=NOW)}
        base = rows["release"]
        self.assertEqual((base.state, base.local), ("ok", "30m"))
        errors = rows["release (errors)"]
        self.assertEqual((errors.state, errors.local),
                         ("drift", "err streak"))
        self.assertIn("non-success", errors.note)

    def test_single_failure_is_not_a_streak(self):
        # cancelled duplicates and isolated red PR runs are not pipeline
        # death — fewer than 3 consecutive significant non-success runs
        runs = {
            ("o/repo-a", "release.yml"): [
                {"createdAt": self._iso(NOW - 1800),
                 "conclusion": "failure"},
                {"createdAt": self._iso(NOW - 2 * 3600),
                 "conclusion": "cancelled"},
                {"createdAt": self._iso(NOW - 3 * 3600),
                 "conclusion": "success"},
            ],
        }
        with mock.patch.object(es.subprocess, "run",
                               side_effect=self._gh(runs)):
            rows = {r.product: r for r in
                    es._workflow_freshness(self.OWNERS, 5, now=NOW)}
        self.assertNotIn("release (errors)", rows)

    def test_newer_success_clears_streak(self):
        runs = {
            ("o/repo-a", "release.yml"): [
                {"createdAt": self._iso(NOW - 600), "conclusion": "success"},
                {"createdAt": self._iso(NOW - 1200), "conclusion": "failure"},
            ],
        }
        with mock.patch.object(es.subprocess, "run",
                               side_effect=self._gh(runs)):
            rows = {r.product: r for r in
                    es._workflow_freshness(self.OWNERS, 5, now=NOW)}
        self.assertEqual(rows["release"].state, "ok")
        self.assertNotIn("release (errors)", rows)

    def test_all_repos_fail_is_unavailable(self):
        with mock.patch.object(es.subprocess, "run",
                               side_effect=self._gh({}, default=None)):
            rows = es._workflow_freshness(self.OWNERS, 5, now=NOW)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r.state == "unavailable" for r in rows))

    def test_threshold_boundary_7d(self):
        runs = {("o/repo-a", "ai-review-fallback.yml"): [
            {"createdAt": self._iso(NOW - 8 * 24 * 3600),
             "conclusion": "success"}]}
        with mock.patch.object(es.subprocess, "run",
                               side_effect=self._gh(runs)):
            rows = {r.product: r for r in
                    es._workflow_freshness(self.OWNERS, 5, now=NOW)}
        self.assertEqual((rows["ai-review-fallback"].state,
                          rows["ai-review-fallback"].remote),
                         ("drift", "<=7d"))


class SilenceMatrixFileTests(unittest.TestCase):
    def test_shipped_matrix_loads(self):
        matrix = es._load_silence_matrix()
        self.assertGreaterEqual(len(matrix), 20)
        self.assertAlmostEqual(matrix["office"]["threshold_h"], 0.25)
        self.assertAlmostEqual(matrix["weekly-testgen"]["threshold_h"], 192)
        self.assertEqual(matrix["review-fallback"]["repo"],
                         "Icaro0310/devin-powerups")
        for tool in ("dispatcher", "slack-output", "scout",
                     "review-fallback", "heartbeat"):
            self.assertIn(tool, matrix)

    def test_fallback_on_missing_or_invalid(self):
        missing = es._load_silence_matrix(Path("/nonexistent/matrix.json"))
        self.assertEqual(set(missing),
                         {t for t, _, _ in es._FRESHNESS_CHECKS})
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        bad = Path(d) / "m.json"
        bad.write_text('{"x": {"threshold_h": -1}, "y": "nope"}')
        self.assertEqual(set(es._load_silence_matrix(bad)),
                         {t for t, _, _ in es._FRESHNESS_CHECKS})


class SilenceMonitorSectionTests(unittest.TestCase):
    def test_state_md_lists_silence_rows(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        out = Path(d) / "state.md"
        rows = [
            es.Row("devin-x", "pypi", "0.1", "0.1", "ok"),
            es.Row("office", "freshness", "4m", "<=15m", "ok", "o/r"),
            es.Row("session-sweep", "freshness", "31h", "<=3h", "drift",
                   "o/r"),
            es.Row("vm-sync", "freshness", "—", "<=8d", "unavailable",
                   "o/r"),
            es.Row("queue-api (errors)", "freshness", "err streak",
                   "<=15m", "drift", "o/r"),
        ]
        es.write_state_md(out, rows, [], [], datetime.now(timezone.utc))
        text = out.read_text()
        self.assertIn("## Silence Monitor", text)
        self.assertIn("- office: ok", text)
        self.assertIn("- session-sweep: DRIFT 31h", text)
        self.assertIn("- vm-sync: n/a", text)
        self.assertIn("- queue-api (errors): DRIFT err streak", text)


class ParseTimestampTests(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(es._parse_timestamp(1_800_000_000), 1_800_000_000.0)
        self.assertEqual(
            es._parse_timestamp("2026-10-25T22:05:32.105Z"),
            datetime(2026, 10, 25, 22, 5, 32, 105000,
                     tzinfo=timezone.utc).timestamp())
        self.assertIsNotNone(es._parse_timestamp("2026-10-28T18:01:30+0000"))
        self.assertIsNotNone(es._parse_timestamp("2026-10-25"))
        self.assertIsNone(es._parse_timestamp("janitor:silent:2026-10-13"))
        self.assertIsNone(es._parse_timestamp(40))  # counters aren't epochs
        self.assertIsNone(es._parse_timestamp(None))
        self.assertIsNone(es._parse_timestamp(True))


class CollectPrReadyNotMergedTests(unittest.TestCase):
    """pr-merge sensor: approved+green+unmerged+old PRs -> drift rows."""

    NOW = 1_800_000_000.0
    HEAD_SHA = "a" * 40  # fixture head; audit comments bind via head:<sha>

    def _iso(self, epoch):
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat()

    def _green_rollup(self, extra=()):
        return [
            {"__typename": "CheckRun", "name": "ci",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "StatusContext", "context": "devin-judge/review",
             "state": "SUCCESS"},
            *extra,
        ]

    def _pr(self, number=1, decision="APPROVED", rollup=None,
            auto_merge=None, age_s=3600, draft=False, title="t",
            head_sha=None):
        return {
            "number": number,
            "title": title,
            "url": f"https://github.com/o/r/pull/{number}",
            "reviewDecision": decision,
            "isDraft": draft,
            "autoMergeRequest": auto_merge,
            "createdAt": self._iso(self.NOW - age_s),
            "headRefOid": self.HEAD_SHA if head_sha is None else head_sha,
            "statusCheckRollup": self._green_rollup() if rollup is None
            else rollup,
        }

    def _gh(self, prs_by_repo, comments_by_pr=None, fail_repos=()):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            if "view" in cmd:
                repo = cmd[cmd.index("--repo") + 1]
                num = cmd[cmd.index("view") + 1]
                comments = (comments_by_pr or {}).get((repo, num), [])
                return mock.Mock(
                    returncode=0,
                    stdout=json.dumps({"comments": comments}), stderr="")
            repo = cmd[cmd.index("--repo") + 1]
            if repo in fail_repos:
                return mock.Mock(returncode=1, stdout="", stderr="boom")
            return mock.Mock(
                returncode=0,
                stdout=json.dumps(prs_by_repo.get(repo, [])), stderr="")

        fake.calls = calls
        return fake

    def _collect(self, prs_by_repo, comments_by_pr=None, fail_repos=()):
        fake = self._gh(prs_by_repo, comments_by_pr, fail_repos)
        with mock.patch.object(es.subprocess, "run", side_effect=fake):
            rows = es.collect_pr_ready_not_merged(
                {"r": "o"}, 10, now=self.NOW)
        return rows, fake.calls

    def test_approved_green_unmerged_is_drift(self):
        rows, _ = self._collect({"o/r": [self._pr(7, title="feat: x")]})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row.channel, row.state, row.repo),
                         ("pr-merge", "drift", "o/r"))
        self.assertEqual(row.product, "r#7")
        self.assertIn("unmerged 1h", row.local)
        self.assertIn("feat: x", row.note)

    def test_cancelled_checks_do_not_block(self):
        # approve/fallback CANCELLED are known concurrency flakes — the
        # lesson that motivated treating CANCELLED as non-blocking.
        rollup = self._green_rollup(extra=[
            {"__typename": "CheckRun", "name": "approve",
             "status": "COMPLETED", "conclusion": "CANCELLED"},
            {"__typename": "CheckRun", "name": "fallback / classify",
             "status": "COMPLETED", "conclusion": "CANCELLED"},
            {"__typename": "CheckRun", "name": "sonar",
             "status": "COMPLETED", "conclusion": "SKIPPED"},
        ])
        rows, _ = self._collect({"o/r": [self._pr(1, rollup=rollup)]})
        self.assertEqual(len(rows), 1)

    def test_failure_check_blocks(self):
        rollup = self._green_rollup(extra=[
            {"__typename": "CheckRun", "name": "tools-tests",
             "status": "COMPLETED", "conclusion": "FAILURE"}])
        rows, _ = self._collect({"o/r": [self._pr(1, rollup=rollup)]})
        self.assertEqual(rows, [])

    def test_pending_check_blocks(self):
        rollup = self._green_rollup(extra=[
            {"__typename": "CheckRun", "name": "ci",
             "status": "IN_PROGRESS", "conclusion": None}])
        rows, _ = self._collect({"o/r": [self._pr(1, rollup=rollup)]})
        self.assertEqual(rows, [])

    def test_pending_status_context_blocks(self):
        rollup = self._green_rollup(extra=[
            {"__typename": "StatusContext", "context": "ci/build",
             "state": "PENDING"}])
        rows, _ = self._collect({"o/r": [self._pr(1, rollup=rollup)]})
        self.assertEqual(rows, [])

    def test_status_failure_blocks(self):
        rollup = [
            {"__typename": "CheckRun", "name": "ci",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "StatusContext", "context": "devin-judge/review",
             "state": "FAILURE"},
        ]
        rows, _ = self._collect({"o/r": [self._pr(1, rollup=rollup)]})
        self.assertEqual(rows, [])

    def test_armed_draft_and_young_skip(self):
        prs = [
            self._pr(1, auto_merge={"enabledAt": "x"}),
            self._pr(2, draft=True),
            self._pr(3, age_s=10 * 60),
            self._pr(4, decision="CHANGES_REQUESTED"),
        ]
        rows, _ = self._collect({"o/r": prs})
        self.assertEqual(rows, [])

    def test_not_approved_skips_without_comments_lookup(self):
        rollup = [
            {"__typename": "CheckRun", "name": "ci",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]
        rows, calls = self._collect(
            {"o/r": [self._pr(1, decision="REVIEW_REQUIRED",
                              rollup=rollup)]})
        self.assertEqual(rows, [])
        self.assertFalse(any("view" in c for c in calls))

    def test_manual_blocking0_path_needs_audit_comment(self):
        rollup = self._green_rollup()
        prs = {"o/r": [self._pr(9, decision="REVIEW_REQUIRED",
                                rollup=rollup)]}
        # judge success but no audit marker -> still not approved
        rows, _ = self._collect(
            prs, comments_by_pr={("o/r", "9"): [
                {"body": "unrelated comment"}]})
        self.assertEqual(rows, [])
        # audit bound to a STALE head -> not approval for the live head
        rows, _ = self._collect(
            prs, comments_by_pr={("o/r", "9"): [
                {"body": "gate-resolved-via: manual-blocking0 — clean "
                         "evaluation on abc123\n"
                         "gate-fallback-pairs: manual-blocking0 "
                         f"head:{'0' * 40}"}]})
        self.assertEqual(rows, [])
        # audit with no head binding at all -> rejected the same way
        rows, _ = self._collect(
            prs, comments_by_pr={("o/r", "9"): [
                {"body": "gate-resolved-via: manual-blocking0 — clean "
                         "evaluation on abc123"}]})
        self.assertEqual(rows, [])
        # audit on the CURRENT head -> approved via the documented 2nd path
        rows, _ = self._collect(
            prs, comments_by_pr={("o/r", "9"): [
                {"body": "gate-resolved-via: manual-blocking0 — clean "
                         "evaluation on abc123\n"
                         "gate-fallback-pairs: manual-blocking0 "
                         f"head:{self.HEAD_SHA}"}]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].product, "r#9")

    def test_repo_failure_skips_silently(self):
        rows, _ = self._collect({}, fail_repos={"o/r"})
        self.assertEqual(rows, [])

    def test_unparsable_created_skips(self):
        pr = self._pr(1)
        pr["createdAt"] = "not-a-date"
        rows, _ = self._collect({"o/r": [pr]})
        self.assertEqual(rows, [])

    def test_failure_class_mapping(self):
        row = es.Row("r#1", "pr-merge", "unmerged 1h", "merged", "drift",
                     "o/r")
        self.assertEqual(es._failure_class(row), "pr_stuck")


class HostScopingTests(unittest.TestCase):
    """`host` scoping: foreign-host rows skipped; unhosted run everywhere."""

    def _collect(self, matrix, this_host="laptop"):
        with mock.patch.object(es, "_this_host", return_value=this_host), \
             mock.patch.object(es, "_load_silence_matrix",
                               return_value=matrix), \
             mock.patch.object(es, "_read_heartbeats", return_value={}), \
             mock.patch.object(es, "_install_evidence", return_value=""), \
             mock.patch.object(es, "_workflow_freshness", return_value=[]):
            return es.collect_freshness([Path("/nonexistent")], {}, 5)

    def test_foreign_host_row_skipped(self):
        matrix = {"vm-probes": {"threshold_h": 1, "repo": "o/r",
                                "host": "vm"}}
        self.assertEqual(self._collect(matrix, "laptop"), [])

    def test_own_host_row_evaluated(self):
        matrix = {"vm-probes": {"threshold_h": 1, "repo": "o/r",
                                "host": "vm"}}
        rows = self._collect(matrix, "vm")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].product, "vm-probes")

    def test_unhosted_row_runs_on_both_hosts(self):
        matrix = {"cron-daemon": {"threshold_h": 1, "repo": "o/r"}}
        self.assertEqual(len(self._collect(matrix, "laptop")), 1)
        self.assertEqual(len(self._collect(matrix, "vm")), 1)

    def test_shipped_matrix_host_consistency(self):
        """Every shipped entry is host-scoped or in the shared allowlist."""
        shared = {"cron-daemon", "scout", "slack-output", "review-fallback"}
        matrix = es._load_silence_matrix()  # real tools/silence-matrix.json
        unhosted = {t for t, cfg in matrix.items() if "host" not in cfg}
        self.assertEqual(unhosted, shared)
        for tool, cfg in matrix.items():
            self.assertIn(cfg.get("host", "") or "shared",
                          ("laptop", "vm", "shared"), tool)
        self.assertEqual(matrix["laptop-freshness"].get("host"), "laptop")
        self.assertEqual(
            matrix["laptop-freshness-watch"].get("host"), "vm")


class CronRepoCandidatesTests(unittest.TestCase):
    """Pure parsing: which paths in a cron command count as repo code."""

    DEVIN = Path("/home/test/devin")
    HOME = Path("/home/test")

    def test_script_extensions(self):
        for ext in (".py", ".sh", ".mjs", ".js"):
            line = (f"0 9 * * * python3 /home/test/devin/repo-a/s/x{ext} "
                    ">>/tmp/log 2>&1")
            cands, foreign = es._cron_repo_candidates(
                line, self.DEVIN, self.HOME)
            self.assertEqual(foreign, 0)
            self.assertEqual(
                cands, [Path(f"/home/test/devin/repo-a/s/x{ext}")], ext)

    def test_dollar_home_and_tilde_spellings(self):
        for spelling in ("$HOME/devin/repo-b/tools/y.mjs",
                         "~/devin/repo-b/tools/y.mjs"):
            line = f"*/5 * * * * /usr/bin/node {spelling}"
            cands, foreign = es._cron_repo_candidates(
                line, self.DEVIN, self.HOME)
            self.assertEqual(foreign, 0)
            self.assertEqual(
                cands, [Path("/home/test/devin/repo-b/tools/y.mjs")],
                spelling)

    def test_dollar_home_defaults_to_devin_parent(self):
        # home=None -> devin.parent: $HOME/devin maps onto the devin root.
        line = "0 9 * * * python3 $HOME/devin/repo-b/x.py"
        cands, foreign = es._cron_repo_candidates(line, self.DEVIN)
        self.assertEqual(foreign, 0)
        self.assertEqual(cands, [Path("/home/test/devin/repo-b/x.py")])

    def test_foreign_cron_home_is_counted_not_classified(self):
        # HOME=/srv/alice -> $HOME/devin lands outside /home/test/devin:
        # out of scope, reported as foreign — never silently ok.
        line = "0 9 * * * python3 $HOME/devin/app/job.py"
        cands, foreign = es._cron_repo_candidates(
            line, self.DEVIN, Path("/srv/alice"))
        self.assertEqual(cands, [])
        self.assertEqual(foreign, 1)
        # absolute spellings do not depend on HOME and stay in scope
        line = "0 9 * * * python3 /home/test/devin/app/job.py"
        cands, foreign = es._cron_repo_candidates(
            line, self.DEVIN, Path("/srv/alice"))
        self.assertEqual(foreign, 0)
        self.assertEqual(cands, [Path("/home/test/devin/app/job.py")])

    def test_cd_target_needs_no_extension(self):
        line = "0 3 * * * cd /home/test/devin/repo-c && ./run.sh"
        cands, _ = es._cron_repo_candidates(line, self.DEVIN, self.HOME)
        self.assertEqual(cands, [Path("/home/test/devin/repo-c")])
        line = '30 4 * * * cd "$HOME/devin/repo-c/sub" && make'
        cands, _ = es._cron_repo_candidates(line, self.DEVIN, self.HOME)
        self.assertEqual(cands, [Path("/home/test/devin/repo-c/sub")])

    def test_non_devin_paths_and_non_scripts_ignored(self):
        line = ("0 9 * * * /home/test/.local/bin/tool.sh "
                "/home/test/devin/repo-a/README.md /opt/x.py "
                "/home/test/devin/repo-a/data.json")
        self.assertEqual(
            es._cron_repo_candidates(line, self.DEVIN, self.HOME),
            ([], 0))

    def test_devin_prefix_sibling_not_matched(self):
        # /home/test/devin-other is NOT under the devin root.
        line = "0 9 * * * python3 /home/test/devin-other/scripts/x.py"
        self.assertEqual(
            es._cron_repo_candidates(line, self.DEVIN, self.HOME),
            ([], 0))

    def test_duplicates_deduped(self):
        line = ("0 9 * * * python3 /home/test/devin/r/a.py && "
                "python3 /home/test/devin/r/a.py")
        cands, _ = es._cron_repo_candidates(line, self.DEVIN, self.HOME)
        self.assertEqual(cands, [Path("/home/test/devin/r/a.py")])


class CronRepoRefTests(unittest.TestCase):
    """Branch classification: main ok, tag-detached ok, else warn."""

    REPO = Path("/home/test/devin/repo-a")

    def _ref(self, abbrev="main", describe_rc=128, sha="abc1234"):
        def fake_run(cmd, **kw):
            args = cmd[3:]
            if args[:2] == ["rev-parse", "--abbrev-ref"]:
                return mock.Mock(returncode=0, stdout=abbrev + "\n",
                                 stderr="")
            if args[:2] == ["describe", "--tags"]:
                return mock.Mock(
                    returncode=describe_rc,
                    stdout="v1.0\n" if describe_rc == 0 else "",
                    stderr="")
            if args[:2] == ["rev-parse", "--short"]:
                return mock.Mock(returncode=0, stdout=sha + "\n",
                                 stderr="")
            return mock.Mock(returncode=1, stdout="", stderr="")

        with mock.patch.object(es.subprocess, "run", side_effect=fake_run):
            return es._cron_repo_ref(self.REPO, 5)

    def test_named_branches(self):
        self.assertEqual(self._ref("main"), "main")
        self.assertEqual(self._ref("feature/x"), "feature/x")

    def test_detached_on_tag_is_tolerated(self):
        self.assertEqual(self._ref("HEAD", describe_rc=0), "tag:v1.0")

    def test_detached_on_commit_is_flagged(self):
        self.assertEqual(self._ref("HEAD", describe_rc=128),
                         "detached@abc1234")

    def test_git_failure_is_none(self):
        with mock.patch.object(es.subprocess, "run",
                               side_effect=OSError("no git")):
            self.assertIsNone(es._cron_repo_ref(self.REPO, 5))


class _FakeCronGit:
    """subprocess.run fake for collect_cron_branch_stale.

    ``crontab -l`` returns the canned crontab; ``git -C <dir> ...``
    resolves the longest matching repo root from ``repos`` —
    ``{root: {"branch": name, "detached": bool, "tag": name|None,
    "broken": bool}}`` (``broken`` makes every git call fail, modelling
    a checkout the sensor cannot classify).
    """

    def __init__(self, crontab, repos):
        self.crontab = crontab
        self.repos = repos
        self.calls = []

    def _root_for(self, directory):
        best = None
        for root in self.repos:
            if (directory == root or directory.startswith(root + "/")) \
                    and (best is None or len(root) > len(best)):
                best = root
        return best

    def _proc(self, rc, out="", err=""):
        return mock.Mock(returncode=rc, stdout=out, stderr=err)

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[0] == "crontab":
            return self._proc(0, self.crontab)
        directory, args = cmd[2], cmd[3:]
        root = self._root_for(directory)
        if root is None:
            return self._proc(128, "", "not a git repository")
        cfg = self.repos[root]
        if args == ["rev-parse", "--show-toplevel"]:
            return self._proc(0, root + "\n")
        if cfg.get("broken"):
            # toplevel resolves but branch state cannot be proven —
            # models the "undetermined" path in _cron_repo_ref.
            return self._proc(128, "", "git exploded")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            ref = "HEAD" if cfg.get("detached") else cfg["branch"]
            return self._proc(0, ref + "\n")
        if args == ["describe", "--tags", "--exact-match", "HEAD"]:
            if cfg.get("tag"):
                return self._proc(0, cfg["tag"] + "\n")
            return self._proc(128, "", "no tag")
        if args == ["rev-parse", "--short", "HEAD"]:
            return self._proc(0, "abc1234\n")
        return self._proc(1, "", "?")


class CollectCronBranchStaleTests(unittest.TestCase):
    """End-to-end collect over a fake crontab + fake git.

    ``_collect`` builds a real ``<tmp>/devin`` tree (repo dirs must exist
    for the candidate walk-up) and maps ``{DEVIN}`` placeholders in the
    crontab entries to it. ``repo_states`` maps repo dir names (relative
    to devin) to ``{"branch": ..., "detached": bool, "tag": ...}``.
    """

    def _collect(self, entries, repo_states):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        devin = Path(d) / "devin"
        repos = {}
        for name, cfg in repo_states.items():
            root = devin / name
            root.mkdir(parents=True, exist_ok=True)
            repos[str(root)] = cfg
        crontab = "\n".join(
            e.format(DEVIN=devin, HOME=devin.parent)
            for e in entries) + "\n"
        fake = _FakeCronGit(crontab, repos)
        with mock.patch.object(es.shutil, "which",
                               return_value="/usr/bin/crontab"), \
                mock.patch.object(es.subprocess, "run", side_effect=fake):
            # home=devin.parent keeps $HOME/devin spellings inside the
            # tmp devin root, mirroring <home>/devin on a real host.
            rows = es.collect_cron_branch_stale(
                devin=devin, home=devin.parent, timeout=5)
        return rows, fake

    def test_non_main_repo_script_warns(self):
        rows, _ = self._collect(
            [("*/5 * * * * /home/x/.local/bin/hb run x -- "
              "/usr/bin/python3 $HOME/devin/repo-a/scripts/x.py")],
            {"repo-a": {"branch": "feature/x"}})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row.product, row.channel, row.state),
                         ("repo-a", "cron-branch", "warn"))
        self.assertEqual((row.local, row.remote),
                         ("feature/x", "main"))
        self.assertIn("x.py", row.note)
        self.assertNotIn(row.state, es.DRIFT_STATES)  # warn never fails

    def test_main_repo_is_ok(self):
        rows, _ = self._collect(
            ["0 9 * * * python3 {DEVIN}/repo-a/s/x.py"],
            {"repo-a": {"branch": "main"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].state, rows[0].local), ("ok", "main"))

    def test_detached_tag_ok_commit_warns(self):
        rows, _ = self._collect(
            ["0 9 * * * python3 {DEVIN}/repo-tag/x.py",
             "0 10 * * * python3 {DEVIN}/repo-det/x.py"],
            {"repo-tag": {"branch": "main", "detached": True,
                          "tag": "v2.0"},
             "repo-det": {"branch": "main", "detached": True,
                          "tag": None}})
        by_product = {r.product: r for r in rows}
        self.assertEqual(by_product["repo-tag"].state, "ok")
        self.assertEqual(by_product["repo-tag"].local, "v2.0")
        self.assertEqual(by_product["repo-det"].state, "warn")
        self.assertEqual(by_product["repo-det"].local, "detached@abc1234")

    def test_wrapper_lines_checked_via_git(self):
        # No exemptions: every ~/devin path — including worktrees/*
        # targets of the self-updating wrappers — goes through the git
        # check. Worktrees sitting on main come back ok; the stale
        # repo-a script still warns. Wrapper tokens themselves live in
        # ~/.local/bin and never match the ~/devin scope.
        rows, _ = self._collect(
            ["# comment with {DEVIN}/repo-a/x.py inside",
             "",
             "PATH=/home/x/.local/bin:/usr/bin:/bin",
             ("*/30 * * * * /home/x/.local/bin/hb run t -- "
              "/home/x/.local/bin/pas-cron.sh /bin/bash -c "
              "'/usr/bin/python3 scripts/x.py'"),
             ("*/30 * * * * /home/x/.local/bin/pas-cron.sh "
              "{DEVIN}/worktrees/pas-main/scripts/y.sh"),
             "*/30 * * * * /home/x/.local/bin/remediate-runner-cron.sh",
             ("*/5 * * * * /home/x/.local/bin/repo-cron.sh repo-b "
              "/usr/bin/python3 {DEVIN}/worktrees/repo-b/tools/x.py"),
             "0 9 * * * cd {DEVIN}/worktrees/pas-main && ./z.sh",
             ("0 9 * * * /usr/bin/python3 {DEVIN}/repo-a/x.py "
              "# pas-cron.sh mentioned only in a shell comment")],
            {"repo-a": {"branch": "stale-branch"},
             "worktrees/pas-main": {"branch": "main"},
             "worktrees/repo-b": {"branch": "main"}})
        by_product = {r.product: r for r in rows}
        self.assertEqual(len(rows), 3)
        self.assertEqual((by_product["repo-a"].state,
                          by_product["repo-a"].local),
                         ("warn", "stale-branch"))
        self.assertEqual((by_product["pas-main"].state,
                          by_product["pas-main"].local),
                         ("ok", "main"))
        self.assertIn("2 cron entries", by_product["pas-main"].note)
        self.assertEqual((by_product["repo-b"].state,
                          by_product["repo-b"].local),
                         ("ok", "main"))

    def test_non_repo_paths_skipped(self):
        rows, _ = self._collect(
            ["0 9 * * * python3 {DEVIN}/not-a-repo/x.py",
             "0 11 * * * /home/x/.local/bin/laptop-probes.sh"],
            {})
        # nothing resolves to a repo -> only the clean summary row
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("cron-branch-stale", "ok"))

    def test_repo_above_devin_root_rejected(self):
        # A checkout whose toplevel sits ABOVE ~/devin is out of scope —
        # e.g. ~/devin itself living inside a dotfiles repo.
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        devin = Path(d) / "devin"
        (devin / "repo-a" / "scripts").mkdir(parents=True)
        crontab = f"0 9 * * * python3 {devin}/repo-a/scripts/x.py\n"
        # the only "repo" the fake git knows is the tmpdir itself —
        # an ancestor of devin, so _cron_repo_root must reject it.
        fake = _FakeCronGit(crontab, {d: {"branch": "main"}})
        with mock.patch.object(es.shutil, "which",
                               return_value="/usr/bin/crontab"), \
                mock.patch.object(es.subprocess, "run", side_effect=fake):
            rows = es.collect_cron_branch_stale(devin=devin, timeout=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("cron-branch-stale", "ok"))

    def test_multiple_lines_same_repo_dedup(self):
        rows, _ = self._collect(
            ["0 9 * * * python3 {DEVIN}/repo-a/x.py",
             "0 10 * * * python3 {DEVIN}/repo-a/y.py"],
            {"repo-a": {"branch": "dev"}})
        self.assertEqual(len(rows), 1)
        self.assertIn("2 cron entries", rows[0].note)
        self.assertIn("x.py", rows[0].note)
        self.assertIn("y.py", rows[0].note)

    def test_cd_into_repo_flagged(self):
        rows, _ = self._collect(
            ["0 4 * * * cd {DEVIN}/repo-c && ./deploy.sh"],
            {"repo-c": {"branch": "release"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("repo-c", "warn"))

    def test_empty_crontab_is_ok(self):
        rows, _ = self._collect([], {})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].state, rows[0].product),
                         ("ok", "cron-branch-stale"))
        self.assertIn("no repo-script", rows[0].note)

    def test_crontab_failures(self):
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        devin = Path(d) / "devin"
        devin.mkdir()
        # no crontab binary -> skip
        with mock.patch.object(es.shutil, "which", return_value=None):
            rows = es.collect_cron_branch_stale(devin=devin)
        self.assertEqual((rows[0].state, rows[0].channel),
                         ("skip", "cron-branch"))
        # rc!=0 with empty stdout -> clean "no crontab"
        proc = mock.Mock(returncode=1, stdout="", stderr="no crontab")
        with mock.patch.object(es.shutil, "which",
                               return_value="/usr/bin/crontab"), \
                mock.patch.object(es.subprocess, "run", return_value=proc):
            rows = es.collect_cron_branch_stale(devin=devin)
        self.assertEqual(rows[0].state, "ok")
        # rc!=0 with stderr -> unavailable
        proc = mock.Mock(returncode=2, stdout="", stderr="denied")
        with mock.patch.object(es.shutil, "which",
                               return_value="/usr/bin/crontab"), \
                mock.patch.object(es.subprocess, "run", return_value=proc):
            rows = es.collect_cron_branch_stale(devin=devin)
        self.assertEqual(rows[0].state, "unavailable")
        # spawn failure -> unavailable
        with mock.patch.object(es.shutil, "which",
                               return_value="/usr/bin/crontab"), \
                mock.patch.object(es.subprocess, "run",
                                  side_effect=OSError("boom")):
            rows = es.collect_cron_branch_stale(devin=devin)
        self.assertEqual(rows[0].state, "unavailable")

    def test_crontab_rc1_requires_known_diagnostic(self):
        # BUG_0002: rc=1 + empty stdout is only "no crontab" when the
        # output carries the known diagnostic — a silent or denied rc=1
        # is a real failure and must surface as unavailable.
        d = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        devin = Path(d) / "devin"
        devin.mkdir()

        def run_with(proc):
            with mock.patch.object(es.shutil, "which",
                                   return_value="/usr/bin/crontab"), \
                    mock.patch.object(es.subprocess, "run",
                                      return_value=proc):
                return es.collect_cron_branch_stale(devin=devin)

        rows = run_with(mock.Mock(returncode=1, stdout="",
                                  stderr="no crontab for ikaros"))
        self.assertEqual(rows[0].state, "ok")
        # the diagnostic may also arrive on stdout on some builds
        rows = run_with(mock.Mock(returncode=1,
                                  stdout="no crontab for ikaros",
                                  stderr=""))
        self.assertEqual(rows[0].state, "ok")
        rows = run_with(mock.Mock(returncode=1, stdout="",
                                  stderr="permission denied"))
        self.assertEqual(rows[0].state, "unavailable")
        rows = run_with(mock.Mock(returncode=1, stdout="", stderr=""))
        self.assertEqual(rows[0].state, "unavailable")

    def test_wrapper_on_same_line_does_not_launder_stale(self):
        # BUG_0001: a wrapper token anywhere in the cron entry must not
        # hide an earlier stale repo script — every ~/devin path is
        # checked regardless of what else the line invokes.
        for sep in ("&&", ";", "||"):
            with self.subTest(sep=sep):
                rows, _ = self._collect(
                    [(f"0 * * * * python3 {{DEVIN}}/repo-old/job.py {sep} "
                      "/home/x/.local/bin/pas-cron.sh")],
                    {"repo-old": {"branch": "backlog/old"}})
                self.assertEqual(len(rows), 1)
                self.assertEqual((rows[0].product, rows[0].state),
                                 ("repo-old", "warn"))
        # and the symmetric order: wrapper first, stale second
        rows, _ = self._collect(
            [("0 * * * * /home/x/.local/bin/pas-cron.sh ; "
              "python3 {DEVIN}/repo-old/job.py")],
            {"repo-old": {"branch": "backlog/old"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("repo-old", "warn"))

    def test_wrapper_line_still_checks_foreign_devin_path(self):
        # pas-cron.sh pulls pas-main then execs its args — an absolute
        # devin path to ANOTHER checkout in the same command is not
        # protected and must still be checked.
        rows, _ = self._collect(
            [("0 * * * * /home/x/.local/bin/pas-cron.sh "
              "/usr/bin/python3 {DEVIN}/repo-stale/x.py")],
            {"repo-stale": {"branch": "feature"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("repo-stale", "warn"))

    def test_worktree_paths_checked_like_any_checkout(self):
        # No worktrees/ exemption: repo-cron.sh repo-b pulls
        # worktrees/repo-b, but the git check — not the wrapper token —
        # decides. On main -> ok row; on a stale branch -> warn.
        for branch, want in (("main", "ok"), ("stale-x", "warn")):
            with self.subTest(branch=branch):
                rows, _ = self._collect(
                    [("0 * * * * /home/x/.local/bin/repo-cron.sh repo-b "
                      "python3 {DEVIN}/worktrees/repo-b/a.py; "
                      "python3 {DEVIN}/worktrees/repo-b/b.py")],
                    {"worktrees/repo-b": {"branch": branch}})
                self.assertEqual(len(rows), 1)
                self.assertEqual((rows[0].product, rows[0].state),
                                 ("repo-b", want))
                if want == "warn":
                    self.assertIn("a.py", rows[0].note)
                    self.assertIn("b.py", rows[0].note)
        # ...and an absolute path to the MAIN checkout in the same
        # wrapper line is checked too (the wrapper only pulls the
        # worktree, never the sibling checkout).
        rows, _ = self._collect(
            [("0 * * * * /home/x/.local/bin/repo-cron.sh repo-b "
              "/usr/bin/python3 {DEVIN}/repo-b/tools/x.py")],
            {"repo-b": {"branch": "feature"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("repo-b", "warn"))

    def test_quoted_payload_paths_still_checked(self):
        # Paths inside a quoted bash -c payload are extracted like any
        # other — quoting changes nothing now that nothing is exempt.
        # A stale worktree behind repo-cron.sh warns either way.
        for quote in ('"', "'"):
            with self.subTest(quote=quote):
                rows, fake = self._collect(
                    [("0 * * * * /home/x/.local/bin/repo-cron.sh repo-b "
                      f"bash -c {quote}python3 {{DEVIN}}/worktrees/"
                      f"repo-b/a.py{quote} ; true")],
                    {"worktrees/repo-b": {"branch": "stale-branch"}})
                self.assertEqual(len(rows), 1)
                self.assertEqual((rows[0].product, rows[0].state),
                                 ("repo-b", "warn"))
                self.assertTrue(any(c[0] == "git" for c in fake.calls))

    def test_stale_script_alongside_wrapper_flagged(self):
        # repo-x/a.py shares the line with pas-cron.sh — the wrapper
        # protects only its own worktree, repo-x is still flagged.
        rows, _ = self._collect(
            [("0 * * * * python3 {DEVIN}/repo-x/a.py; "
              "/home/x/.local/bin/pas-cron.sh")],
            {"repo-x": {"branch": "stale"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("repo-x", "warn"))

    def test_foreign_cron_home_reported_unavailable(self):
        # BUG_0003: HOME=/srv/alice makes $HOME/devin expand outside the
        # sync devin root -> unavailable, never a silent ok.
        rows, _ = self._collect(
            ["HOME=/srv/alice",
             "0 9 * * * python3 $HOME/devin/app/job.py"],
            {})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].state, rows[0].product),
                         ("unavailable", "cron-branch-stale"))
        self.assertIn("HOME", rows[0].note)

    def test_cron_home_env_scoped_to_following_lines(self):
        # HOME= applies only to commands AFTER it: the early line still
        # expands against the process home (tmp devin root) and warns,
        # the late line lands in /srv/alice and is reported foreign.
        rows, _ = self._collect(
            ["0 9 * * * python3 $HOME/devin/repo-early/x.py",
             "HOME=/srv/alice",
             "0 10 * * * python3 $HOME/devin/repo-late/x.py"],
            {"repo-early": {"branch": "dev"}})
        self.assertEqual(len(rows), 2)
        by_state = {r.state: r for r in rows}
        self.assertEqual(by_state["warn"].product, "repo-early")
        self.assertEqual(by_state["unavailable"].product,
                         "cron-branch-stale")
        self.assertIn("HOME", by_state["unavailable"].note)

    def test_matching_cron_home_still_classified(self):
        # HOME=<tmp> lines make $HOME/devin resolve onto the tmp devin
        # root — same classification as the absolute spelling.
        rows, _ = self._collect(
            ["HOME={HOME}",
             "0 9 * * * python3 $HOME/devin/repo-h/x.py"],
            {"repo-h": {"branch": "dev"}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].product, rows[0].state),
                         ("repo-h", "warn"))

    def test_partial_git_failure_surfaces_unavailable(self):
        # ANALYSIS_0001: one checkout classifies, another cannot — the
        # undetermined count must still appear as an unavailable row.
        rows, _ = self._collect(
            ["0 9 * * * python3 {DEVIN}/repo-ok/x.py",
             "0 10 * * * python3 {DEVIN}/repo-broken/x.py"],
            {"repo-ok": {"branch": "main"},
             "repo-broken": {"broken": True}})
        self.assertEqual(len(rows), 2)
        states = {(r.product, r.state) for r in rows}
        self.assertIn(("repo-ok", "ok"), states)
        self.assertIn(("cron-branch-stale", "unavailable"), states)
        unavail = next(r for r in rows if r.state == "unavailable")
        self.assertIn("could not be classified", unavail.note)

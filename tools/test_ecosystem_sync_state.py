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

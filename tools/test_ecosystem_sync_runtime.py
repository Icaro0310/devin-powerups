"""Tests for ecosystem_sync --runtime: runtime-registry drift detection.

Covers load_runtime_registry validation, every heartbeat.source eval
(heartbeats.jsonl / pm2 / cron-log / gh-run / systemd / none), host
drift, deploy freshness vs origin/main and the fail-open contract —
all probes mocked, no VM/network/fs dependence beyond tmp dirs.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import ecosystem_sync as es

NOW = 1_800_000_000.0  # fixed epoch for max_age math


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _comp(name, host="laptop", source="heartbeats.jsonl", key=None,
          max_age="1h", deploy="pm2", deploy_path="/tmp/x",
          policy="accepted", **extra):
    comp = {
        "name": name, "host": host, "description": "t",
        "data_deps": [], "schedule": "t", "deploy": deploy,
        "deploy_path": deploy_path, "staleness_policy": policy,
        "owner": "t",
        "heartbeat": {"source": source, "key": key or name,
                      "max_age": max_age},
    }
    comp.update(extra)
    return comp


def _registry(*comps):
    return {"version": 1, "components": list(comps)}


def _hb_entry(age_s, fail_age_s=None):
    return {"last_success_at": NOW - age_s if age_s is not None else None,
            "last_failure_at": (NOW - fail_age_s
                                if fail_age_s is not None else None),
            "last_detail": ""}


def _vm_probe(heartbeats=None, pm2=None, cron_files=None, git=None,
              cron_journal=None):
    return {"hostname": "vm-test", "heartbeats": heartbeats or {},
            "pm2": pm2 or {}, "cron_files": cron_files or {},
            "git": git or {}, "cron_journal": cron_journal or {}}


class CollectRuntimeCase(unittest.TestCase):
    """Base: patch every probe collect_runtime can reach."""

    def setUp(self):
        self._patches = [
            mock.patch.object(es, "_this_host", return_value="laptop"),
            mock.patch.object(es, "_read_heartbeats", return_value={}),
            mock.patch.object(es, "_cron_journal_hits", return_value={}),
            mock.patch.object(es, "_cron_file_entry", return_value=None),
            mock.patch.object(es, "_runtime_git_state", return_value=None),
            mock.patch.object(es, "_local_pm2", return_value={}),
            mock.patch.object(es, "_systemctl_is_active",
                              return_value="active"),
            mock.patch.object(es, "_timer_last_trigger",
                              return_value=None),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)
        self.gh_api = mock.patch.object(
            es, "_gh_api",
            side_effect=RuntimeError("gh disabled in test")).start()
        self.addCleanup(mock.patch.stopall)

    _UNSET = object()

    def collect(self, comps, vm=_UNSET, offline=False, owners=None,
                roots=None, **kw):
        # vm=_UNSET -> default EMPTY probe (never touches ssh);
        # vm=None -> probe reports unreachable; vm=dict -> canned probe.
        if vm is self._UNSET:
            probe = kw.pop("vm_probe", None) or (
                lambda req, timeout: _vm_probe())
        elif vm is None:
            probe = lambda req, timeout: None
        else:
            probe = lambda req, timeout: vm
        return es.collect_runtime(
            _registry(*comps), owners or {}, roots or [Path("/nonexistent")],
            timeout=5, now=NOW, offline=offline, vm_probe=probe, **kw)


class LoadRuntimeRegistryTests(unittest.TestCase):
    def _write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".json",
                                        delete=False)
        f.write(text)
        f.close()
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        return f.name

    def test_valid_registry_loads(self):
        path = self._write(json.dumps(_registry(_comp("a"))))
        reg = es.load_runtime_registry(path)
        self.assertEqual(len(reg["components"]), 1)

    def test_malformed_variants_raise(self):
        for bad in ("{}", '{"components": []}', "not json",
                    '{"components": [{"name": 1, "host": "laptop",'
                    ' "heartbeat": {"source": "none"}}]}',
                    '{"components": [{"name": "a", "host": "laptop",'
                    ' "heartbeat": {"source": "none"}},'
                    ' {"name": "a", "host": "laptop",'
                    ' "heartbeat": {"source": "none"}}]}'):
            path = self._write(bad)
            with self.assertRaises((ValueError, json.JSONDecodeError),
                                   msg=bad[:40]):
                es.load_runtime_registry(path)

    def test_missing_heartbeat_source_raises(self):
        path = self._write(json.dumps(_registry({
            "name": "a", "host": "laptop", "deploy": "pm2",
            "deploy_path": "/x", "staleness_policy": "accepted"})))
        with self.assertRaises(ValueError):
            es.load_runtime_registry(path)


class RuntimeRegistrySourceTests(unittest.TestCase):
    """Registry resolution: explicit path, PAS_DIR git show origin/main,
    RUNTIME_REGISTRY/PAS_DIR env overrides."""

    def _write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".json",
                                        delete=False)
        f.write(text)
        f.close()
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        return f.name

    def _git_pas(self, registry_obj):
        """Tmp PAS checkout: runtime-registry.json committed and pinned
        as refs/remotes/origin/main, worktree then dirtied — git show
        must return the COMMITTED content, never the worktree."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        repo = d / "pas"
        repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(repo)] + args,
                           check=True, capture_output=True)
        (repo / "runtime-registry.json").write_text(
            json.dumps(registry_obj))
        subprocess.run(["git", "-C", str(repo), "add", "."],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "reg"],
                       check=True, capture_output=True)
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "-C", str(repo), "update-ref",
                        "refs/remotes/origin/main", sha],
                       check=True, capture_output=True)
        (repo / "runtime-registry.json").write_text(
            '{"components": []}')  # dirty worktree — must lose
        return repo

    def test_pas_dir_reads_origin_main_not_worktree(self):
        repo = self._git_pas(_registry(_comp("a")))
        reg = es.load_runtime_registry(pas_dir=str(repo), timeout=5)
        self.assertEqual(len(reg["components"]), 1)
        self.assertEqual(reg["components"][0]["name"], "a")

    def test_pas_dir_env_override(self):
        repo = self._git_pas(_registry(_comp("b")))
        with mock.patch.dict(os.environ, {"PAS_DIR": str(repo)}):
            reg = es.load_runtime_registry(timeout=5)
        self.assertEqual(reg["components"][0]["name"], "b")

    def test_runtime_registry_env_override(self):
        path = self._write(json.dumps(_registry(_comp("c"))))
        with mock.patch.dict(os.environ, {"RUNTIME_REGISTRY": path}):
            reg = es.load_runtime_registry(timeout=5)
        self.assertEqual(reg["components"][0]["name"], "c")

    def test_explicit_path_wins_over_pas_dir(self):
        repo = self._git_pas(_registry(_comp("pas")))
        path = self._write(json.dumps(_registry(_comp("explicit"))))
        reg = es.load_runtime_registry(path, pas_dir=str(repo),
                                       timeout=5)
        self.assertEqual(reg["components"][0]["name"], "explicit")


class HeartbeatJsonlTests(CollectRuntimeCase):
    def test_fresh_heartbeat_ok(self):
        with mock.patch.object(
                es, "_read_heartbeats",
                return_value={"tool-a": _hb_entry(60)}):
            rows = self.collect([_comp("comp-a", key="tool-a")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].state, "ok")
        self.assertEqual(rows[0].channel, "runtime")
        self.assertIn("last success", rows[0].note)

    def test_stale_heartbeat_warns(self):
        with mock.patch.object(
                es, "_read_heartbeats",
                return_value={"tool-a": _hb_entry(7200)}):
            rows = self.collect([_comp("comp-a", key="tool-a",
                                       max_age="1h")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("stale", rows[0].note)

    def test_err_streak_warns(self):
        with mock.patch.object(
                es, "_read_heartbeats",
                return_value={"tool-a": _hb_entry(60, fail_age_s=30)}):
            rows = self.collect([_comp("comp-a", key="tool-a")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("err streak", rows[0].note)

    def test_never_emitted_warns(self):
        rows = self.collect([_comp("comp-a", key="tool-a")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("no 'tool-a' heartbeat", rows[0].note)

    def test_host_drift_warns(self):
        """Laptop component whose heartbeat only exists on the VM ledger."""
        vm = _vm_probe(heartbeats={"tool-a": _hb_entry(30)})
        rows = self.collect([_comp("comp-a", key="tool-a")], vm=vm)
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("host drift", rows[0].note)

    def test_vm_component_uses_vm_probe(self):
        vm = _vm_probe(heartbeats={"tool-b": _hb_entry(30)})
        rows = self.collect(
            [_comp("comp-b", host="vm-qwenpaw", key="tool-b")], vm=vm)
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("last success", rows[0].note)

    def test_vm_unreachable_warns_not_crashes(self):
        rows = self.collect(
            [_comp("comp-b", host="vm-qwenpaw", key="tool-b")], vm=None)
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("unreachable", rows[0].note)


class HeartbeatPm2Tests(CollectRuntimeCase):
    def test_daemon_online_ok(self):
        vm = _vm_probe(pm2={"svc": {"status": "online",
                                    "pm_uptime": (NOW - 80000) * 1000,
                                    "cron_restart": None}})
        rows = self.collect(
            [_comp("svc", host="vm-qwenpaw", source="pm2", key="svc")],
            vm=vm)
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("online", rows[0].note)

    def test_daemon_stopped_warns(self):
        vm = _vm_probe(pm2={"svc": {"status": "stopped",
                                    "pm_uptime": NOW * 1000,
                                    "cron_restart": None}})
        rows = self.collect(
            [_comp("svc", host="vm-qwenpaw", source="pm2", key="svc")],
            vm=vm)
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("status=stopped", rows[0].note)

    def test_cron_restart_stopped_is_ok_when_fresh(self):
        """cron_restart jobs sit 'stopped' between ticks by design."""
        vm = _vm_probe(pm2={"job": {
            "status": "stopped", "pm_uptime": (NOW - 600) * 1000,
            "cron_restart": "*/20 * * * *"}})
        rows = self.collect(
            [_comp("job", host="vm-qwenpaw", source="pm2", key="job",
                   max_age="1h")], vm=vm)
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("cron_restart", rows[0].note)

    def test_cron_restart_stale_pm_uptime_warns(self):
        vm = _vm_probe(pm2={"job": {
            "status": "stopped", "pm_uptime": (NOW - 7200) * 1000,
            "cron_restart": "*/20 * * * *"}})
        rows = self.collect(
            [_comp("job", host="vm-qwenpaw", source="pm2", key="job",
                   max_age="1h")], vm=vm)
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("last start", rows[0].note)

    def test_pm2_missing_process_warns(self):
        vm = _vm_probe(pm2={})
        rows = self.collect(
            [_comp("ghost", host="vm-qwenpaw", source="pm2", key="ghost")],
            vm=vm)
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("not in pm2", rows[0].note)


class HeartbeatCronLogTests(CollectRuntimeCase):
    def test_journal_hit_ok(self):
        with mock.patch.object(
                es, "_cron_journal_hits",
                return_value={"myjob": _iso(NOW - 600)}):
            rows = self.collect(
                [_comp("myjob", source="cron-log", key="myjob",
                       max_age="2h")])
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("last cron-log activity", rows[0].note)

    def test_journal_stale_warns(self):
        with mock.patch.object(
                es, "_cron_journal_hits",
                return_value={"myjob": _iso(NOW - 5 * 3600)}):
            rows = self.collect(
                [_comp("myjob", source="cron-log", key="myjob",
                       max_age="2h")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("ago >", rows[0].note)

    def test_no_evidence_warns(self):
        rows = self.collect(
            [_comp("myjob", source="cron-log", key="myjob",
                   max_age="2h")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("no cron-log evidence", rows[0].note)

    def test_vm_cronlog_uses_remote_files(self):
        """VM cron-log evidence comes from the probe's cron_files map —
        candidate /root/logs/<key>.log hit -> ok."""
        cand = "/root/logs/job.log"
        vm = _vm_probe(cron_files={cand: {"mtime": NOW - 300,
                                          "size": 10, "key_found": True}})
        comp = _comp("job", host="vm-qwenpaw", source="cron-log",
                     key="job", max_age="1h",
                     deploy_path="/root/qwenpaw-queue/job.py")
        rows = self.collect([comp], vm=vm)
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("last cron-log activity", rows[0].note)


class HeartbeatGhRunTests(CollectRuntimeCase):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(
            self.tmp, ignore_errors=True))
        self.root = self.tmp / "eco"
        self.owners = {"devin-powerups": "Icaro0310",
                       "other-repo": "Icaro0310"}

    def _mk_repo(self, name, workflows=()):
        repo = self.root / name
        (repo / ".git").mkdir(parents=True, exist_ok=True)
        wf_dir = repo / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        for w in workflows:
            (wf_dir / w).write_text("name: x\n")
        return repo

    def _gh_with_runs(self, mapping):
        """mapping: {(owner, repo): [run dicts]} -> _gh_api side effect
        for the per-workflow runs endpoint."""
        def side_effect(owner, repo, path, timeout):
            if "/actions/workflows/" in path and "/runs" in path:
                return {"workflow_runs": mapping.get((owner, repo), [])}
            raise RuntimeError(f"unexpected gh path {path}")
        self.gh_api.side_effect = side_effect

    @staticmethod
    def _run(name, wf_file, age_s, conclusion="success"):
        return {"name": name, "path": f".github/workflows/{wf_file}",
                "created_at": _iso(NOW - age_s),
                "conclusion": conclusion, "status": "completed"}

    def _gh_comp(self, key="ci", deploy="github-actions",
                 deploy_file="ci.yml", repo="devin-powerups",
                 max_age="3d"):
        repo_dir = self._mk_repo(repo)
        return _comp(
            f"gh-{key}", host="github-actions", source="gh-run",
            key=key, max_age=max_age, deploy=deploy,
            deploy_path=str(repo_dir / ".github" / "workflows"
                            / deploy_file))

    def test_fresh_run_ok(self):
        comp = self._gh_comp()
        self._gh_with_runs({("Icaro0310", "devin-powerups"): [
            self._run("ci", "ci.yml", 3600)]})
        rows = self.collect([comp], owners=self.owners,
                            roots=[self.root])
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("last 'ci' run", rows[0].note)

    def test_stale_run_warns(self):
        comp = self._gh_comp(max_age="3d")
        self._gh_with_runs({("Icaro0310", "devin-powerups"): [
            self._run("ci", "ci.yml", 10 * 86400)]})
        rows = self.collect([comp], owners=self.owners,
                            roots=[self.root])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("ago >", rows[0].note)

    def test_no_matching_run_warns(self):
        comp = self._gh_comp()
        self._gh_with_runs({("Icaro0310", "devin-powerups"): [
            self._run("other", "other.yml", 3600)]})
        rows = self.collect([comp], owners=self.owners,
                            roots=[self.root])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("no 'ci' workflow runs", rows[0].note)

    def test_reusable_scans_caller_repos(self):
        """github-reusable heartbeat lives in caller workflows."""
        powerups = self._mk_repo("devin-powerups",
                                 ["pr-approve.yml"])
        self._mk_repo("other-repo", ["auto-approve.yml"])
        comp = _comp(
            "pr-approve", host="github-actions", source="gh-run",
            key="auto-approve", max_age="7d",
            deploy="github-reusable",
            deploy_path=str(powerups / ".github" / "workflows"
                            / "pr-approve.yml"))
        self._gh_with_runs({
            ("Icaro0310", "devin-powerups"): [],
            ("Icaro0310", "other-repo"): [
                self._run("auto-approve", "auto-approve.yml", 7200)],
        })
        rows = self.collect([comp], owners=self.owners,
                            roots=[self.root])
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("other-repo", rows[0].note)

    def test_gh_unreachable_warns(self):
        comp = self._gh_comp()
        self.gh_api.side_effect = RuntimeError("gh down")
        rows = self.collect([comp], owners=self.owners,
                            roots=[self.root])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("unreachable", rows[0].note)


class DeployFreshnessTests(CollectRuntimeCase):
    def test_git_deploy_clean_ok(self):
        with mock.patch.object(
                es, "_runtime_git_state",
                return_value={"toplevel": "/r", "head": "a" * 40,
                              "branch": "main", "upstream": "b" * 40,
                              "ahead": 0, "behind": 0}):
            rows = self.collect([_comp(
                "dep", source="none", deploy="git-pull-ff-only",
                deploy_path="/r/scripts/x.py", policy="abort-if-stale")])
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("== origin/main", rows[0].note)

    def test_git_deploy_behind_warns_abort_policy(self):
        with mock.patch.object(
                es, "_runtime_git_state",
                return_value={"toplevel": "/r", "head": "a" * 40,
                              "branch": "main", "upstream": "b" * 40,
                              "ahead": 0, "behind": 3}):
            rows = self.collect([_comp(
                "dep", source="none", deploy="git-pull-ff-only",
                deploy_path="/r/scripts/x.py", policy="abort-if-stale")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("3 behind", rows[0].note)

    def test_git_deploy_diverged_accepted_ok(self):
        with mock.patch.object(
                es, "_runtime_git_state",
                return_value={"toplevel": "/r", "head": "a" * 40,
                              "branch": "feat/x", "upstream": "b" * 40,
                              "ahead": 2, "behind": 1}):
            rows = self.collect([_comp(
                "dep", source="none", deploy="working-tree",
                deploy_path="/r/scripts/x.py", policy="accepted")])
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("staleness accepted", rows[0].note)

    def test_non_git_deploy_skips(self):
        rows = self.collect([_comp("dep", source="none", deploy="pm2")])
        self.assertEqual(rows[0].state, "skip")  # nothing to check
        self.assertNotIn("deploy:", rows[0].note)

    def test_policy_none_skips_deploy(self):
        with mock.patch.object(
                es, "_runtime_git_state") as m:
            rows = self.collect([_comp(
                "dep", source="none", deploy="git-pull-ff-only",
                deploy_path="/r/scripts/x.py", policy="none")])
        m.assert_not_called()
        self.assertNotIn("behind", rows[0].note)


class SystemdTests(CollectRuntimeCase):
    def test_active_service_ok(self):
        with mock.patch.object(es, "_systemctl_is_active",
                               return_value="active"):
            rows = self.collect([_comp(
                "svc", source="systemd", key="svc.service",
                deploy="systemd-user")])
        self.assertEqual(rows[0].state, "ok")

    def test_timer_driven_ok(self):
        def is_active(base, unit, timeout):
            return "inactive" if unit.endswith(".service") else "active"
        with mock.patch.object(es, "_systemctl_is_active",
                               side_effect=is_active), \
                mock.patch.object(es, "_timer_last_trigger",
                                  return_value=NOW - 3600):
            rows = self.collect([_comp(
                "job", source="systemd", key="job.service",
                max_age="25h", deploy="systemd-user")])
        self.assertEqual(rows[0].state, "ok")
        self.assertIn("timer-driven", rows[0].note)

    def test_failed_service_with_fresh_timer_warns(self):
        def is_active(base, unit, timeout):
            return "failed" if unit.endswith(".service") else "active"
        with mock.patch.object(es, "_systemctl_is_active",
                               side_effect=is_active), \
                mock.patch.object(es, "_timer_last_trigger",
                                  return_value=NOW - 3600):
            rows = self.collect([_comp(
                "job", source="systemd", key="job.service",
                max_age="25h", deploy="systemd-user")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("failed", rows[0].note)

    def test_inactive_no_timer_warns(self):
        with mock.patch.object(es, "_systemctl_is_active",
                               return_value="inactive"):
            rows = self.collect([_comp(
                "svc", source="systemd", key="svc.service",
                deploy="systemd-user")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("state=inactive", rows[0].note)


class MiscRuntimeTests(CollectRuntimeCase):
    def test_source_none_skips(self):
        rows = self.collect([_comp("boot", source="none", key="boot",
                                   deploy="cron-vm")])
        self.assertEqual(rows[0].state, "skip")

    def test_unknown_source_warns(self):
        rows = self.collect([_comp("x", source="bogus", key="x")])
        self.assertEqual(rows[0].state, "warn")
        self.assertIn("unknown heartbeat.source", rows[0].note)

    def test_offline_skips_remote_probes(self):
        called = []
        vm = _vm_probe()
        probe = lambda req, timeout: (called.append(req), vm)[1]
        rows = es.collect_runtime(
            _registry(
                _comp("vmc", host="vm-qwenpaw", key="t"),
                _comp("ghc", host="github-actions", source="gh-run",
                      key="ci", deploy="github-actions",
                      deploy_path="/r/p/.github/workflows/ci.yml"),
                _comp("lpc", key="tool-a")),
            {}, [Path("/nonexistent")], timeout=5, now=NOW, offline=True,
            vm_probe=probe)
        self.assertEqual(called, [])  # vm probe never invoked offline
        states = {r.product: r.state for r in rows}
        self.assertEqual(states["vmc"], "skip")   # offline -> skip
        self.assertEqual(states["ghc"], "skip")
        # laptop heartbeat still evaluated locally (warn: no entries)
        self.assertEqual(states["lpc"], "warn")


class MainRuntimeFlagTests(unittest.TestCase):
    def test_runtime_bad_registry_returns_2(self):
        missing = "/nonexistent/runtime-registry.json"
        rc = es.main(["--runtime", "--runtime-registry", missing,
                      "--ecosystem-root", "/nonexistent",
                      "--offline"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

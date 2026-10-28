"""Tests for check_required_checks.py — all gh calls are mocked; no live API."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_required_checks as crc  # noqa: E402


# ---------------------------------------------------------------------------
# parse_jobs / declared_contexts — pure filesystem legs
# ---------------------------------------------------------------------------

def write_workflow(repo: Path, name: str, body: str) -> Path:
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    p = wf / name
    p.write_text(body)
    return p


class TestParseJobs:
    def test_name_and_uses_at_job_level(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "ci.yml",
            """
name: ci
on: push
jobs:
  test:
    name: Test suite
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
  secrets-scan:
    uses: ./.github/workflows/scan.yml
""",
        )
        jobs = crc.parse_jobs(wf)
        assert jobs["test"]["name"] == "Test suite"
        assert jobs["test"]["uses"] is None
        # the - uses: inside steps must not be read as the job's uses:
        assert jobs["secrets-scan"]["uses"] == "./.github/workflows/scan.yml"

    def test_jobs_block_ends_at_next_top_level_key(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "ci.yml",
            """
jobs:
  a:
    runs-on: ubuntu-latest
concurrency:
  group: x
""",
        )
        assert list(crc.parse_jobs(wf)) == ["a"]

    def test_matrix_name_kept_for_pattern(self, tmp_path):
        wf = write_workflow(
            tmp_path,
            "c.yml",
            """
jobs:
  analyze:
    name: Analyze (${{ matrix.language }})
    strategy:
      matrix:
        language: [python]
""",
        )
        assert crc.parse_jobs(wf)["analyze"]["name"] == "Analyze (${{ matrix.language }})"


class TestDeclaredContexts:
    def test_plain_jobs_produce_name_or_id(self, tmp_path):
        write_workflow(
            tmp_path,
            "ci.yml",
            """
jobs:
  test:
    runs-on: ubuntu-latest
  lint:
    name: Lint everything
    runs-on: ubuntu-latest
""",
        )
        exact, patterns = crc.declared_contexts(tmp_path, {})
        assert exact == {"test", "Lint everything"}
        assert patterns == []

    def test_local_reusable_resolves_to_caller_inner(self, tmp_path):
        write_workflow(
            tmp_path,
            "ci.yml",
            """
on: push
jobs:
  secrets-scan:
    uses: ./.github/workflows/scan.yml
""",
        )
        write_workflow(
            tmp_path,
            "scan.yml",
            """
on:
  workflow_call:
jobs:
  scan:
    runs-on: ubuntu-latest
""",
        )
        exact, _ = crc.declared_contexts(tmp_path, {})
        # GitHub names reusable-call check runs `caller / callee job` —
        # the bare caller id alone is never a produced context, and the
        # callee's `scan` job produces nothing bare either (the file is
        # workflow_call-only, so it can never run by itself).
        assert exact == {"secrets-scan / scan"}

    def test_workflow_call_with_inputs_is_not_standalone(self, tmp_path):
        # The realistic reusable shape — `inputs:`/`outputs:` children of
        # workflow_call must not count as trigger events.
        write_workflow(
            tmp_path,
            "ci.yml",
            """
on: push
jobs:
  call:
    uses: ./.github/workflows/reuse.yml
""",
        )
        write_workflow(
            tmp_path,
            "reuse.yml",
            """
name: reuse
on:
  workflow_call:
    inputs:
      package-dir:
        type: string
    outputs:
      version:
        value: ${{ jobs.x.outputs.v }}
permissions:
  contents: read
jobs:
  x:
    outputs:
      v: ${{ steps.a.outputs.v }}
    steps:
      - id: a
        run: echo v=1 >> "$GITHUB_OUTPUT"
""",
        )
        exact, _ = crc.declared_contexts(tmp_path, {})
        assert exact == {"call / x"}

    def test_callable_plus_push_declares_bare(self, tmp_path):
        write_workflow(
            tmp_path,
            "w.yml",
            """
on:
  workflow_call:
  push:
    branches: [main]
jobs:
  j:
    runs-on: ubuntu-latest
""",
        )
        exact, _ = crc.declared_contexts(tmp_path, {})
        assert exact == {"j"}

    def test_callable_file_with_own_trigger_still_declares_bare(
        self, tmp_path
    ):
        write_workflow(
            tmp_path,
            "ci.yml",
            """
on: push
jobs:
  scan:
    uses: ./.github/workflows/scan.yml
""",
        )
        write_workflow(
            tmp_path,
            "scan.yml",
            """
on: [push, workflow_call]
jobs:
  scan:
    runs-on: ubuntu-latest
""",
        )
        exact, _ = crc.declared_contexts(tmp_path, {})
        assert exact == {"scan / scan", "scan"}

    def test_remote_reusable_resolves_via_registry_dirs(self, tmp_path):
        caller = tmp_path / "devin-x"
        write_workflow(
            caller,
            "ci.yml",
            """
jobs:
  secrets-scan:
    uses: Icaro0310/devin-powerups/.github/workflows/secrets-scan.yml@v1
""",
        )
        hub = tmp_path / "devin-powerups"
        write_workflow(
            hub,
            "secrets-scan.yml",
            """
jobs:
  secrets-scan:
    runs-on: ubuntu-latest
""",
        )
        dirs = {"icaro0310/devin-powerups": hub.resolve()}
        exact, _ = crc.declared_contexts(caller, dirs)
        assert exact == {"secrets-scan / secrets-scan"}

    def test_unresolvable_reusable_yields_wildcard(self, tmp_path):
        write_workflow(
            tmp_path,
            "ci.yml",
            """
jobs:
  audit:
    uses: other-org/somewhere/.github/workflows/audit.yml@main
""",
        )
        exact, _ = crc.declared_contexts(tmp_path, {})
        assert exact == {"audit / *"}

    def test_expression_name_becomes_pattern(self, tmp_path):
        write_workflow(
            tmp_path,
            "c.yml",
            """
jobs:
  analyze:
    name: Analyze (${{ matrix.language }})
""",
        )
        exact, patterns = crc.declared_contexts(tmp_path, {})
        assert exact == set()
        assert len(patterns) == 1
        assert crc.covered("Analyze (python)", set(), exact, patterns)
        assert not crc.covered("Analyze", set(), exact, patterns)


class TestCovered:
    def test_exact_and_wildcard(self):
        assert crc.covered("a / b", {"a / b"}, set(), [])
        assert crc.covered("a / b", set(), {"a / b"}, [])
        assert crc.covered("a / anything", set(), {"a / *"}, [])
        assert not crc.covered("a", set(), {"a / *"}, [])
        assert not crc.covered("a / b", set(), {"a / c"}, [])


# ---------------------------------------------------------------------------
# collect_repo / audit_repo — gh_api mocked per path
# ---------------------------------------------------------------------------

def fake_api(responses):
    """Fixture dispatcher: keys are regexes searched against the gh path.

    Anchored on `$` where order matters — the bare `repos/OWNER/r$` meta
    key must not swallow `repos/OWNER/r/branches/main` (substring or
    longest-prefix dispatch would both get this wrong).
    """

    def _api(path, errors):
        for pattern, payload in responses.items():
            if re.search(pattern, path):
                if isinstance(payload, Exception):
                    errors.append(f"gh api {path}: {payload}")
                    return {}
                return payload
        errors.append(f"gh api {path}: no fixture")
        return {}

    return _api


def base_responses(**over):
    """Healthy repo: protected branch, required `test` which is observed."""
    resp = {
        r"branches/main$": {
            "protected": True,
            "protection": {
                "enabled": True,
                "required_status_checks": {
                    "enforcement_level": "non_admins",
                    "contexts": ["test"],
                    "checks": [{"context": "test", "app_id": 15368}],
                },
            },
        },
        r"rulesets\?includes_parents": [],
        "check-runs": {"check_runs": [{"name": "test"}, {"name": "lint"}]},
        r"status$": {"statuses": []},
        "pulls": [],
        "permissions/workflow": {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": True,
        },
    }
    resp.update(over)
    meta = over.pop("meta", None) or {
        "default_branch": "main",
        "archived": False,
    }
    resp[r"repos/OWNER/r$"] = meta
    return resp


def run_collect(monkeypatch, responses, prs=0):
    monkeypatch.setattr(crc, "gh_api", fake_api(responses))
    return crc.collect_repo("OWNER", "r", prs)


class TestCollectRepo:
    def test_required_from_branch_protection(self, monkeypatch):
        r = run_collect(monkeypatch, base_responses())
        assert r["required"] == ["test"]
        assert r["can_approve"] is True
        assert "test" in r["observed_names"]

    def test_ghost_context_shape(self, monkeypatch):
        # The 2026-10-08 incident verbatim: required `secrets-scan`, real
        # check run `secrets-scan / secrets-scan` from a reusable call.
        resp = base_responses(
            **{
                r"branches/main$": {
                    "protected": True,
                    "protection": {
                        "enabled": True,
                        "required_status_checks": {
                            "enforcement_level": "non_admins",
                            "contexts": ["secrets-scan"],
                        },
                    },
                },
                "check-runs": {
                    "check_runs": [{"name": "secrets-scan / secrets-scan"}]
                },
            }
        )
        r = run_collect(monkeypatch, resp)
        assert r["required"] == ["secrets-scan"]

    def test_checks_key_shape(self, monkeypatch):
        # Newer API shape carries checks[{context, app_id}] — both must
        # be unioned, not just the legacy `contexts` list.
        resp = base_responses(
            **{
                r"branches/main$": {
                    "protected": True,
                    "protection": {
                        "enabled": True,
                        "required_status_checks": {
                            "enforcement_level": "non_admins",
                            "checks": [{"context": "lint", "app_id": 15368}],
                        },
                    },
                },
            }
        )
        r = run_collect(monkeypatch, resp)
        assert r["required"] == ["lint"]

    def test_ruleset_contexts_included(self, monkeypatch):
        resp = base_responses(
            **{
                r"rulesets\?includes_parents": [{"id": 7, "enforcement": "active"}],
                r"rulesets/7$": {
                    "enforcement": "active",
                    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}},
                    "rules": [
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "ruleset-gate"}
                                ]
                            },
                        }
                    ],
                },
            }
        )
        r = run_collect(monkeypatch, resp)
        assert "ruleset-gate" in r["required"]

    def test_evaluate_ruleset_ignored(self, monkeypatch):
        resp = base_responses(
            **{
                r"rulesets\?includes_parents": [{"id": 7}],
                r"rulesets/7$": {
                    "enforcement": "evaluate",
                    "rules": [
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "eval-only"}
                                ]
                            },
                        }
                    ],
                },
            }
        )
        r = run_collect(monkeypatch, resp)
        assert "eval-only" not in r["required"]

    def test_ruleset_not_targeting_default_ignored(self, monkeypatch):
        resp = base_responses(
            **{
                r"rulesets\?includes_parents": [{"id": 7}],
                r"rulesets/7$": {
                    "enforcement": "active",
                    "conditions": {
                        "ref_name": {"include": ["refs/heads/release/*"]}
                    },
                    "rules": [
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "release-only"}
                                ]
                            },
                        }
                    ],
                },
            }
        )
        r = run_collect(monkeypatch, resp)
        assert "release-only" not in r["required"]

    def test_pr_head_check_runs_observed(self, monkeypatch):
        resp = base_responses(
            **{
                "pulls": [{"head": {"sha": "abc123"}}],
            }
        )
        calls = []
        inner = fake_api(resp)

        def api(path, errors):
            calls.append(path)
            return inner(path, errors)

        monkeypatch.setattr(crc, "gh_api", api)
        r = crc.collect_repo("OWNER", "r", 5)
        assert any("abc123/check-runs" in c for c in calls)
        assert "test" in r["observed_names"]

    def test_archived_repo_skipped(self, monkeypatch):
        resp = base_responses()
        resp[r"repos/OWNER/r$"] = {"default_branch": "main", "archived": True}
        r = run_collect(monkeypatch, resp)
        assert r["skipped"] is True
        assert r["required"] == []

    def test_unprotected_branch_noted(self, monkeypatch):
        resp = base_responses(**{r"branches/main$": {"protected": False}})
        r = run_collect(monkeypatch, resp)
        assert r["required"] == []
        assert any("no branch protection" in n for n in r["notes"])

    def test_can_approve_unreadable_is_note_not_flag(self, monkeypatch):
        resp = base_responses()
        del resp["permissions/workflow"]
        r = run_collect(monkeypatch, resp)
        assert r["can_approve"] is None
        assert any("can_approve" in n for n in r["notes"])

    def test_api_failure_recorded_not_raised(self, monkeypatch):
        resp = {r"repos/OWNER/r$": RuntimeError("boom")}
        r = run_collect(monkeypatch, resp)
        assert r["errors"]


class TestAuditRepo:
    def test_orphan_detected(self, monkeypatch, tmp_path):
        resp = base_responses(
            **{
                r"branches/main$": {
                    "protected": True,
                    "protection": {
                        "enabled": True,
                        "required_status_checks": {"contexts": ["old-name"]},
                    },
                },
                "check-runs": {"check_runs": [{"name": "new-name"}]},
            }
        )
        monkeypatch.setattr(crc, "gh_api", fake_api(resp))
        write_workflow(
            tmp_path,
            "ci.yml",
            "jobs:\n  new-name:\n    runs-on: ubuntu-latest\n",
        )
        r = crc.audit_repo("OWNER", "r", tmp_path, {}, 0)
        assert r["orphans"] == ["old-name"]

    def test_required_covered_by_declared_job(self, monkeypatch, tmp_path):
        # pull_request-only job: never observed on main, but declared —
        # not an orphan.
        resp = base_responses(
            **{
                r"branches/main$": {
                    "protected": True,
                    "protection": {
                        "enabled": True,
                        "required_status_checks": {"contexts": ["label"]},
                    },
                },
                "check-runs": {"check_runs": []},
            }
        )
        monkeypatch.setattr(crc, "gh_api", fake_api(resp))
        write_workflow(
            tmp_path,
            "labeler.yml",
            "jobs:\n  label:\n    permissions:\n      contents: read\n",
        )
        r = crc.audit_repo("OWNER", "r", tmp_path, {}, 0)
        assert r["orphans"] == []

    def test_bare_required_not_covered_by_reusable_declared(
        self, monkeypatch, tmp_path
    ):
        # Required 'secrets-scan' while the workflow only declares a
        # reusable call that produces 'secrets-scan / *' — the ghost.
        resp = base_responses(
            **{
                r"branches/main$": {
                    "protected": True,
                    "protection": {
                        "enabled": True,
                        "required_status_checks": {"contexts": ["secrets-scan"]},
                    },
                },
                "check-runs": {
                    "check_runs": [{"name": "secrets-scan / secrets-scan"}]
                },
            }
        )
        monkeypatch.setattr(crc, "gh_api", fake_api(resp))
        write_workflow(
            tmp_path,
            "ci.yml",
            "on: push\njobs:\n  secrets-scan:\n    uses: ./.github/workflows/s.yml\n",
        )
        write_workflow(
            tmp_path,
            "s.yml",
            "on:\n  workflow_call:\njobs:\n  secrets-scan:\n    runs-on: ubuntu-latest\n",
        )
        r = crc.audit_repo("OWNER", "r", tmp_path, {}, 0)
        assert r["orphans"] == ["secrets-scan"]


# ---------------------------------------------------------------------------
# registry_repos — product rows collapse to unique repos
# ---------------------------------------------------------------------------

class TestRegistryRepos:
    def test_product_rows_dedupe_to_their_monorepo(
        self, monkeypatch, tmp_path
    ):
        hub = tmp_path / "hub"
        hub.mkdir()
        (hub / "registry.json").write_text(json.dumps({
            "repositories": [
                {
                    "name": "devin-explore",
                    "visibility": "public",
                    "url": "https://github.com/Icaro0310/devin-explore",
                },
                {
                    "name": "devin-history",  # absorbed product row
                    "visibility": "public",
                    "url": "https://github.com/Icaro0310/devin-explore",
                    "local_dir": "devin-explore",
                },
                {
                    "name": "private-thing",
                    "visibility": "private",
                    "url": "https://github.com/Icaro0310/private-thing",
                },
                {"name": "no-url-repo", "visibility": "public"},
            ]
        }))
        monkeypatch.setattr(crc, "HUB", hub)
        repos = crc.registry_repos(tmp_path)
        names = [r[1] for r in repos]
        assert sorted(names) == ["devin-explore", "no-url-repo"]

    def test_registry_missing_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(crc, "HUB", tmp_path / "nohub")
        assert crc.registry_repos(tmp_path) == []


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain:
    def _patch(self, monkeypatch, responses):
        monkeypatch.setattr(crc, "gh_api", fake_api(responses))

    def test_repo_flag_and_clean_exit(self, monkeypatch, tmp_path, capsys):
        self._patch(monkeypatch, base_responses())
        rc = crc.main(["--repo", "OWNER/r", "--root", str(tmp_path), "--prs", "0"])
        assert rc == 0
        assert "ok:" in capsys.readouterr().out

    def test_orphan_exits_one(self, monkeypatch, tmp_path, capsys):
        resp = base_responses(
            **{
                r"branches/main$": {
                    "protected": True,
                    "protection": {
                        "enabled": True,
                        "required_status_checks": {"contexts": ["ghost"]},
                    },
                },
                "check-runs": {"check_runs": []},
            }
        )
        self._patch(monkeypatch, resp)
        rc = crc.main(["--repo", "OWNER/r", "--root", str(tmp_path), "--prs", "0"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "ORPHAN" in out and "ghost" in out

    def test_can_approve_false_exits_one(self, monkeypatch, tmp_path, capsys):
        resp = base_responses(
            **{
                "permissions/workflow": {
                    "can_approve_pull_request_reviews": False
                }
            }
        )
        self._patch(monkeypatch, resp)
        rc = crc.main(["--repo", "OWNER/r", "--root", str(tmp_path), "--prs", "0"])
        assert rc == 1
        assert "can_approve" in capsys.readouterr().out

    def test_json_output(self, monkeypatch, tmp_path, capsys):
        resp = base_responses(
            **{
                r"branches/main$": {
                    "protected": True,
                    "protection": {
                        "enabled": True,
                        "required_status_checks": {"contexts": ["ghost"]},
                    },
                },
                "check-runs": {"check_runs": []},
            }
        )
        self._patch(monkeypatch, resp)
        rc = crc.main(
            ["--repo", "OWNER/r", "--root", str(tmp_path), "--prs", "0", "--json"]
        )
        assert rc == 1
        data = json.loads(capsys.readouterr().out)
        assert data["orphans"] == {"r": ["ghost"]}

    def test_total_api_failure_exits_two(self, monkeypatch, tmp_path):
        def boom(path, errors):
            errors.append(f"gh api {path}: boom")
            return {}

        monkeypatch.setattr(crc, "gh_api", boom)
        rc = crc.main(["--repo", "OWNER/r", "--root", str(tmp_path), "--prs", "0"])
        assert rc == 2

    def test_owner_slash_repo_spec(self, monkeypatch, tmp_path):
        seen = []

        def api(path, errors):
            seen.append(path)
            if "branches/main" in path:
                return {"protected": False}
            if "rulesets" in path:
                return []
            if "check-runs" in path:
                return {"check_runs": []}
            if "status" in path:
                return {"statuses": []}
            if "permissions" in path:
                return {"can_approve_pull_request_reviews": True}
            if "repos/other/x" in path:
                return {"default_branch": "main"}
            return {}

        monkeypatch.setattr(crc, "gh_api", api)
        rc = crc.main(["--repo", "other/x", "--root", str(tmp_path), "--prs", "0"])
        assert rc == 0
        assert any("repos/other/x" in p for p in seen)

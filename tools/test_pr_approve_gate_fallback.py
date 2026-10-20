"""pr-approve gate fallback — the real workflow run-blocks vs stubbed `gh`.

Executes the bash `run:` blocks of the `findings` and `Approve` steps
from `.github/workflows/pr-approve.yml` verbatim (extracted from the
YAML, never re-implemented) against a `gh` stub that serves fixture
JSON. Covers the v1.4 fallback predicate (D-2026-10-20):

(a) unresolved bug thread + qualified reply citing a fix commit that is
    an ancestor of a clean-re-reviewed head -> non-blocking, logged
    `fallback-resolved:`, counted in `fallback_resolutions`;
(b) reply without a commit token -> still blocking;
(c) reply citing a sha that is NOT an ancestor of the head -> still
    blocking;
(d) thread resolved by the Devin bot -> non-blocking via the primary
    path, no fallback traffic at all;
plus the safety rails: zero replies, unprivileged reply authors,
unknown commits, and a non-success head status all keep blocking.
"""

import json
import os
import re
import stat
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-approve.yml"
HEAD_SHA = "3eeaf7f91a1e4382785746f20a944790033860f6"
FIX_SHA = "55ded04"
PR_AUTHOR = "Icaro0310"
BOT = "devin-ai-integration"

GH_STUB = r"""#!/usr/bin/env bash
# `gh` test stub: logs every call to GH_STUB_LOG, serves GH_FIXTURE_DIR.
set -u
echo "gh $*" >> "${GH_STUB_LOG:?missing GH_STUB_LOG}"
[ "${1:-}" = "pr" ] && exit 0
[ "${1:-}" = "api" ] || { echo "unstubbed: $*" >&2; exit 1; }
shift
endpoint="" ; jqexpr="" ; pr=""
args=("$@") ; i=0
while [ $i -lt ${#args[@]} ]; do
  a="${args[$i]}"
  case "$a" in
    --jq|-q) i=$((i+1)); jqexpr="${args[$i]:-}" ;;
    -F|-f|--field|--raw-field|-X|--method|-H|--header|--input|--cache|--hostname)
      i=$((i+1))
      case "${args[$i]:-}" in pr=*) pr="${args[$i]#pr=}" ;; esac ;;
    -*) ;;
    *) [ -z "$endpoint" ] && endpoint="$a" ;;
  esac
  i=$((i+1))
done
out=""
case "$endpoint" in
  graphql)
    f="$GH_FIXTURE_DIR/graphql_pr${pr:-1}.json"
    [ -f "$f" ] || { echo "no fixture $f" >&2; exit 1; }
    out=$(cat "$f") ;;
  repos/*/commits/*/status)
    out=$(cat "$GH_FIXTURE_DIR/status.json") ;;
  repos/*/compare/*)
    pair="${endpoint##*/compare/}"
    if jq -e --arg p "$pair" 'has($p)' "$GH_FIXTURE_DIR/compares.json" >/dev/null 2>&1; then
      out=$(jq -c --arg p "$pair" '.[$p]' "$GH_FIXTURE_DIR/compares.json")
    else
      echo "gh: Not Found (HTTP 404)" >&2; exit 1
    fi ;;
  repos/*/commits/*)
    sha="${endpoint##*/commits/}"
    if jq -e --arg s "$sha" 'index($s)' "$GH_FIXTURE_DIR/compares.json" >/dev/null 2>&1 \
       || jq -e --arg s "$sha" 'index($s)' "$GH_FIXTURE_DIR/commits.json" >/dev/null 2>&1; then
      out="{\"sha\": \"$sha\"}"
    else
      echo "gh: Not Found (HTTP 404)" >&2; exit 1
    fi ;;
  *) echo "unstubbed api endpoint: $endpoint" >&2; exit 1 ;;
esac
if [ -n "$jqexpr" ]; then echo "$out" | jq -r "$jqexpr"; else echo "$out"; fi
"""

FINDING_BODY = '{"kind": "bug", "severity": "high"} finding text'


def comment(author, body, assoc="NONE"):
    return {
        "author": {"login": author},
        "authorAssociation": assoc,
        "originalCommit": {"oid": "0" * 40},
        "body": body,
    }


def thread(tid, replies=(), resolved=False, resolved_by=None,
           outdated=False, first_body=FINDING_BODY, first_author=BOT):
    nodes = [comment(first_author, first_body)]
    for author, assoc, body in replies:
        nodes.append(comment(author, body, assoc))
    return {
        "id": tid,
        "isResolved": resolved,
        "isOutdated": outdated,
        "resolvedBy": {"login": resolved_by} if resolved_by else None,
        "comments": {"nodes": nodes},
    }


def graphql_fixture(threads, author=PR_AUTHOR):
    return {
        "data": {"repository": {"pullRequest": {
            "author": {"login": author},
            "reviewThreads": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": threads,
            },
        }}}
    }


def status_fixture(state="success"):
    return {"statuses": [{
        "context": "Devin Review",
        "state": state,
        "avatar_url": "https://avatars.githubusercontent.com/in/811515?v=4",
    }]}


def extract_run_block(workflow_text, marker):
    """Literal `run: |` block of the step containing `marker`."""
    lines = workflow_text.splitlines()
    i = next(n for n, l in enumerate(lines) if marker in l)
    j = next(n for n in range(i, len(lines))
             if lines[n].strip() == "run: |")
    indent = len(lines[j]) - len(lines[j].lstrip())
    block = []
    for l in lines[j + 1:]:
        if l.strip():
            cur = len(l) - len(l.lstrip())
            if cur <= indent:
                break
        block.append(l[indent + 2:] if l.startswith(" " * (indent + 2)) else l)
    return "\n".join(block)


class GateFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()
        cls.findings = extract_run_block(cls.text, "id: findings")
        cls.approve = extract_run_block(
            cls.text, "name: Approve PRs with no blocking findings")
        # the fixture block must be the fallback-aware version
        assert "fallback-resolved" in cls.findings
        assert "gate-resolved-via" in cls.approve

    def run_block(self, block, fixtures, extra_env=None):
        """Run an extracted run-block with the gh stub; return (outputs,
        stdout, stub_log)."""
        with TemporaryDirectory() as td:
            td = Path(td)
            bindir = td / "bin"
            fxdir = td / "fixtures"
            bindir.mkdir()
            fxdir.mkdir()
            stub = bindir / "gh"
            stub.write_text(GH_STUB)
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            for name, data in fixtures.items():
                (fxdir / name).write_text(
                    data if isinstance(data, str) else json.dumps(data))
            out_file = td / "github_output"
            out_file.touch()
            log_file = td / "gh_calls.log"
            log_file.touch()
            env = dict(os.environ)
            env.update({
                "PATH": f"{bindir}:{os.environ['PATH']}",
                "REPO": "Icaro0310/devin-test",
                "PR_NUMBERS": "5",
                "HEAD_SHA": HEAD_SHA,
                "GH_TOKEN": "test-token",
                "GITHUB_OUTPUT": str(out_file),
                "GITHUB_EVENT_NAME": "pull_request_target",
                "GH_STUB_LOG": str(log_file),
                "GH_FIXTURE_DIR": str(fxdir),
            })
            env.update(extra_env or {})
            proc = subprocess.run(
                ["bash", "-c", block], env=env,
                capture_output=True, text=True, timeout=60)
            outputs = {}
            for line in out_file.read_text().splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    outputs[k] = v
            return proc, outputs, log_file.read_text()

    def base_fixtures(self, threads, compares=None, commits=None,
                      status="success"):
        return {
            "graphql_pr5.json": graphql_fixture(threads),
            "compares.json": compares if compares is not None else {},
            "commits.json": commits if commits is not None else [FIX_SHA],
            "status.json": status_fixture(status),
        }

    # --- the four spec fixtures ---------------------------------------

    def test_a_reply_with_verified_commit_clears_via_fallback(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "NONE", f"Fixed in {FIX_SHA} — shim probes now"),
            (PR_AUTHOR, "NONE", "all green locally"),
        ])]
        fx = self.base_fixtures(
            threads, compares={f"{FIX_SHA}...{HEAD_SHA}": {"status": "ahead"}})
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 1})
        self.assertEqual(json.loads(out["fallback_threads"]),
                         {"5": [f"T1@{FIX_SHA}"]})
        self.assertIn(f"fallback-resolved: PR #5 thread T1 via commit {FIX_SHA}",
                      proc.stdout)
        self.assertIn(f"commits/{HEAD_SHA}/status", log)  # head status consulted

    def test_a2_collaborator_reply_also_qualifies(self):
        threads = [thread("T2", replies=[
            ("teammate", "COLLABORATOR", f"fixed by {FIX_SHA}"),
        ])]
        fx = self.base_fixtures(
            threads,
            compares={f"{FIX_SHA}...{HEAD_SHA}": {"status": "identical"}})
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 1})

    def test_b_reply_without_commit_still_blocking(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", "fixed it, please re-check"),
        ])]
        proc, out, log = self.run_block(
            self.findings, self.base_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 0})
        self.assertNotIn("fallback-resolved", proc.stdout)
        self.assertNotIn("compare", log)

    def test_c_non_ancestor_sha_still_blocking(self):
        for status in ("diverged", "behind"):
            with self.subTest(compare_status=status):
                threads = [thread("T1", replies=[
                    (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}"),
                ])]
                fx = self.base_fixtures(
                    threads,
                    compares={f"{FIX_SHA}...{HEAD_SHA}": {"status": status}})
                proc, out, _ = self.run_block(self.findings, fx)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(out["blocking"], "1")
                self.assertNotIn("fallback-resolved", proc.stdout)

    def test_d_bot_resolved_stays_primary_nonblocking(self):
        threads = [thread("T1", resolved=True,
                          resolved_by="devin-ai-integration[bot]",
                          replies=[(PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}")])]
        fx = self.base_fixtures(threads)
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 0})
        # never reached the fallback machinery: graphql only, no REST
        self.assertNotIn("/commits/", log)
        self.assertNotIn("/compare/", log)

    # --- safety rails --------------------------------------------------

    def test_zero_replies_still_blocking(self):
        threads = [thread("T1")]
        proc, out, _ = self.run_block(
            self.findings, self.base_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_unqualified_reply_author_still_blocking(self):
        threads = [thread("T1", replies=[
            ("mallory", "NONE", f"Fixed in {FIX_SHA} trust me"),
            ("driveby", "CONTRIBUTOR", f"yes {FIX_SHA} is the fix"),
        ])]
        fx = self.base_fixtures(
            threads, compares={f"{FIX_SHA}...{HEAD_SHA}": {"status": "ahead"}})
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")
        self.assertNotIn("compare", log)  # shas never even extracted

    def test_unknown_commit_still_blocking(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}"),
        ])]
        fx = self.base_fixtures(threads, commits=[], compares={})
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_no_success_status_still_blocking(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}"),
        ])]
        for state in ("pending", "failure"):
            with self.subTest(devin_state=state):
                fx = self.base_fixtures(
                    threads,
                    compares={f"{FIX_SHA}...{HEAD_SHA}": {"status": "ahead"}},
                    status=state)
                proc, out, _ = self.run_block(self.findings, fx)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(out["blocking"], "1")

    def test_outdated_and_nonfinding_threads_ignored(self):
        threads = [
            thread("T-out", outdated=True, replies=[
                (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}")]),
            thread("T-doc", first_body='{"kind": "docs"} note', replies=[
                (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}")]),
            thread("T-real", replies=[
                (PR_AUTHOR, "OWNER", "no sha here")]),
        ]
        proc, out, _ = self.run_block(
            self.findings, self.base_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")  # only T-real counts

    def test_second_token_resolves_after_invalid_first(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"first tried {FIX_SHA} then rebased"),
            (PR_AUTHOR, "OWNER", "final fix in 0badf00"),
        ])]
        fx = self.base_fixtures(
            threads,
            commits=[FIX_SHA, "0badf00"],
            compares={
                f"{FIX_SHA}...{HEAD_SHA}": {"status": "diverged"},
                f"0badf00...{HEAD_SHA}": {"status": "ahead"},
            })
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertIn("via commit 0badf00", proc.stdout)

    # --- approve step: the public fallback comment ---------------------

    def approve_env(self, **over):
        env = {
            "VERDICT_MAP": '{"5": "STATUS_CLEAN"}',
            "BLOCKING_MAP": '{"5": 0}',
            "FALLBACK_MAP": '{"5": 1}',
            "FALLBACK_THREADS": f'{{"5": ["T1@{FIX_SHA}"]}}',
        }
        env.update(over)
        return env

    def test_approve_posts_gate_resolved_comment(self):
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        proc, _, log = self.run_block(
            self.approve, fx, extra_env=self.approve_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pr review --approve", log)
        self.assertIn("gate-resolved-via: fallback", log)
        self.assertIn("T1", log)
        self.assertIn(FIX_SHA, log)
        self.assertIn("Threads left unresolved", log)

    def test_approve_without_fallback_posts_no_comment(self):
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        env = self.approve_env(FALLBACK_MAP='{"5": 0}',
                               FALLBACK_THREADS='{"5": []}')
        proc, _, log = self.run_block(self.approve, fx, extra_env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pr review --approve", log)
        self.assertNotIn("pr comment", log)

    def test_approve_held_pr_posts_nothing(self):
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        env = self.approve_env(BLOCKING_MAP='{"5": 2}', FALLBACK_MAP='{"5": 0}',
                               FALLBACK_THREADS='{"5": []}')
        proc, _, log = self.run_block(self.approve, fx, extra_env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("pr review --approve", log)
        self.assertNotIn("pr comment", log)


if __name__ == "__main__":
    unittest.main()

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

v1.5 additions: cross-repo `repo@sha` cites (only the gate's own repo,
owner case-insensitive, committer-date postdate instead of ancestry)
and the manual-blocking0 delivery path (clean evaluation + undeliverable
APPROVE review -> green check with audit comment; other errors fail).
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
FBASE_SHA = "aaa111aaa111aaa111aaa111aaa111aaa111aaa1"
PR_AUTHOR = "Icaro0310"
BOT = "devin-ai-integration"

GH_STUB = r"""#!/usr/bin/env bash
# `gh` test stub: logs every call to GH_STUB_LOG, serves GH_FIXTURE_DIR.
set -u
echo "gh $*" >> "${GH_STUB_LOG:?missing GH_STUB_LOG}"
if [ "${1:-}" = "pr" ]; then
  # Knobs for the manual-blocking0 path: deny the APPROVE review with the
  # real GitHub message, a different error, or fail the audit comment.
  if [ "${2:-}" = "review" ] && [ "${GH_STUB_PR_REVIEW_FAIL:-}" = "deny" ]; then
    echo "gh: GraphQL: GitHub Actions is not permitted to approve pull requests. (addPullRequestReview)" >&2
    exit 1
  fi
  if [ "${2:-}" = "review" ] && [ "${GH_STUB_PR_REVIEW_FAIL:-}" = "other" ]; then
    echo "gh: upstream timed out (HTTP 502)" >&2
    exit 1
  fi
  if [ "${2:-}" = "comment" ] && [ -n "${GH_STUB_PR_COMMENT_FAIL:-}" ]; then
    echo "gh: Not Found (HTTP 404)" >&2
    exit 1
  fi
  exit 0
fi
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
    # commits.json may be a list of existing shas (old date default) or
    # an object mapping sha -> committer date (drives the cross-repo
    # postdate check).
    date=$(jq -r --arg s "$sha" \
      'if type=="object" then .[$s] // empty
       else (if index($s) then "2000-01-01T00:00:00Z" else empty end) end' \
      "$GH_FIXTURE_DIR/commits.json" 2>/dev/null || true)
    if [ -z "$date" ] && jq -e --arg s "$sha" 'index($s) != null' "$GH_FIXTURE_DIR/compares.json" >/dev/null 2>&1; then
      date="2000-01-01T00:00:00Z"
    fi
    [ -n "$date" ] || { echo "gh: Not Found (HTTP 404)" >&2; exit 1; }
    out="{\"sha\": \"$sha\", \"commit\": {\"committer\": {\"date\": \"$date\"}}}" ;;
  *) echo "unstubbed api endpoint: $endpoint" >&2; exit 1 ;;
esac
if [ -n "$jqexpr" ]; then echo "$out" | jq -r "$jqexpr"; else echo "$out"; fi
"""

FINDING_BODY = '{"kind": "bug", "severity": "high"} finding text'


def comment(cid, author, body, assoc="NONE", base=FBASE_SHA):
    return {
        "id": cid,
        "author": {"login": author},
        "authorAssociation": assoc,
        "originalCommit": {"oid": base},
        "body": body,
    }


def thread(tid, replies=(), resolved=False, resolved_by=None,
           outdated=False, first_body=FINDING_BODY, first_author=BOT,
           base=FBASE_SHA, deep=False):
    """`comments(first: 1)` + `replies: comments(last: 50)` shape.

    Short threads: the finding rides inside the last-50 window, the jq
    filter drops it by id. `deep=True` simulates a >50-comment thread:
    the finding is outside the replies window entirely.
    """
    first = comment(f"{tid}-c0", first_author, first_body, base=base)
    reply_nodes = [
        comment(f"{tid}-c{n + 1}", author, body, assoc)
        for n, (author, assoc, body) in enumerate(replies)
    ]
    window = reply_nodes if deep else [first] + reply_nodes
    return {
        "id": tid,
        "isResolved": resolved,
        "isOutdated": outdated,
        "resolvedBy": {"login": resolved_by} if resolved_by else None,
        "comments": {"nodes": [first]},
        "replies": {"nodes": window},
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

    def ok_compares(self, sha=FIX_SHA, head_status="ahead"):
        """Both ancestry legs for a clean fallback: sha inside the head
        AND sha strictly after the finding's commit."""
        return {
            f"{sha}...{HEAD_SHA}": {"status": head_status},
            f"{FBASE_SHA}...{sha}": {"status": "ahead"},
        }

    # --- the four spec fixtures ---------------------------------------

    def test_a_reply_with_verified_commit_clears_via_fallback(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "NONE", f"Fixed in {FIX_SHA} — shim probes now"),
            (PR_AUTHOR, "NONE", "all green locally"),
        ])]
        fx = self.base_fixtures(threads, compares=self.ok_compares())
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 1})
        self.assertEqual(json.loads(out["fallback_threads"]),
                         {"5": [f"T1|{FIX_SHA}"]})
        self.assertIn(f"fallback-resolved: PR #5 thread T1 via commit {FIX_SHA}",
                      proc.stdout)
        self.assertIn(f"commits/{HEAD_SHA}/status", log)  # head status consulted

    def test_a2_collaborator_reply_also_qualifies(self):
        threads = [thread("T2", replies=[
            ("teammate", "COLLABORATOR", f"fixed by {FIX_SHA}"),
        ])]
        fx = self.base_fixtures(threads, compares=self.ok_compares())
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 1})

    def test_a3_fix_commit_is_the_head_itself(self):
        # `identical` to head still clears — the push after the finding
        # IS the fix (postdate check passes on head...fix ancestry).
        threads = [thread("T2", replies=[
            (PR_AUTHOR, "OWNER", f"last commit is the fix: {HEAD_SHA}"),
        ])]
        fx = self.base_fixtures(
            threads,
            commits=[HEAD_SHA],
            compares={
                f"{HEAD_SHA}...{HEAD_SHA}": {"status": "identical"},
                f"{FBASE_SHA}...{HEAD_SHA}": {"status": "ahead"},
            })
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")

    def test_a4_deep_thread_reply_past_first_page(self):
        # >50 comments on the thread: the finding left the last-50
        # replies window, the fix reply stayed inside it.
        threads = [thread("T2", deep=True, replies=[
            (PR_AUTHOR, "NONE", f"Fixed in {FIX_SHA}"),
        ])]
        fx = self.base_fixtures(threads, compares=self.ok_compares())
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

    def test_c2_sha_not_after_finding_still_blocking(self):
        # citing the flagged commit itself (identical) or an older one
        # (behind) proves no fix — even with head ancestry + clean status
        for status in ("identical", "behind"):
            with self.subTest(finding_cmp=status):
                threads = [thread("T1", replies=[
                    (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}"),
                ])]
                fx = self.base_fixtures(threads, compares={
                    f"{FIX_SHA}...{HEAD_SHA}": {"status": "ahead"},
                    f"{FBASE_SHA}...{FIX_SHA}": {"status": status},
                })
                proc, out, _ = self.run_block(self.findings, fx)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(out["blocking"], "1")

    def test_c3_citing_head_without_push_still_blocking(self):
        # the review-flagged exploit: finding ON the head, reply cites
        # head — identical in both compares, nothing was ever pushed
        threads = [thread("T1", base=HEAD_SHA, replies=[
            (PR_AUTHOR, "OWNER", f"Fixed in {HEAD_SHA}"),
        ])]
        fx = self.base_fixtures(
            threads,
            commits=[HEAD_SHA],
            compares={f"{HEAD_SHA}...{HEAD_SHA}": {"status": "identical"}})
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

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
        fx = self.base_fixtures(threads, compares=self.ok_compares())
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
                    threads, compares=self.ok_compares(), status=state)
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
                f"{FBASE_SHA}...0badf00": {"status": "ahead"},
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
            "FALLBACK_THREADS": f'{{"5": ["T1|{FIX_SHA}"]}}',
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

    # --- v1.5: cross-repo cites ([owner/]repo@sha in the gate repo) ----

    GATE_SHA = "eb02ca4"  # a commit living in the gate repo

    def xrepo_fixtures(self, threads, cited_date="2026-10-21T00:00:00Z"):
        # commits.json as dict: FBASE old, cited sha postdates it.
        return self.base_fixtures(
            threads,
            commits={FBASE_SHA: "2026-10-19T00:00:00Z",
                     self.GATE_SHA: cited_date})

    def test_x_gate_repo_cite_clears(self):
        # `devin-powerups@<sha>` (bare repo name, same-owner implied)
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             f"Fix belongs in devin-powerups@{self.GATE_SHA} — gate-side"),
        ])]
        proc, out, log = self.run_block(
            self.findings, self.xrepo_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertIn(f"via commit devin-powerups@{self.GATE_SHA}",
                      proc.stdout)

    def test_x_full_owner_cite_clears(self):
        # `Icaro0310/devin-powerups@<sha>` — owner compare must be
        # case-insensitive (tokens are downcased by ascii_downcase).
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             f"fixed upstream: Icaro0310/devin-powerups@{self.GATE_SHA}"),
        ])]
        proc, out, _ = self.run_block(
            self.findings, self.xrepo_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")

    def test_x_other_repo_still_blocking(self):
        # a same-owner cite into a NON-gate repo never clears — nothing
        # ties an arbitrary sibling commit to the finding.
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             f"fixed in devin-state@{self.GATE_SHA}"),
        ])]
        proc, out, log = self.run_block(
            self.findings, self.xrepo_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")
        self.assertNotIn("devin-powerups/commits", log)

    def test_x_wrong_owner_still_blocking(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             f"fixed in upstream/devin-powerups@{self.GATE_SHA}"),
        ])]
        proc, out, _ = self.run_block(
            self.findings, self.xrepo_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_x_stale_commit_still_blocking(self):
        # cited commit OLDER than the finding's base proves no fix
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             f"fixed in devin-powerups@{self.GATE_SHA}"),
        ])]
        proc, out, _ = self.run_block(
            self.findings,
            self.xrepo_fixtures(threads, cited_date="2026-10-18T00:00:00Z"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_x_unqualified_author_still_blocking(self):
        threads = [thread("T1", replies=[
            ("mallory", "NONE",
             f"fixed in devin-powerups@{self.GATE_SHA}"),
        ])]
        proc, out, _ = self.run_block(
            self.findings, self.xrepo_fixtures(threads))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    # --- v1.5: manual-blocking0 delivery path -------------------------

    def test_approve_denied_posts_manual_audit(self):
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        proc, _, log = self.run_block(
            self.approve, fx,
            extra_env=self.approve_env(GH_STUB_PR_REVIEW_FAIL="deny"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pr review --approve", log)
        self.assertIn("manual-blocking0", log)
        self.assertIn("pr comment", log)  # audit trail was posted

    def test_approve_denied_other_error_fails(self):
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        proc, _, log = self.run_block(
            self.approve, fx,
            extra_env=self.approve_env(GH_STUB_PR_REVIEW_FAIL="other"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("manual-blocking0", proc.stdout)

    def test_approve_denied_comment_failure_fails(self):
        # the audit comment IS the mechanism — if it cannot post, the
        # gate fails red rather than going green silently.
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        proc, _, _ = self.run_block(
            self.approve, fx,
            extra_env=self.approve_env(GH_STUB_PR_REVIEW_FAIL="deny",
                                       GH_STUB_PR_COMMENT_FAIL="1"))
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()

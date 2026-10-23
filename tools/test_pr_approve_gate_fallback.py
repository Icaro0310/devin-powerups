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

And the v1.5 additions (D-2026-10-20b — canary failures from
assure#89): cross-repo fix anchors (`owner/repo@sha`, /commit/ and
/pull/ URLs, org-scoped to the PR repo's owner, verified by existence
or mergedness instead of ancestry/postdate) and the idempotent
`gate-resolved-via: fallback` audit comment (deduped on the resolved
thread|anchor set recorded in a `gate-fallback-pairs:` line).
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
# v1.5 cross-repo fixtures: same owner, different repo. Anchors are
# lowercased by the extractor, so expectations use the canonical form.
XREPO = "icaro0310/devin-powerups"
XSHA = "ca55e77"
MERGE_SHA = "bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222"

GH_STUB = r"""#!/usr/bin/env bash
# `gh` test stub: logs every call to GH_STUB_LOG, serves GH_FIXTURE_DIR.
set -u
echo "gh $*" >> "${GH_STUB_LOG:?missing GH_STUB_LOG}"
if [ "${1:-}" = "pr" ]; then
  # Knobs for the manual-blocking0 path: fail the APPROVE review with
  # the real GitHub restriction ("deny") or an unrelated error ("other").
  if [ "${2:-}" = "review" ] && [ "${GH_STUB_PR_REVIEW_FAIL:-}" = "deny" ]; then
    echo "gh: GraphQL: GitHub Actions is not permitted to approve pull requests. (addPullRequestReview)" >&2
    exit 1
  fi
  if [ "${2:-}" = "review" ] && [ "${GH_STUB_PR_REVIEW_FAIL:-}" = "other" ]; then
    echo "gh: upstream timed out (HTTP 502)" >&2
    exit 1
  fi
  exit 0
fi
[ "${1:-}" = "api" ] || { echo "unstubbed: $*" >&2; exit 1; }
shift
endpoint="" ; jqexpr="" ; pr="" ; method="GET"
args=("$@") ; i=0
while [ $i -lt ${#args[@]} ]; do
  a="${args[$i]}"
  case "$a" in
    --jq|-q) i=$((i+1)); jqexpr="${args[$i]:-}" ;;
    -X|--method) i=$((i+1)); method="${args[$i]:-GET}" ;;
    -F|-f|--field|--raw-field|-H|--header|--input|--cache|--hostname)
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
  repos/*/issues/*/comments)
    if [ "${method^^}" = "POST" ]; then
      if [ -n "${GH_STUB_COMMENT_POST_FAIL:-}" ]; then
        echo "gh: Not Found (HTTP 404)" >&2; exit 1
      fi
      out="{\"id\": 1}"
    else
      num="${endpoint##*/issues/}" ; num="${num%%/*}"
      f="$GH_FIXTURE_DIR/issue_comments_pr${num}.json"
      [ -f "$f" ] && out=$(cat "$f") || out="[]"
    fi ;;
  repos/*/pulls/*/reviews*)
    num="${endpoint##*/pulls/}" ; num="${num%%/reviews*}"
    f="$GH_FIXTURE_DIR/pulls_reviews_pr${num}.json"
    [ -f "$f" ] && out=$(cat "$f") || out="[]" ;;
  repos/*/pulls/*)
    # keyed "owner/repo#number" — keeps same-repo and cross-repo pulls apart
    key="${endpoint#repos/}"
    key="${key%%/pulls/*}#${endpoint##*/pulls/}"
    if jq -e --arg k "$key" 'has($k)' "$GH_FIXTURE_DIR/pulls.json" >/dev/null 2>&1; then
      out=$(jq -c --arg k "$key" '.[$k]' "$GH_FIXTURE_DIR/pulls.json")
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
  repos/*)
    # bare repo lookup — default_branch for cross-repo landedness.
    # LAST: `repos/*` also globs the deeper paths above, so it must be
    # tried only after every specific pattern failed.
    key="${endpoint#repos/}"
    if jq -e --arg k "$key" 'has($k)' "$GH_FIXTURE_DIR/repos.json" >/dev/null 2>&1; then
      out=$(jq -c --arg k "$key" '.[$k]' "$GH_FIXTURE_DIR/repos.json")
    else
      echo "gh: Not Found (HTTP 404)" >&2; exit 1
    fi ;;
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


def status_fixture(state="success",
                   description="Completed analysis in 26s"):
    return {"statuses": [{
        "context": "Devin Review",
        "state": state,
        "description": description,
        "avatar_url": "https://avatars.githubusercontent.com/in/811515?v=4",
    }]}


def coverage_fixture(description="devin=SKIPPED_CREDITS a=ok b=ok"):
    return {"statuses": [{
        "context": "Devin Review",
        "state": "success",
        "description": "Full review skipped: trial expired and no "
                       "credits remaining",
        "avatar_url": "https://avatars.githubusercontent.com/in/811515?v=4",
    }, {
        "context": "Review Coverage",
        "state": "success",
        "description": description,
        "avatar_url": "https://avatars.githubusercontent.com/in/148668982?v=4",
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
                         {"5": [f"T1|commit:{FIX_SHA}"]})
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

    # --- v1.8: status re-verification hardened + fallback reviews --------

    def test_v18_skipped_credits_status_does_not_clear_anchor(self):
        # state=success with a skip description is NOT re-review proof:
        # the fix anchor stays unverifiable and the thread keeps blocking.
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}"),
        ])]
        fx = self.base_fixtures(
            threads, compares=self.ok_compares(),
            status="success")
        fx["status.json"] = status_fixture(
            "success", "Full review skipped: trial expired and no "
                       "credits remaining")
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")
        self.assertNotIn("fallback-resolved", proc.stdout)

    def test_v18_coverage_success_clears_anchor_when_devin_skipped(self):
        # Devin skipped but a clean "Review Coverage" status exists on the
        # head — the fallback reviewers re-ran, anchors may verify.
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}"),
        ])]
        fx = self.base_fixtures(threads, compares=self.ok_compares())
        fx["status.json"] = coverage_fixture()
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertIn("fallback-resolved", proc.stdout)

    def test_v18_degraded_coverage_does_not_clear_anchor(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"Fixed in {FIX_SHA}"),
        ])]
        fx = self.base_fixtures(threads, compares=self.ok_compares())
        fx["status.json"] = coverage_fixture(
            "devin=SKIPPED_CREDITS a=ok b=failed DEGRADED")
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_v18_fallback_blocking_review_counts(self):
        # Zero devin threads, but reviewer B left CHANGES_REQUESTED on the
        # head — blocking=1. A stale-sha or non-blocking review does not.
        threads = []
        fx = self.base_fixtures(threads)
        fx["pulls_reviews_pr5.json"] = [
            {"user": {"login": "github-actions[bot]"},
             "state": "CHANGES_REQUESTED", "commit_id": HEAD_SHA},
            {"user": {"login": "github-actions[bot]"},
             "state": "CHANGES_REQUESTED", "commit_id": "old-sha-stale"},
            {"user": {"login": "github-actions[bot]"},
             "state": "COMMENTED", "commit_id": HEAD_SHA},
            {"user": {"login": "human-reviewer"},
             "state": "CHANGES_REQUESTED", "commit_id": HEAD_SHA},
        ]
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_v18_no_fallback_reviews_stays_zero(self):
        fx = self.base_fixtures([])
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")

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

    # --- v1.5: cross-repo fix anchors (canary assure#89) ----------------

    def xrepo_fx(self, threads, branch_status="ahead", **kw):
        """Cross-repo landedness fixtures: the upstream repo's default
        branch is `main`; the cited sha is an ancestor of it (or not,
        when branch_status is diverged/behind)."""
        fx = self.base_fixtures(threads, **kw)
        fx["repos.json"] = {XREPO: {"default_branch": "main"}}
        if branch_status is not None:
            fx["compares.json"] = {
                f"{XSHA}...main": {"status": branch_status}}
        return fx

    def test_xrepo_at_anchor_resolves(self):
        # `owner/repo@sha` — the fix lives upstream, landedness on the
        # default branch verifies (existence alone is not enough).
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             f"fixed upstream in Icaro0310/devin-powerups@{XSHA}"),
        ])]
        fx = self.xrepo_fx(threads, commits=[])
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 1})
        self.assertEqual(json.loads(out["fallback_threads"]),
                         {"5": [f"T1|commit:{XREPO}@{XSHA}"]})
        self.assertIn(f"via commit {XREPO}@{XSHA}", proc.stdout)
        self.assertIn(f"repos/{XREPO}/compare/{XSHA}...main", log)
        self.assertIn(f"commits/{HEAD_SHA}/status", log)

    def test_xrepo_commit_url_resolves(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             "landed: https://github.com/Icaro0310/devin-powerups"
             f"/commit/{XSHA}"),
        ])]
        fx = self.xrepo_fx(threads, commits=[])
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_threads"]),
                         {"5": [f"T1|commit:{XREPO}@{XSHA}"]})

    def test_xrepo_commit_not_on_default_branch_still_blocking(self):
        # the sha EXISTS upstream but sits on an unmerged branch —
        # existence is not landedness (review SEC finding).
        for status in ("diverged", "behind"):
            with self.subTest(branch_status=status):
                threads = [thread("T1", replies=[
                    (PR_AUTHOR, "OWNER",
                     f"fixed upstream in Icaro0310/devin-powerups@{XSHA}"),
                ])]
                fx = self.xrepo_fx(threads, branch_status=status,
                                   commits=[XSHA])
                proc, out, _ = self.run_block(self.findings, fx)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(out["blocking"], "1")

    def test_xrepo_pull_merged_resolves(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "COLLABORATOR",
             "upstream fix merged: https://github.com/Icaro0310/"
             "devin-powerups/pull/215"),
        ])]
        fx = self.base_fixtures(threads, commits=[])
        fx["pulls.json"] = {f"{XREPO}#215": {
            "merged_at": "2026-10-21T00:00:00Z"}}
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_threads"]),
                         {"5": [f"T1|pull:{XREPO}#215"]})
        self.assertIn(f"via pull {XREPO}#215", proc.stdout)
        self.assertIn(f"repos/{XREPO}/pulls/215", log)

    def test_xrepo_pull_unmerged_still_blocking(self):
        # an OPEN upstream PR is not a landed fix
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             "fix in flight: https://github.com/Icaro0310/"
             "devin-powerups/pull/215"),
        ])]
        fx = self.base_fixtures(threads, commits=[])
        fx["pulls.json"] = {f"{XREPO}#215": {"merged_at": None}}
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")
        self.assertEqual(json.loads(out["fallback_resolutions"]), {"5": 0})

    def test_xrepo_other_owner_still_blocking(self):
        # org-scope rail: any owner other than the PR repo's is rejected
        # before the anchor is even queried.
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             f"see other-org/devin-powerups@{XSHA}"),
        ])]
        fx = self.base_fixtures(threads, commits=[XSHA])
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")
        self.assertNotIn("repos/other-org", log)

    def test_xrepo_missing_commit_still_blocking(self):
        # anchor parses but the commit never landed upstream — the
        # default-branch compare 404s.
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"Icaro0310/devin-powerups@{XSHA}"),
        ])]
        fx = self.xrepo_fx(threads, branch_status=None, commits=[])
        fx["compares.json"] = {}
        proc, out, log = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")
        self.assertIn(f"repos/{XREPO}/compare/{XSHA}...main", log)

    def test_own_repo_at_anchor_resolves_like_bare_sha(self):
        # `owner/<own-repo>@sha` is the same-repo alias — full
        # ancestor+postdate proof still applies.
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER", f"fixed in Icaro0310/devin-test@{FIX_SHA}"),
        ])]
        fx = self.base_fixtures(threads, compares=self.ok_compares())
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_threads"]),
                         {"5": [f"T1|commit:icaro0310/devin-test@{FIX_SHA}"]})

    def test_own_repo_at_anchor_keeps_postdate_rail(self):
        # own-repo@<head> must NOT clear on existence alone — that would
        # reopen the cite-head exploit the postdate check closed.
        threads = [thread("T1", base=HEAD_SHA, replies=[
            (PR_AUTHOR, "OWNER", f"fixed in Icaro0310/devin-test@{HEAD_SHA}"),
        ])]
        fx = self.base_fixtures(
            threads, commits=[HEAD_SHA],
            compares={f"{HEAD_SHA}...{HEAD_SHA}": {"status": "identical"}})
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_own_repo_pull_needs_merge_in_head(self):
        # merged upstream but the merge commit never entered this head
        # -> the flagged code is still here, still blocking.
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             "fixed by https://github.com/Icaro0310/devin-test/pull/9"),
        ])]
        fx = self.base_fixtures(
            threads, commits=[],
            compares={f"{MERGE_SHA}...{HEAD_SHA}": {"status": "behind"}})
        fx["pulls.json"] = {"icaro0310/devin-test#9": {
            "merged_at": "2026-10-21T00:00:00Z",
            "merge_commit_sha": MERGE_SHA}}
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "1")

    def test_own_repo_pull_merged_into_head_resolves(self):
        threads = [thread("T1", replies=[
            (PR_AUTHOR, "OWNER",
             "fixed by https://github.com/Icaro0310/devin-test/pull/9"),
        ])]
        fx = self.base_fixtures(
            threads, commits=[],
            compares={f"{MERGE_SHA}...{HEAD_SHA}": {"status": "ahead"},
                      f"{FBASE_SHA}...{MERGE_SHA}": {"status": "ahead"}})
        fx["pulls.json"] = {"icaro0310/devin-test#9": {
            "merged_at": "2026-10-21T00:00:00Z",
            "merge_commit_sha": MERGE_SHA}}
        proc, out, _ = self.run_block(self.findings, fx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out["blocking"], "0")
        self.assertEqual(json.loads(out["fallback_threads"]),
                         {"5": ["T1|pull:icaro0310/devin-test#9"]})

    def test_own_repo_pull_predating_finding_still_blocking(self):
        # the merge IS in the head but PREDATES the finding — it cannot
        # be the fix for a finding filed later (review SEC finding).
        for status in ("identical", "behind"):
            with self.subTest(finding_cmp=status):
                threads = [thread("T1", replies=[
                    (PR_AUTHOR, "OWNER",
                     "fixed by https://github.com/Icaro0310/"
                     "devin-test/pull/9"),
                ])]
                fx = self.base_fixtures(
                    threads, commits=[],
                    compares={
                        f"{MERGE_SHA}...{HEAD_SHA}": {"status": "ahead"},
                        f"{FBASE_SHA}...{MERGE_SHA}": {"status": status},
                    })
                fx["pulls.json"] = {"icaro0310/devin-test#9": {
                    "merged_at": "2026-10-21T00:00:00Z",
                    "merge_commit_sha": MERGE_SHA}}
                proc, out, _ = self.run_block(self.findings, fx)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(out["blocking"], "1")

    # --- approve step: the public fallback comment ---------------------

    def approve_env(self, **over):
        env = {
            "VERDICT_MAP": '{"5": "STATUS_CLEAN"}',
            "BLOCKING_MAP": '{"5": 0}',
            "FALLBACK_MAP": '{"5": 1}',
            "FALLBACK_THREADS": f'{{"5": ["T1|commit:{FIX_SHA}"]}}',
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
        # posted via issues/comments POST carrying the dedupe key
        self.assertIn("-X POST", log)
        self.assertIn("issues/5/comments", log)
        self.assertIn(
            f"gate-fallback-pairs: T1|commit:{FIX_SHA} head:{HEAD_SHA}",
            log)

    def test_approve_without_fallback_posts_no_comment(self):
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        env = self.approve_env(FALLBACK_MAP='{"5": 0}',
                               FALLBACK_THREADS='{"5": []}')
        proc, _, log = self.run_block(self.approve, fx, extra_env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pr review --approve", log)
        self.assertNotIn("-X POST", log)
        self.assertNotIn("issues/5/comments", log)

    def test_approve_held_pr_posts_nothing(self):
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        env = self.approve_env(BLOCKING_MAP='{"5": 2}', FALLBACK_MAP='{"5": 0}',
                               FALLBACK_THREADS='{"5": []}')
        proc, _, log = self.run_block(self.approve, fx, extra_env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("pr review --approve", log)
        self.assertNotIn("-X POST", log)
        self.assertNotIn("issues/5/comments", log)

    # --- v1.5: audit comment idempotency (canary finding, assure#89) ---

    def prior_pairs_comment(self, pairs, author="github-actions[bot]"):
        return {
            "user": {"login": author},
            "body": ("gate-resolved-via: fallback — cleared by replies\n"
                     "\nThreads left unresolved — the findings stay "
                     "visible.\n"
                     f"gate-fallback-pairs: {pairs}"),
        }

    def prior_pairs(self, extra=()):
        """Canonical dedupe key for the current head: sorted resolved
        pairs + the `head:<sha>` token the step now records."""
        return " ".join(sorted({"T1|commit:" + FIX_SHA,
                                f"head:{HEAD_SHA}", *extra}))

    def test_approve_skips_duplicate_fallback_comment(self):
        # second run resolves the identical set on the same head: one
        # GET listing, no POST
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture(),
              "issue_comments_pr5.json": [
                  self.prior_pairs_comment(self.prior_pairs())]}
        proc, _, log = self.run_block(
            self.approve, fx, extra_env=self.approve_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pr review --approve", log)
        self.assertEqual(log.count("issues/5/comments"), 1)
        self.assertNotIn("-X POST", log)
        self.assertIn("skipping duplicate", proc.stdout)

    def test_approve_posts_fresh_comment_on_new_resolved_set(self):
        # a NEW thread got fallback-resolved — different set posts again
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture(),
              "issue_comments_pr5.json": [
                  self.prior_pairs_comment(self.prior_pairs())]}
        env = self.approve_env(
            FALLBACK_MAP='{"5": 2}',
            FALLBACK_THREADS=(
                f'{{"5": ["T1|commit:{FIX_SHA}", "T2|commit:0badf00"]}}'))
        proc, _, log = self.run_block(self.approve, fx, extra_env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("-X POST", log)
        self.assertEqual(log.count("issues/5/comments"), 2)
        self.assertIn("T2|commit:0badf00", log)
        # the fresh comment records the full current set + head
        self.assertIn(
            f"gate-fallback-pairs: {self.prior_pairs(('T2|commit:0badf00',))}",
            log)

    def test_approve_posts_fresh_comment_on_new_head(self):
        # identical resolved set but a different head — the head is part
        # of the dedupe key, so a new head is fresh evidence and posts
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture(),
              "issue_comments_pr5.json": [
                  self.prior_pairs_comment(self.prior_pairs())]}
        env = self.approve_env()
        env["HEAD_SHA"] = "9" * 40
        proc, _, log = self.run_block(self.approve, fx, extra_env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("-X POST", log)
        self.assertIn(f"head:{'9' * 40}", log)

    def test_approve_pairs_line_by_others_does_not_suppress(self):
        # only github-actions[bot] comments dedupe — a human pasting the
        # marker, or an unrelated bot forging it, cannot silence the
        # audit trail (review SEC finding)
        for author in ("Icaro0310", "dependabot[bot]"):
            with self.subTest(author=author):
                fx = {"compares.json": {}, "commits.json": [],
                      "status.json": status_fixture(),
                      "issue_comments_pr5.json": [
                          self.prior_pairs_comment(
                              self.prior_pairs(), author=author)]}
                proc, _, log = self.run_block(
                    self.approve, fx, extra_env=self.approve_env())
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("-X POST", log)

    # --- v1.6: manual-blocking0 — clean evaluation, undeliverable
    # APPROVE review. The check still reflects the evaluation, with a
    # public audit trail (observed personal-agent-system#37). --------

    def manual_env(self, **over):
        env = {"GH_STUB_PR_REVIEW_FAIL": "deny",
               "FALLBACK_MAP": '{"5": 0}', "FALLBACK_THREADS": '{"5": []}'}
        env.update(over)
        return self.approve_env(**env)

    def test_manual_blocking0_posts_audit_comment(self):
        # exact GitHub restriction -> warning + manual-blocking0 audit
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        proc, _, log = self.run_block(
            self.approve, fx, extra_env=self.manual_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pr review --approve", log)
        self.assertIn("gate-resolved-via: manual-blocking0", log)
        self.assertIn("-X POST", log)
        self.assertIn("issues/5/comments", log)
        self.assertIn(f"head:{HEAD_SHA}", log)

    def test_manual_blocking0_other_error_still_fails(self):
        # a different approve failure is NOT the documented path
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        proc, _, _ = self.run_block(
            self.approve, fx,
            extra_env=self.manual_env(GH_STUB_PR_REVIEW_FAIL="other"))
        self.assertNotEqual(proc.returncode, 0)

    def test_manual_blocking0_comment_failure_is_fatal(self):
        # the audit trail IS the mechanism — undeliverable comment =
        # red job, never a silent green
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture()}
        proc, _, _ = self.run_block(
            self.approve, fx,
            extra_env=self.manual_env(GH_STUB_COMMENT_POST_FAIL="1"))
        self.assertNotEqual(proc.returncode, 0)

    def test_manual_blocking0_idempotent_same_head(self):
        # a prior manual-blocking0 audit for the same head suppresses
        # the duplicate comment — GET listing only, no POST
        fx = {"compares.json": {}, "commits.json": [],
              "status.json": status_fixture(),
              "issue_comments_pr5.json": [{
                  "user": {"login": "github-actions[bot]"},
                  "body": ("gate-resolved-via: manual-blocking0 — earlier\n"
                           f"gate-fallback-pairs: manual-blocking0 head:{HEAD_SHA}")}]}
        proc, _, log = self.run_block(
            self.approve, fx, extra_env=self.manual_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("-X POST", log)
        self.assertIn("skipping duplicate", proc.stdout)


if __name__ == "__main__":
    unittest.main()

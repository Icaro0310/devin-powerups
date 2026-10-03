#!/usr/bin/env python3
"""weekly_repo_report.py — weekly activity report for the public devin-* projects.

Reads registry.json, keeps only entries with kind=project + visibility=public,
queries the public GitHub commits REST endpoint for the previous 7 days per
repo (bounded pagination), and writes a standalone HTML report grouped by
repository and day (date, short SHA linked to GitHub, escaped first-line
commit subject).

Only registry entries tagged ``kind=project`` and ``visibility=public`` are
queried or included in the report.

Usage:
    python tools/weekly_repo_report.py [--registry registry.json]
                                       [--out weekly-repo-report.html]
                                       [--days 7] [--max-commits 25]
                                       [--timeout 15]

    python tools/weekly_repo_report.py --send weekly-repo-report.html
                                       --to someone@example.com
                                       --from "Name <verified-sender>"

--send uses the MailerSend SMTP env vars (MAILERSEND_SMTP_HOST,
MAILERSEND_SMTP_PORT, MAILERSEND_SMTP_USER, MAILERSEND_SMTP_PASSWORD) over
verified TLS (ssl.create_default_context). The sender identity must be supplied
with ``--from`` or ``REPORT_SENDER``; it is not the SMTP login.
"""

from __future__ import annotations

import argparse
import html
import http.client
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
GITHUB_API = "https://api.github.com"
GITHUB_HOST = "github.com"
USER_AGENT = "devin-powerups-weekly-report"

DEFAULT_DAYS = 7
DEFAULT_MAX_COMMITS = 25
DEFAULT_TIMEOUT = 15
DEFAULT_SENDER = os.environ.get("REPORT_SENDER", "")
PER_PAGE = 100
MAX_PAGES = 3
SMTP_TIMEOUT = 30

SECRET_ENV_VARS = (
    "MAILERSEND_SMTP_HOST",
    "MAILERSEND_SMTP_PORT",
    "MAILERSEND_SMTP_USER",
    "MAILERSEND_SMTP_PASSWORD",
)

_OWNER_RE = re.compile(r"[A-Za-z0-9-]+")
_REPO_RE = re.compile(r"[A-Za-z0-9_.-]+")
_SHA_RE = re.compile(r"[0-9a-fA-F]{7,40}")


def parse_github_repo_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) for an https://github.com/<owner>/<repo> URL.

    Rejects non-GitHub hosts, non-https schemes, and malformed paths so no
    registry entry can inject links or API paths outside github.com.
    """
    if not isinstance(url, str):
        raise ValueError(f"repo url is not a string: {url!r}")
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as exc:
        raise ValueError(f"invalid repo url {url!r}: {exc}") from exc
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != GITHUB_HOST:
        raise ValueError(f"repo url must be https://{GITHUB_HOST}/<owner>/<repo>: {url!r}")
    parts = parsed.path.strip("/").split("/")
    if (
        len(parts) != 2
        or not _OWNER_RE.fullmatch(parts[0])
        or not _REPO_RE.fullmatch(parts[1])
    ):
        raise ValueError(f"repo url must be https://{GITHUB_HOST}/<owner>/<repo>: {url!r}")
    return parts[0], parts[1]


def safe_github_link(url: str, repo_url: str) -> str | None:
    """Return url only if it stays under https://github.com/<owner>/<repo>/.

    Escaping attributes is not enough — a hostile API payload could point
    hrefs anywhere. Anything outside the repo's own github.com path is
    dropped (rendered without a link).
    """
    if not isinstance(url, str) or not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
        prefix_path = urllib.parse.urlparse(repo_url).path.rstrip("/")
    except ValueError:
        return None
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != GITHUB_HOST:
        return None
    if parsed.path != prefix_path and not parsed.path.startswith(prefix_path + "/"):
        return None
    return url


def load_public_projects(registry_path: Path) -> list[dict]:
    """Return registry entries that are public project repositories.

    Required fields are validated: name must be a non-empty string and url
    must be an https://github.com/<owner>/<repo> URL.
    """
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("registry.json: 'repositories' must be a list")
    selected = []
    for entry in repositories:
        if not isinstance(entry, dict):
            raise ValueError("registry.json: repository entries must be objects")
        if entry.get("kind") != "project" or entry.get("visibility") != "public":
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("registry.json: public project missing 'name'")
        parse_github_repo_url(entry.get("url"))  # raises on invalid/non-GitHub url
        selected.append(entry)
    if not selected:
        raise ValueError("registry.json: no public project repositories found")
    return selected


def _commit_ts(item: dict) -> datetime | None:
    """UTC commit timestamp, or None if unparseable."""
    commit = item.get("commit") or {}
    for author_key in ("committer", "author"):
        raw = ((commit.get(author_key) or {}).get("date")) or ""
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _commit_subject(item: dict) -> str:
    message = ((item.get("commit") or {}).get("message")) or ""
    first_line = message.splitlines()[0].strip() if message.splitlines() else ""
    return first_line or "(no subject)"


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    """Sanitized HTTPError description: status + API message, never headers."""
    detail = ""
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
        if isinstance(body, dict) and body.get("message"):
            detail = str(body["message"])[:200]
    except Exception:
        pass
    rate_note = " (rate limit or forbidden)" if exc.code in (403, 429) else ""
    return f"HTTP {exc.code}{rate_note}" + (f": {detail}" if detail else "")


def fetch_commits(
    repo: dict,
    since: datetime,
    until: datetime,
    timeout: int = DEFAULT_TIMEOUT,
    opener=urllib.request.urlopen,
) -> dict:
    """Fetch commits for one repo between since/until (UTC).

    Paginates with per_page=100 up to MAX_PAGES; if the bound is reached the
    result is flagged lower_bound so the report shows the count as "at
    least N" rather than an exact total. Returns
    {"name", "url", "commits", "error", "fetched", "lower_bound"}; commits
    are filtered client-side on full timestamps and sorted newest first.
    """
    result = {
        "name": repo["name"],
        "url": repo["url"],
        "commits": [],
        "error": None,
        "fetched": 0,
        "lower_bound": False,
    }
    try:
        api_path = "/".join(parse_github_repo_url(repo["url"]))
    except ValueError as exc:
        result["error"] = str(exc)
        return result

    items: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        params = urllib.parse.urlencode(
            {
                "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "until": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "per_page": PER_PAGE,
                "page": page,
            }
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{GITHUB_API}/repos/{api_path}/commits?{params}",
            headers=headers,
        )
        try:
            with opener(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            result["error"] = _http_error_message(exc)
            return result
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
            return result
        if not isinstance(payload, list):
            message = (
                str(payload.get("message", "unexpected API response"))[:200]
                if isinstance(payload, dict)
                else "unexpected API response"
            )
            result["error"] = message
            return result
        items.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < PER_PAGE:
            break
    else:
        # All MAX_PAGES pages came back full — the count is a lower bound.
        result["lower_bound"] = True

    commits = []
    for item in items:
        ts = _commit_ts(item)
        if ts is None or ts < since or ts > until:
            continue
        sha_full = str(item.get("sha") or "")
        link = safe_github_link(str(item.get("html_url") or ""), repo["url"])
        if link is None and _SHA_RE.fullmatch(sha_full):
            link = f"{repo['url']}/commit/{sha_full}"
        commits.append(
            {
                "sha": sha_full[:7] or "?",
                "url": link,
                "day": ts.date().isoformat(),
                "ts": ts,
                "subject": _commit_subject(item),
            }
        )
    commits.sort(key=lambda c: c["ts"], reverse=True)
    result["fetched"] = len(commits)
    result["commits"] = commits
    return result


def collect_report(
    registry_path: Path,
    days: int = DEFAULT_DAYS,
    max_commits: int = DEFAULT_MAX_COMMITS,
    timeout: int = DEFAULT_TIMEOUT,
    now: datetime | None = None,
    opener=urllib.request.urlopen,
) -> dict:
    """Fetch all public-project commits and return the report data."""
    if days <= 0 or max_commits <= 0 or timeout <= 0:
        raise ValueError("days, max_commits and timeout must be positive integers")
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    results = []
    for repo in load_public_projects(registry_path):
        result = fetch_commits(repo, since, now, timeout=timeout, opener=opener)
        if len(result["commits"]) > max_commits:
            result["truncated"] = len(result["commits"]) - max_commits
            result["commits"] = result["commits"][:max_commits]
        else:
            result["truncated"] = 0
        results.append(result)
    return {"generated": now, "since": since, "days": days, "repos": results}


def render_html(report: dict) -> str:
    """Render the collected report data as a standalone HTML page."""
    generated = report["generated"].strftime("%Y-%m-%d %H:%M UTC")
    since_day = report["since"].date().isoformat()
    until_day = report["generated"].date().isoformat()
    total_shown = sum(len(r["commits"]) for r in report["repos"])
    total_fetched = sum(r.get("fetched", len(r["commits"])) for r in report["repos"])
    lower_bound = any(r.get("lower_bound") for r in report["repos"])
    errors = sum(1 for r in report["repos"] if r["error"])

    sections = []
    for repo in report["repos"]:
        name = html.escape(repo["name"])
        # repo urls are validated to https://github.com/<owner>/<repo> at load.
        url = html.escape(repo["url"], quote=True)
        header = f'<h2><a href="{url}">{name}</a></h2>'
        if repo["error"]:
            sections.append(
                f"{header}\n"
                f'<table><tr class="error"><td colspan="3">Fetch error: '
                f"{html.escape(repo['error'])}</td></tr></table>"
            )
            continue
        if not repo["commits"]:
            sections.append(f'{header}\n<p class="empty">No commits in this window.</p>')
            continue
        rows = []
        for commit in repo["commits"]:
            sha = html.escape(commit["sha"])
            if commit["url"]:
                link = f'<a href="{html.escape(commit["url"], quote=True)}"><code>{sha}</code></a>'
            else:
                link = f"<code>{sha}</code>"
            rows.append(
                "<tr>"
                f"<td>{html.escape(commit['day'])}</td>"
                f"<td>{link}</td>"
                f"<td>{html.escape(commit['subject'])}</td>"
                "</tr>"
            )
        if repo.get("truncated"):
            rows.append(
                f'<tr class="muted"><td colspan="3">…and {repo["truncated"]} more '
                "commit(s) not shown (per-repo display cap).</td></tr>"
            )
        if repo.get("lower_bound"):
            rows.append(
                '<tr class="muted"><td colspan="3">Fetch limit reached — the '
                "commit count for this repo is a lower bound.</td></tr>"
            )
        sections.append(
            f"{header}\n<table>\n<thead><tr><th>Day</th><th>Commit</th>"
            f"<th>Subject</th></tr></thead>\n<tbody>\n{''.join(rows)}\n"
            "</tbody>\n</table>"
        )

    approx = "+" if lower_bound else ""
    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>devin-* weekly repo report — {until_day}</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; color: #1c1c1e; }}
h1 {{ font-size: 1.4rem; }}
h2 {{ font-size: 1.05rem; margin: 1.6rem 0 0.4rem; }}
.meta, .empty, .muted {{ color: #666; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: 0.3rem 0.6rem; border-bottom: 1px solid #e2e2e4; vertical-align: top; }}
th {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: #666; }}
tr.error td {{ color: #a40000; }}
code {{ font-family: ui-monospace, Consolas, monospace; }}
</style>
</head>
<body>
<h1>devin-* weekly repository report</h1>
<p class="meta">Generated {generated} — commits from {since_day} to {until_day}
(inclusive, UTC). {total_fetched}{approx} commit(s) fetched across
{len(report['repos'])} public project repo(s), {total_shown} shown;
{errors} fetch error(s). Source: registry.json
only entries tagged kind=project and visibility=public are included.</p>
{body}
</body>
</html>
"""


def send_report_email(
    html_path: Path, recipient: str, sender: str | None = None
) -> int:
    """Send the rendered report via MailerSend SMTP (env-provided creds).

    STARTTLS uses ssl.create_default_context() so the server certificate and
    hostname are verified. The sender identity must be supplied by the caller
    or the ``REPORT_SENDER`` environment variable, not inferred from SMTP login.
    """
    missing = [var for var in SECRET_ENV_VARS if not os.environ.get(var)]
    if missing:
        print(
            f"::warning::Missing env vars {', '.join(missing)} — cannot send email.",
            file=sys.stderr,
        )
        return 2
    sender = (sender or os.environ.get("REPORT_SENDER", "")).strip()
    if not sender:
        print("::warning::Set REPORT_SENDER or pass --from — cannot send email.",
              file=sys.stderr)
        return 2

    body_html = Path(html_path).read_text(encoding="utf-8")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"devin-* weekly repo report — {datetime.now(timezone.utc):%Y-%m-%d}"
    message.set_content("Weekly devin-* repository report attached inline (HTML).")
    message.add_alternative(body_html, subtype="html")

    context = ssl.create_default_context()
    try:
        port = int(os.environ["MAILERSEND_SMTP_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("out of range")
    except ValueError:
        print(
            f"::warning::MAILERSEND_SMTP_PORT is not a valid port: "
            f"{os.environ['MAILERSEND_SMTP_PORT'][:20]!r}",
            file=sys.stderr,
        )
        return 2
    try:
        with smtplib.SMTP(os.environ["MAILERSEND_SMTP_HOST"], port, timeout=SMTP_TIMEOUT) as smtp:
            smtp.starttls(context=context)
            smtp.login(os.environ["MAILERSEND_SMTP_USER"], os.environ["MAILERSEND_SMTP_PASSWORD"])
            smtp.send_message(message)
    except smtplib.SMTPException as exc:
        print(f"::error::SMTP send failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"::error::SMTP connection failed: {exc}", file=sys.stderr)
        return 1
    print(f"email sent to {recipient}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", default=str(HUB / "registry.json"))
    parser.add_argument("--out", default="weekly-repo-report.html")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--max-commits", type=int, default=DEFAULT_MAX_COMMITS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--send", metavar="HTML", help="send an existing report file via MailerSend SMTP")
    parser.add_argument("--to", metavar="ADDR", help="email recipient (required with --send)")
    parser.add_argument("--from", dest="sender", default=os.environ.get("REPORT_SENDER", ""),
                        help="verified email From identity (or set REPORT_SENDER)")
    args = parser.parse_args(argv)

    if args.days <= 0 or args.max_commits <= 0 or args.timeout <= 0:
        parser.error("--days, --max-commits and --timeout must be positive integers")

    if args.send:
        if not args.to:
            parser.error("--send requires --to")
        if not args.sender.strip():
            parser.error("--from must not be empty")
        return send_report_email(Path(args.send), args.to, args.sender)

    try:
        report = collect_report(
            Path(args.registry),
            days=args.days,
            max_commits=args.max_commits,
            timeout=args.timeout,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"::error::registry problem: {exc}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(report), encoding="utf-8")

    total = sum(len(r["commits"]) for r in report["repos"])
    errors = [r["name"] for r in report["repos"] if r["error"]]
    print(f"wrote {out} — {total} commit(s) shown across {len(report['repos'])} repo(s)")
    for name in errors:
        print(f"::warning::{name}: fetch error (see report)", file=sys.stderr)
    if errors and len(errors) == len(report["repos"]):
        # Artifact exists, but every fetch failed — fail loudly so callers
        # (e.g. the workflow) can mark the run non-green after handling it.
        print("::error::all repository fetches failed; report contains only error rows",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

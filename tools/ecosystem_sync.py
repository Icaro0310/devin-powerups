#!/usr/bin/env python3
"""ecosystem_sync.py — drift report between local versions and published channels.

Reads registry.json (source of truth for products/repos), scans the local
checkouts for package manifests (pyproject.toml / package.json), then probes
every external channel the ecosystem publishes to:

    - PyPI              https://pypi.org/pypi/<dist>/json
    - npm               https://registry.npmjs.org/<name>
    - Open VSX          https://open-vsx.org/api/<publisher>/<ext>
    - VS Code Marketplace  reported as "unavailable" (Entra credential pending)
    - GitHub releases   ``gh api repos/<owner>/<repo>/tags`` (+ releases/latest)
    - Website           https://icaro0310.github.io product-name presence
    - committed .vsix   zip package.json version vs the source package.json

VS Code extensions are discovered by scanning every local repo checkout for
package.json files whose ``publisher`` is ``icaro0310`` — covering both
``packages/*/adapters/vscode/package.json`` and package-level manifests like
``packages/agent-sessions/package.json``. The ``adapters/vscode_ext/``
skeleton (``<pkg>`` placeholders, not a publishable artifact) is excluded.

A health section probes the local daemons (mcp-hub /devin-office healthz,
Ollama on the tailnet, known systemd --user units). Daemon failures print
``DAEMON-DOWN`` lines but never crash the report.

A freshness section watches silent components on top of two sources.
Five bespoke probes keep working (dispatcher queue, Slack notify ledger,
weekly scout, review-fallback runs, heartbeat state); a universal silence
matrix (``tools/silence-matrix.json``) adds every tool that emits to the
shared heartbeat ledger (``$XDG_STATE_HOME/devin/heartbeats.jsonl`` or
``$DEVIN_HEARTBEAT_FILE``), plus a per-workflow GitHub Actions freshness
roll-up. A component that produces nothing within its expected interval —
or whose recent events are failures — is reported as ``drift`` in the
``freshness`` channel so it feeds --state-md and, with --issue, opens
``silence-alert`` issues plus a Slack notify (``--no-silence-alerts``
disables those side effects).

A runtime section (``--runtime``) reads the PAS ``runtime-registry.json``
(declarative inventory of every scheduled/daemon component on laptop,
vm-qwenpaw and github-actions) and checks per component: heartbeat
activity per ``heartbeat.source`` (heartbeats.jsonl / pm2 / cron-log /
gh-run / systemd / none), host drift, and deploy freshness for git-managed
deploys. Findings are ``warn`` rows — ops signal, outside DRIFT_STATES.

Usage:
    python tools/ecosystem_sync.py [--registry registry.json]
                                   [--ecosystem-root ~/devin/devin-ecosystem]
                                   [--timeout 10] [--offline] [--json]
                                   [--issue] [--no-silence-alerts]
                                   [--runtime] [--runtime-registry PATH]

Without --issue the report is printed and the exit code is 1 when any drift
is found (0 otherwise). With --issue, one GitHub Issue labeled ``drift`` is
opened per affected physical repo, deduplicated against open ``drift``
issues first.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import shlex
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None

HUB = Path(__file__).resolve().parent.parent
USER_AGENT = "devin-powerups-ecosystem-sync"

DEFAULT_TIMEOUT = 10
DAEMON_TIMEOUT = 5
PYPI_API = "https://pypi.org/pypi"
NPM_API = "https://registry.npmjs.org"
OPEN_VSX_API = "https://open-vsx.org/api"
WEBSITE_URL = "https://icaro0310.github.io"
VSCODE_PUBLISHER = "icaro0310"

# Local daemon probes. (name, kind, target)
HEALTHZ_URL = "http://127.0.0.1:8764/healthz"
OLLAMA_TAGS_URL = "http://100.102.159.65:11435/api/tags"
SYSTEMD_USER_UNITS = ("slack-poll.service", "mcp-hub.service")

# Drift states that fail the run / feed --issue.
DRIFT_STATES = {"drift", "stale-vsix", "not-published"}
# Informational states that never fail the run.
INFO_STATES = {"absent", "skip", "n/a"}

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_VERSION_LINE_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass
class Row:
    """One line of the drift table."""

    product: str
    channel: str
    local: str
    remote: str
    state: str  # ok | drift | stale-vsix | not-published | unavailable | absent | skip | n/a
    repo: str = ""  # physical GitHub repo (owner/name) that owns the drift
    note: str = ""


@dataclass
class Product:
    """A registry repository entry that maps to a physical repo + manifest."""

    name: str  # registry entry name (product id)
    repo_owner: str
    repo_name: str  # physical repo basename from the entry url
    ecosystem: str = ""  # pypi | npm | ""
    dist_name: str = ""  # published distribution name
    pkg_path: str = "."  # package subdir inside the repo
    registry_version: str = ""
    local_version: str = ""
    manifest: str = ""  # manifest path that produced local_version
    local_repo_dir: Path | None = None
    channels: list = field(default_factory=list)


@dataclass
class VsCodeExt:
    name: str
    version: str
    repo_name: str  # physical repo basename containing the extension
    manifest: Path


def _repo_basename(url: str) -> tuple[str, str]:
    """Return (owner, repo) from an https://github.com/<owner>/<repo> URL."""
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "github.com":
        raise ValueError(f"repo url must be https://github.com/<owner>/<repo>: {url!r}")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"repo url must be https://github.com/<owner>/<repo>: {url!r}")
    return parts[0], parts[1]


def load_products(registry_path: Path) -> list[dict]:
    """Return public registry repository entries (source of truth)."""
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("registry.json: 'repositories' must be a list")
    selected = []
    for entry in repositories:
        if not isinstance(entry, dict):
            raise ValueError("registry.json: repository entries must be objects")
        if entry.get("visibility") != "public":
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("registry.json: public repository missing 'name'")
        _repo_basename(entry.get("url"))  # raises on invalid/non-GitHub url
        selected.append(entry)
    if not selected:
        raise ValueError("registry.json: no public repositories found")
    return selected


def _read_manifest_version(manifest: Path) -> str:
    """Extract version from a pyproject.toml or package.json."""
    try:
        if manifest.name == "pyproject.toml":
            if tomllib is not None:
                data = tomllib.loads(manifest.read_text(encoding="utf-8"))
                version = (data.get("project") or {}).get("version")
                if isinstance(version, str):
                    return version.strip()
            match = _VERSION_LINE_RE.search(manifest.read_text(encoding="utf-8"))
            return match.group(1).strip() if match else ""
        if manifest.name == "package.json":
            data = json.loads(manifest.read_text(encoding="utf-8"))
            version = data.get("version")
            return str(version).strip() if version else ""
    except (OSError, ValueError):
        return ""
    return ""


def _find_repo_dir(repo_name: str, roots: list[Path]) -> Path | None:
    """Locate the local checkout of a repo across candidate roots."""
    for root in roots:
        candidate = root / repo_name
        if candidate.is_dir():
            return candidate
    return None


def resolve_products(entries: list[dict], roots: list[Path]) -> list[Product]:
    """Map registry entries to local checkouts and read manifest versions."""
    products = []
    for entry in entries:
        owner, repo_name = _repo_basename(entry["url"])
        package = entry.get("package") or {}
        product = Product(
            name=entry["name"],
            repo_owner=owner,
            repo_name=repo_name,
            ecosystem=str(package.get("ecosystem") or ""),
            dist_name=str(package.get("name") or ""),
            pkg_path=str(package.get("path") or "."),
            registry_version=str(entry.get("version") or ""),
        )
        repo_dir = _find_repo_dir(repo_name, roots)
        product.local_repo_dir = repo_dir
        if repo_dir is not None and product.dist_name:
            pkg_dir = repo_dir if product.pkg_path in ("", ".") else repo_dir / product.pkg_path
            for manifest_name in ("pyproject.toml", "package.json"):
                manifest = pkg_dir / manifest_name
                if manifest.is_file():
                    product.local_version = _read_manifest_version(manifest)
                    product.manifest = str(manifest)
                    break
        products.append(product)
    return products


def scan_vscode_extensions(roots: list[Path], repo_names: set[str]) -> list[VsCodeExt]:
    """Find package.json files with publisher == VSCODE_PUBLISHER.

    Scans each repo checkout for adapters/vscode/package.json and
    package-level extension manifests. ``adapters/vscode_ext/`` is the repo
    skeleton template (``<pkg>`` placeholders) and is never a publishable
    artifact, so it is excluded along with node_modules.
    """
    extensions: dict[str, VsCodeExt] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for repo_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            if repo_names and repo_dir.name not in repo_names:
                continue
            for manifest in sorted(repo_dir.rglob("package.json")):
                parts = manifest.parts
                if "node_modules" in parts or "vscode_ext" in parts:
                    continue
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if data.get("publisher") != VSCODE_PUBLISHER:
                    continue
                name = str(data.get("name") or "")
                if not name or "<" in name:  # skeleton placeholder
                    continue
                key = f"{repo_dir.name}:{name}"
                extensions[key] = VsCodeExt(
                    name=name,
                    version=str(data.get("version") or ""),
                    repo_name=repo_dir.name,
                    manifest=manifest,
                )
    return sorted(extensions.values(), key=lambda e: (e.repo_name, e.name))


def _http_get_json(url: str, timeout: int, opener=urllib.request.urlopen):
    """GET url and decode JSON. Raises on transport/HTTP errors."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    """Sanitized HTTPError description: status + short body message."""
    detail = ""
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
        if isinstance(body, dict) and body.get("message"):
            detail = str(body["message"])[:160]
        elif isinstance(body, dict) and body.get("error"):
            detail = str(body["error"])[:160]
    except Exception:
        pass
    rate_note = " (rate limit or forbidden)" if exc.code in (403, 429) else ""
    return f"HTTP {exc.code}{rate_note}" + (f": {detail}" if detail else "")


def fetch_channel_version(url: str, timeout: int, opener=urllib.request.urlopen) -> str:
    """Return a published version from a JSON channel endpoint.

    Raises KeyError('not-published') on 404 so callers can distinguish
    "not published yet" from transport failures.
    """
    try:
        payload = _http_get_json(url, timeout, opener=opener)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise KeyError("not-published") from exc
        raise RuntimeError(_http_error_message(exc)) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected API response")
    return payload


def _gh_api(owner: str, repo: str, path: str, timeout: int) -> object:
    proc = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}{path}"],
        capture_output=True,
        text=True,
        timeout=timeout + 5,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "gh api failed").strip()[:200])
    return json.loads(proc.stdout)


def _repo_tags(owner: str, repo: str, timeout: int,
               cache: dict | None = None) -> list[str]:
    """Tag names of a repo, cached per (owner, repo) for monorepo fan-out."""
    key = (owner, repo)
    if cache is not None and key in cache:
        return cache[key]
    try:
        tags = _gh_api(owner, repo, "/tags?per_page=100", timeout)
    except RuntimeError:
        tags = []
    names = [t["name"] for t in tags if isinstance(t, dict)] if isinstance(tags, list) else []
    names = [n for n in names if isinstance(n, str)]
    if cache is not None:
        cache[key] = names
    return names


def pypi_version(dist: str, timeout: int, opener=urllib.request.urlopen) -> str:
    payload = fetch_channel_version(f"{PYPI_API}/{dist}/json", timeout, opener=opener)
    info = payload.get("info") or {}
    version = info.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("PyPI payload missing info.version")
    return version


def npm_version(dist: str, timeout: int, opener=urllib.request.urlopen) -> str:
    quoted = urllib.parse.quote(dist, safe="")
    payload = fetch_channel_version(f"{NPM_API}/{quoted}", timeout, opener=opener)
    version = (payload.get("dist-tags") or {}).get("latest")
    if not isinstance(version, str) or not version:
        raise RuntimeError("npm payload missing dist-tags.latest")
    return version


def open_vsx_version(ext_name: str, timeout: int, opener=urllib.request.urlopen) -> str:
    payload = fetch_channel_version(
        f"{OPEN_VSX_API}/{VSCODE_PUBLISHER}/{ext_name}", timeout, opener=opener
    )
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("Open VSX payload missing version")
    return version


VSCODE_MARKETPLACE_API = (
    "https://marketplace.visualstudio.com/_apis/public/gallery/"
    "extensionquery?api-version=7.2-preview.1"
)


def marketplace_version(ext_name: str, timeout: int) -> str | None:
    """VS Code Marketplace public gallery API — no credential needed.

    Returns "" when the extension is not published there, None on
    transport/API failure."""
    body = json.dumps({
        "filters": [{"criteria": [
            {"filterType": 7, "value": f"{VSCODE_PUBLISHER}.{ext_name}"}]}],
        "flags": 914,
    }).encode()
    req = urllib.request.Request(
        VSCODE_MARKETPLACE_API, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json;api-version=7.2-preview.1"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=timeout))
    except (OSError, ValueError):
        return None
    exts = (data.get("results") or [{}])[0].get("extensions") or []
    if not exts:
        return ""
    versions = exts[0].get("versions") or []
    return versions[0].get("version", "") if versions else ""


def _semver_key(tag: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.match(tag.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def tag_prefixes(product: "Product") -> list[str]:
    """Tag prefixes a monorepo may use for this product.

    Package-specific tags are ``<pkg>-v*`` where ``<pkg>`` is the package
    directory basename (``packages/redact`` -> ``redact-v0.2.6``). For
    root-level packages the dist name and its ``devin-``-stripped short
    form are tried too (``devin-memory`` -> ``memory-v0.1.1``).
    """
    prefixes = []
    if product.pkg_path not in ("", "."):
        prefixes.append(Path(product.pkg_path).name)
    if product.dist_name:
        prefixes.append(product.dist_name)
        if product.dist_name.startswith("devin-"):
            prefixes.append(product.dist_name[len("devin-"):])
    seen, out = set(), []
    for prefix in prefixes:
        if prefix and prefix not in seen:
            seen.add(prefix)
            out.append(prefix)
    return out


def normalize_tag(tag: str, prefixes: list[str]) -> str:
    """Normalize a git tag to a bare version: ``pkg-v1.2.3``/``v1.2.3`` -> 1.2.3."""
    tag = tag.strip()
    for prefix in prefixes:
        for head in (f"{prefix}-v", f"{prefix}-"):
            if tag.startswith(head):
                return tag[len(head):].lstrip("v")
    return tag.lstrip("v")


def github_release_version(owner: str, repo: str, prefixes: list[str],
                           timeout: int, cache: dict | None = None) -> str:
    """Latest published version on GitHub for a distribution.

    Monorepos tag per package (``<pkg>-v*``), so package-prefixed tags win;
    otherwise the highest semver tag is used, with releases/latest as a last
    resort. Raises KeyError('not-published') when nothing is tagged.
    """
    names = _repo_tags(owner, repo, timeout, cache=cache)

    prefixed = [n for n in names
                if any(n.startswith(f"{p}-v") for p in prefixes)]
    candidates = prefixed or [n for n in names if _semver_key(n) is not None]
    best, best_key = None, None
    for name in candidates:
        key = _semver_key(normalize_tag(name, prefixes))
        if key is not None and (best_key is None or key > best_key):
            best, best_key = name, key
    if best is not None:
        return normalize_tag(best, prefixes)

    try:
        latest = _gh_api(owner, repo, "/releases/latest", timeout)
        tag = latest.get("tag_name") if isinstance(latest, dict) else None
        if isinstance(tag, str) and tag:
            return normalize_tag(tag, prefixes)
    except RuntimeError:
        pass
    raise KeyError("not-published")


def fetch_website(timeout: int, opener=urllib.request.urlopen) -> str:
    """Return the product-site HTML (single fetch shared by all rows)."""
    request = urllib.request.Request(WEBSITE_URL, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def vsix_version(vsix_path: Path) -> str:
    """Version inside a committed .vsix (zip extension/package.json)."""
    try:
        with zipfile.ZipFile(vsix_path) as archive:
            data = json.loads(archive.read("extension/package.json").decode("utf-8"))
        return str(data.get("version") or "")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return ""


def _compare(product: str, channel: str, local: str, remote: str, repo: str,
             not_published_state: str = "not-published") -> Row:
    """Build a table row comparing a local version with a remote one."""
    if remote is None:
        return Row(product, channel, local or "—", "—", "unavailable", repo)
    if remote == "":
        return Row(product, channel, local or "—", "—", not_published_state, repo)
    if not local:
        return Row(product, channel, "—", remote, "n/a", repo)
    state = "ok" if local == remote else "drift"
    return Row(product, channel, local, remote, state, repo)


def check_daemon(url: str, timeout: int = DAEMON_TIMEOUT,
                 opener=urllib.request.urlopen) -> str | None:
    """None when healthy, otherwise a short failure description."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=timeout) as response:
            response.read()
        return None
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"


def systemd_unit_state(unit: str, timeout: int = DAEMON_TIMEOUT) -> str:
    """systemctl --user is-active <unit>; 'skip' when the unit is absent.

    Returns 'n/a' when systemctl itself is absent — on Windows the binary
    never exists, so reporting DAEMON-DOWN would be a false negative."""
    if shutil.which("systemctl") is None:
        return "n/a"
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"error: {type(exc).__name__}"
    state = proc.stdout.strip()
    if proc.returncode == 4 or "could not be found" in (proc.stderr + state):
        return "skip"
    return state or "unknown"


def check_ollama_via_vm(timeout: int = 10) -> str | None:
    """Probe Ollama through the VM SSH alias — the honest path.

    The tailnet endpoint (100.102.159.65:11435) is ACL-scoped to tagged
    GH runners, so a laptop probe reports DAEMON-DOWN falsely even when
    the pipeline is healthy. SSH'ing to the VM and hitting the local
    rewriter (:11436 -> ollama:11434) tests the chain the lanes use."""
    if shutil.which("ssh") is None:
        return "n/a (no ssh client on this host)"
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout}",
             "devin-vm",
             "curl -s -m 8 -o /dev/null -w '%{http_code}' "
             "localhost:11436/api/tags"],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"ssh probe error: {type(exc).__name__}"
    if proc.returncode != 0:
        return f"ssh to devin-vm failed rc={proc.returncode}"
    return None if "200" in proc.stdout else f"ollama http={proc.stdout.strip()}"


def check_slack_auth(roots: list[Path], timeout: int) -> str | None:
    """Slack auth.test — proves the notify channel is alive, not just that
    some caller reported success. Token from env or the first
    ``*/gateways/.env`` under the roots; never logged. None = ok."""
    token = os.environ.get("SLACK_BOT_TOKEN") or os.environ.get("SLACK_USER_TOKEN")
    if not token:
        for root in roots:
            for env_file in sorted(root.glob("*/gateways/.env")):
                try:
                    for line in env_file.read_text(encoding="utf-8").splitlines():
                        m = re.match(
                            r"\s*(SLACK_BOT_TOKEN|SLACK_USER_TOKEN)\s*=\s*(.*\S)\s*$", line)
                        if m:
                            token = m.group(2).strip().strip("\"'")
                            if m.group(1) == "SLACK_BOT_TOKEN":
                                break
                except OSError:
                    continue
                if token:
                    break
            if token:
                break
    if not token:
        return "skip (no SLACK_*_TOKEN in env or gateways/.env)"
    try:
        req = urllib.request.Request(
            "https://slack.com/api/auth.test", data=b"",
            headers={"Authorization": f"Bearer {token}"})
        data = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"[:140]
    return None if data.get("ok") else str(data.get("error") or "not ok")[:140]


def collect_health(roots: list[Path] | None = None,
                   timeout: int = DEFAULT_TIMEOUT) -> list[tuple[str, str]]:
    """Daemon probes -> [(name, status)]; failures read DAEMON-DOWN."""
    checks: list[tuple[str, str]] = []
    failure = check_daemon(HEALTHZ_URL)
    checks.append(("mcp-hub/office healthz", "ok" if failure is None else f"DAEMON-DOWN {failure}"))
    failure = check_ollama_via_vm()
    checks.append(("ollama (via devin-vm)", "ok" if failure is None else
                   failure if failure.startswith("n/a") else f"DAEMON-DOWN {failure}"))
    failure = check_slack_auth(roots or [], timeout)
    checks.append(("slack auth.test", "ok" if failure is None else f"DAEMON-DOWN {failure}"))
    for unit in SYSTEMD_USER_UNITS:
        state = systemd_unit_state(unit)
        if state == "skip":
            checks.append((unit, "skip (unit absent)"))
        elif state == "n/a":
            checks.append((unit, "n/a (no systemctl on this platform)"))
        elif state == "active":
            checks.append((unit, "ok"))
        else:
            checks.append((unit, f"DAEMON-DOWN is-active={state}"))
    return checks


def collect_open_prs(repos: dict[str, str], timeout: int) -> list[tuple[str, int, str]]:
    """Open PRs per physical repo -> [(repo, number, title)].

    ``repos`` maps repo name -> owner. Failures are skipped silently: an
    unauthenticated or unreachable ``gh`` must not blank the state file.
    """
    out: list[tuple[str, int, str]] = []
    for name, owner in sorted(repos.items()):
        try:
            proc = subprocess.run(
                ["gh", "pr", "list", "--repo", f"{owner}/{name}",
                 "--state", "open", "--json", "number,title", "--limit", "25"],
                capture_output=True, text=True, timeout=timeout + 5)
            if proc.returncode != 0:
                continue
            for pr in json.loads(proc.stdout):
                out.append((name, int(pr["number"]), str(pr["title"])))
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError,
                KeyError, TypeError):
            continue
    return out


def write_state_md(path: Path, rows: list[Row],
                   health: list[tuple[str, str]],
                   prs: list[tuple[str, int, str]],
                   generated: datetime,
                   silence: list[Row] | None = None) -> None:
    """Markdown snapshot for agent consumption (push-memory source of truth)."""
    lines = [
        "# Ecosystem state",
        "",
        f"<!-- generated {generated.isoformat()} UTC by tools/ecosystem_sync.py — do not edit -->",
        "",
        "## Published versions",
        "",
        "| product | channel | local | remote | state |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r.product} | {r.channel} | {r.local} | {r.remote} | {r.state} |")
    lines += ["", "## Service health", ""]
    for name, status in health:
        lines.append(f"- {name}: {status}")
    if silence is None:
        silence = [r for r in rows if r.channel == "freshness"]
    lines += ["", "## Silence Monitor", ""]
    if silence:
        for r in silence:
            if r.state == "ok":
                status = "ok"
            elif r.state in DRIFT_STATES:
                status = f"DRIFT {r.local}"
            else:
                status = "n/a"
            lines.append(f"- {r.product}: {status}")
    else:
        lines.append("- none")
    drift = [r for r in rows if r.state in DRIFT_STATES]
    lines += ["", "## Drift requiring action", ""]
    if drift:
        for r in drift:
            lines.append(f"- **{r.product}** ({r.channel}): local {r.local} vs remote {r.remote} [{r.state}]")
    else:
        lines.append("- none")
    lines += ["", "## Open PRs", ""]
    if prs:
        for repo, number, title in prs:
            lines.append(f"- {repo}#{number} — {title}")
    else:
        lines.append("- none")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# Non-product repos that still host PRs and must carry the review fallback.
EXTRA_REPOS = {
    "personal-agent-system": "Icaro0310",
    "devin-dashboard": "Icaro0310",
    "Icaro0310.github.io": "Icaro0310",
}


def collect_repo_settings(repos: dict[str, str], timeout: int) -> list[Row]:
    """Repo settings that gate the remediation agent -> one Row per repo.

    ``allow_auto_merge=false`` means a PR the agent opens stays open
    forever — a silent failure no sensor catches. Reported as ``warn``:
    visible in the report/STATE.md table but deliberately NOT in
    DRIFT_STATES, because the fix is a governance decision (enable the
    setting), not a code defect the agent should patch on its own.

    Exception: PRIVATE repos on the free tier cannot use branch
    protection or repo auto-merge at all — their gate merges
    in-workflow (pr-approve@v1.12 / review-fallback `merge:` job).
    A repo whose workflows carry such a caller is `ok` with
    ``in-workflow merge``; ``off`` with no merge path is the real warn."""
    out: list[Row] = []
    for name, owner in sorted(repos.items()):
        try:
            repo = _gh_api(owner, name, "", timeout)
        except RuntimeError as exc:
            out.append(Row(name, "repo-settings", "—", "on",
                           "unavailable", f"{owner}/{name}",
                           str(exc)[:120]))
            continue
        if repo.get("allow_auto_merge") is True:
            out.append(Row(name, "repo-settings", "auto-merge on", "on",
                           "ok", f"{owner}/{name}", ""))
            continue
        merge_path = False
        try:
            wf = _gh_api(owner, name, "/contents/.github/workflows",
                         timeout)
            names = {str(f.get("name", "")) for f in wf
                     if isinstance(f, dict)}
            merge_path = any(
                ("auto-approve" in n) or ("review-fallback" in n) or
                ("auto-merge" in n) or ("merge" in n and n.endswith(".yml"))
                for n in names)
        except RuntimeError:
            pass
        if merge_path:
            out.append(Row(name, "repo-settings", "in-workflow merge",
                           "on", "ok", f"{owner}/{name}",
                           "free-tier private: gate merges in-job"))
        else:
            out.append(Row(name, "repo-settings", "no merge path", "on",
                           "warn", f"{owner}/{name}",
                           "agent-opened PRs hang — enable auto-merge or "
                           "wire the in-workflow merge gate"))
    return out


# ---------------------------------------------------------------------------
# PR merge-flow sensor (pr_ready_not_merged)
#
# An APPROVED PR with green checks that sits unmerged is drift between the
# review gate and the merge click — personal-agent-system#141 stayed
# ready-but-stuck for days because nothing arms auto-merge. pr-approve@v1.13
# now arms `gh pr merge --auto` best-effort; this sensor is the net for
# whatever the arm cannot cover (auto-merge disabled, clean-status PRs,
# callers still on contents:read).
#
# "Approved" follows the two paths the gate documents: a formal APPROVED
# review (reviewDecision APPROVED), or the manual-blocking0 audit comment
# left when the APPROVE review is undeliverable — judge success is still
# required so a later rejected verdict un-counts it. devin-judge/review
# success ALONE is not approval: the approve step also requires a clean
# Devin verdict and zero blocking findings, so counting the judge status
# by itself would flag PRs legitimately held for findings.
#
# "Checks green" treats CANCELLED check-run conclusions as non-blocking —
# approve/fallback cancellations are known concurrency flakes, not signal.

_PR_READY_MIN_AGE_S = 30 * 60
_CHECKRUN_GREEN = {"SUCCESS", "SKIPPED", "NEUTRAL"}


def _rollup_blocker(rollup: object) -> str:
    """First non-green entry on the head's statusCheckRollup, else "".

    CheckRun nodes carry status+conclusion; StatusContext nodes carry
    state. CANCELLED conclusions are ignored (concurrency flakes); a
    non-COMPLETED run or a PENDING/EXPECTED status blocks as "pending".
    """
    if not isinstance(rollup, list):
        return ""
    for entry in rollup:
        if not isinstance(entry, dict):
            continue
        if entry.get("__typename") == "StatusContext" or (
                "state" in entry and "conclusion" not in entry
                and "status" not in entry):
            state = str(entry.get("state") or "").upper()
            if state == "SUCCESS":
                continue
            context = str(entry.get("context") or entry.get("name") or "?")
            if state in {"PENDING", "EXPECTED"}:
                return f"{context} pending"
            return f"{context} {state.lower() or 'unknown'}"
        conclusion = str(entry.get("conclusion") or "").upper()
        if conclusion == "CANCELLED":
            continue
        status = str(entry.get("status") or "").upper()
        name = str(entry.get("name") or entry.get("context") or "?")
        if status and status != "COMPLETED":
            return f"{name} pending ({status.lower()})"
        if conclusion in _CHECKRUN_GREEN:
            continue
        if conclusion:
            return f"{name} {conclusion.lower()}"
        return f"{name} pending"
    return ""


def _judge_success(rollup: object) -> bool:
    """devin-judge/review green on the head — commit status or check run."""
    if not isinstance(rollup, list):
        return False
    for entry in rollup:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("context") or entry.get("name") or "") \
                != "devin-judge/review":
            continue
        if str(entry.get("state") or "").upper() == "SUCCESS":
            return True
        if str(entry.get("conclusion") or "").upper() == "SUCCESS":
            return True
    return False


def _has_manual_blocking0_audit(repo: str, number: int,
                                timeout: int,
                                head_sha: str | None = None) -> bool:
    """Second approval path: the gate-resolved-via audit comment.

    The audit comment carries `head:<sha>`; matching it without the
    sha would let an audit written for an older head still count as
    approval after a push (the workflow itself dedupes per head)."""
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", str(number), "--repo", repo,
             "--json", "comments"],
            capture_output=True, text=True, timeout=timeout + 10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return False
    for comment in data.get("comments") or []:
        if not isinstance(comment, dict):
            continue
        body = str(comment.get("body") or "")
        if "gate-resolved-via: manual-blocking0" not in body:
            continue
        if head_sha and f"head:{head_sha}" not in body:
            continue
        return True
    return False


def _stuck_pr_verdict(pr: dict, now: float) -> str:
    """'' when the PR is approved+green+unmerged+old enough, else why not.

    Returned reasons: draft | armed | changes-requested | too-young |
    checks:<blocker> | not-approved | maybe-manual-blocking0 (needs the
    comments lookup) | no-createdAt.
    """
    if pr.get("isDraft"):
        return "draft"
    if pr.get("autoMergeRequest"):
        return "armed"
    decision = str(pr.get("reviewDecision") or "")
    if decision == "CHANGES_REQUESTED":
        return "changes-requested"
    created = _parse_timestamp(pr.get("createdAt"))
    if created is None:
        return "no-createdAt"
    if now - created < _PR_READY_MIN_AGE_S:
        return "too-young"
    blocker = _rollup_blocker(pr.get("statusCheckRollup"))
    if blocker:
        return f"checks:{blocker}"
    if decision == "APPROVED":
        return ""
    if _judge_success(pr.get("statusCheckRollup")):
        return "maybe-manual-blocking0"
    return "not-approved"


def collect_pr_ready_not_merged(repos: dict[str, str], timeout: int,
                                now: float | None = None) -> list[Row]:
    """One drift Row per approved PR that should have merged but didn't.

    ``repos`` maps repo name -> owner (same shape as collect_open_prs).
    gh failures skip the repo silently — an unreachable API must not
    blank the report. ``now`` is injectable for tests (epoch seconds).
    """
    now = time.time() if now is None else now
    rows: list[Row] = []
    for name, owner in sorted(repos.items()):
        repo = f"{owner}/{name}"
        try:
            proc = subprocess.run(
                ["gh", "pr", "list", "--repo", repo, "--state", "open",
                 "--limit", "100",
                 "--json", "number,title,reviewDecision,isDraft,headRefOid,"
                           "statusCheckRollup,autoMergeRequest,createdAt,url"],
                capture_output=True, text=True, timeout=timeout + 10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            continue
        try:
            prs = json.loads(proc.stdout)
        except ValueError:
            continue
        if not isinstance(prs, list):
            continue
        for pr in prs:
            if not isinstance(pr, dict):
                continue
            try:
                number = int(pr.get("number"))
            except (TypeError, ValueError):
                continue
            verdict = _stuck_pr_verdict(pr, now)
            if verdict == "maybe-manual-blocking0":
                if not _has_manual_blocking0_audit(
                        repo, number, timeout,
                        head_sha=str(pr.get("headRefOid") or "") or None):
                    continue
            elif verdict:
                continue
            created = _parse_timestamp(pr.get("createdAt"))
            age = max(0.0, now - created) if created is not None else 0.0
            title = str(pr.get("title") or "")
            url = str(pr.get("url") or "")
            rows.append(Row(
                product=f"{name}#{number}",
                channel="pr-merge",
                local=f"unmerged {_fmt_age(age)}",
                remote="merged",
                state="drift",
                repo=repo,
                note=f"{title} — {url}"[:200],
            ))
    return rows


def collect_ci_config(repos: dict[str, str], timeout: int) -> list[Row]:
    """Half-configured review-fallback detection -> one Row per physical repo.

    Every registry repo must have BOTH the ``TS_AUTHKEY`` secret AND a
    ``*fallback*.yml`` caller workflow; secrets provisioned without the
    workflow (or vice-versa) mean the review gate waits on evidence that
    can never arrive — exactly the 2026-10-28 incident."""
    out: list[Row] = []
    for name, owner in sorted(repos.items()):
        try:
            secrets = _gh_api(owner, name, "/actions/secrets", timeout)
            names = {s.get("name") for s in secrets.get("secrets", [])}
        except RuntimeError as exc:
            out.append(Row(name, "ci-review-fallback", "—", "—",
                           "unavailable", f"{owner}/{name}", str(exc)[:120]))
            continue
        try:
            wf = _gh_api(owner, name, "/contents/.github/workflows", timeout)
            files = {f.get("name", "") for f in wf if isinstance(f, dict)}
        except RuntimeError:
            files = set()
        has_secret = "TS_AUTHKEY" in names
        has_workflow = any("fallback" in f or "ai-review" in f for f in files)
        if has_secret and has_workflow:
            state, local = "ok", "workflow+secret"
        elif has_secret or has_workflow:
            state = "drift"
            local = "secret only" if has_secret else "workflow only"
        else:
            state, local = "drift", "neither"
        note = "" if state == "ok" else "review gate cannot produce evidence"
        out.append(Row(name, "ci-review-fallback", local, "workflow+secret",
                       state, f"{owner}/{name}", note))
    return out


# ---------------------------------------------------------------------------
# Cron branch sensor (cron_branch_stale)
#
# DL-152e (2026-11-10): the remediate-runner cron ran
# scripts/remediate-runner.py from a checkout sitting on
# backlog/session-rows-oom — a version WITHOUT the auto_merge_pr handler.
# Tasks enqueued by ecosystem_sync were never processed: the sensor path
# dead in production, silently. Same class as the ci-watch.py stale copy
# and uptime-email lost on the VM rebuild. The fix routes every PAS cron
# through ~/.local/bin/pas-cron.sh / remediate-runner-cron.sh, which pull
# --ff-only origin main inside dedicated worktrees and abort on failure;
# this sensor is the regression net for any cron that still executes repo
# code out of a checkout that is not on main.
#
# Scope: the local user crontab of whatever host runs the sync (the laptop
# in practice — VM crontabs are a different fleet). A cron line "uses repo
# code" when it references a path under <home>/devin/ ending in a script
# extension (.py/.sh/.mjs/.js) or cds into a directory under it — and EVERY
# such path is checked, no exemptions: the canonical worktrees under
# <devin>/worktrees/ are expected on main, and the git check proves it
# (ok row) instead of trusting wrapper tokens, which cannot vouch for
# worktrees they did not pull (repo-cron.sh repo-b only updates
# worktrees/repo-b). ~/.local/bin helpers never match the ~/devin/ scope
# at all. ``$HOME``/``~`` spellings expand against the crontab's own
# ``HOME=`` env lines when present; an expansion landing outside the
# configured devin root is reported unavailable, never silently ok. For
# each repo a path resolves to (git rev-parse --show-toplevel), the
# checked-out branch must be `main`; detached HEAD is tolerated only when
# it sits exactly on a tag.
#
# Findings are WARN rows — visible in the report and STATE.md but
# deliberately outside DRIFT_STATES: a stale cron checkout is hygiene debt
# the Owner re-points by hand, not a defect the --remediate agent should
# patch unattended. Undeterminable checkouts (not a git repo, git failure,
# foreign cron HOME) surface as an ``unavailable`` summary row — the
# sensor only flags what it can prove, and never hides what it cannot.

_CRON_SCRIPT_EXTS = (".py", ".sh", ".mjs", ".js")
_CRON_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_CRON_HOME_RE = re.compile(r"""^HOME=(?:"([^"]+)"|'([^']+)'|(\S+))""")
_CRON_SHELL_COMMENT_RE = re.compile(r"\s+#")
# Path characters inside a crontab command: everything except whitespace,
# quotes and shell metacharacters (incl. glob chars, which would only
# produce paths that fail to resolve anyway).
_CRON_PATH_CHARS = r"[^\s\"'`;|&<>()*?\[\]{}]+"


def _cron_path_token_re(devin: Path) -> re.Pattern:
    """Devin-root path tokens in any cron spelling: absolute,
    ``$HOME/<name>/…`` or ``~/<name>/…``."""
    name = re.escape(devin.name)
    root = rf"(?:{re.escape(str(devin))}|\$HOME/{name}|~/{name})"
    return re.compile(rf"{root}/{_CRON_PATH_CHARS}")


def _cron_cd_re(devin: Path) -> re.Pattern:
    """``cd <devin-root path>`` — a directory target needs no extension."""
    name = re.escape(devin.name)
    root = rf"(?:{re.escape(str(devin))}|\$HOME/{name}|~/{name})"
    return re.compile(rf"\bcd\s+[\"']?({root}/{_CRON_PATH_CHARS})")


def _normalize_cron_path(raw: str, devin: Path,
                         home: Path) -> Path | None:
    """``$HOME``/``~`` spellings -> absolute path, ``None`` when foreign.

    ``$HOME`` and ``~`` expand against the crontab's effective HOME (env
    ``HOME=`` lines override it), not necessarily the sync process's.
    When that expansion lands outside the configured devin root the path
    belongs to another account's tree — out of scope, reported as foreign
    rather than classified against the wrong home.
    """
    prefix = str(devin)
    if raw == prefix or raw.startswith(prefix + "/"):
        return Path(raw)
    marker = f"/{devin.name}/"
    if marker in raw:
        resolved = home / devin.name / raw.split(marker, 1)[1]
        try:
            resolved_r, devin_r = resolved.resolve(), devin.resolve()
        except OSError:
            resolved_r, devin_r = resolved, devin
        if resolved_r != devin_r and devin_r not in resolved_r.parents:
            return None
        return resolved
    return Path(raw)


def _cron_repo_candidates(line: str, devin: Path,
                          home: Path | None = None
                          ) -> tuple[list[Path], int]:
    """Devin-root paths a cron command may execute, plus foreign count.

    Returns ``(paths, foreign)``: ``paths`` are absolute candidates under
    the devin root, deduped in order; ``foreign`` counts ``$HOME``/``~``
    spellings whose expansion lands outside it (a crontab ``HOME=``
    override pointing at another account's tree). Script files
    (.py/.sh/.mjs/.js) qualify anywhere on the line; a ``cd <dir>`` target
    qualifies without an extension — both resolve to a repo root
    downstream. ``home`` defaults to the devin root's parent, the home
    the ``devin`` dir conventionally lives under.
    """
    home = devin.parent if home is None else home
    paths: list[Path] = []
    foreign = 0
    for match in _cron_path_token_re(devin).finditer(line):
        raw = match.group(0)
        if raw.lower().endswith(_CRON_SCRIPT_EXTS):
            norm = _normalize_cron_path(raw, devin, home)
            if norm is None:
                foreign += 1
            else:
                paths.append(norm)
    for match in _cron_cd_re(devin).finditer(line):
        norm = _normalize_cron_path(match.group(1), devin, home)
        if norm is None:
            foreign += 1
        else:
            paths.append(norm)
    return list(dict.fromkeys(paths)), foreign


def _git(repo: Path, *args: str,
         timeout: int) -> subprocess.CompletedProcess | None:
    """``git -C <repo> <args>``; None on spawn/timeout failure."""
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _cron_repo_root(candidate: Path, devin: Path,
                    timeout: int) -> Path | None:
    """Git toplevel containing ``candidate`` when it lives under devin.

    The candidate may be a file (probe its parent) or not exist at all
    (walk up to the nearest existing directory). ``None`` when the path
    is not inside a git repo or the repo resolves ABOVE the devin root —
    both out of this sensor's scope.
    """
    probe = candidate if candidate.is_dir() else candidate.parent
    while not probe.is_dir() and probe != probe.parent:
        probe = probe.parent
    if not probe.is_dir():
        return None
    proc = _git(probe, "rev-parse", "--show-toplevel", timeout=timeout)
    if proc is None or proc.returncode != 0:
        return None
    top = proc.stdout.strip()
    if not top:
        return None
    root = Path(top)
    try:
        root_r, devin_r = root.resolve(), devin.resolve()
    except OSError:
        root_r, devin_r = root, devin
    if root_r != devin_r and devin_r not in root_r.parents:
        return None
    return root


def _cron_repo_ref(repo_root: Path, timeout: int) -> str | None:
    """HEAD descriptor for a repo checkout: ``main``, ``<branch>``,
    ``tag:<name>`` (detached exactly on a tag) or ``detached@<sha>``.
    ``None`` when git cannot prove the state."""
    proc = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD",
               timeout=timeout)
    if proc is None or proc.returncode != 0:
        return None
    ref = proc.stdout.strip()
    if not ref:
        return None
    if ref != "HEAD":  # named branch — "HEAD" means detached
        return ref
    tag = _git(repo_root, "describe", "--tags", "--exact-match", "HEAD",
               timeout=timeout)
    if tag is not None and tag.returncode == 0 and tag.stdout.strip():
        return f"tag:{tag.stdout.strip()}"
    sha = _git(repo_root, "rev-parse", "--short", "HEAD", timeout=timeout)
    short = sha.stdout.strip() if (
        sha is not None and sha.returncode == 0) else "?"
    return f"detached@{short}"


def collect_cron_branch_stale(devin: Path | str | None = None,
                              home: Path | str | None = None,
                              timeout: int = 5) -> list[Row]:
    """Cron entries running repo code off a non-main checkout -> rows.

    See the section comment for scope. One row per repo checkout the
    crontab touches: ``warn`` when HEAD is not ``main`` (detached HEAD
    only tolerated exactly on a tag), ``ok`` otherwise. ``skip``/
    ``unavailable`` rows cover a missing crontab, git failures and
    ``$HOME``/``~`` expansions landing outside the devin root. ``home``
    is the home ``$HOME``/``~`` expand against when the crontab sets no
    ``HOME=`` itself (defaults to the process home; the devin root
    defaults to ``<home>/devin``).
    """
    home_path = (Path(home).expanduser() if home is not None
                 else Path.home())
    devin_path = (Path(devin).expanduser() if devin is not None
                  else home_path / "devin")
    if shutil.which("crontab") is None:
        return [Row("cron-branch-stale", "cron-branch", "—", "—", "skip",
                    "", "crontab not installed on this host")]
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [Row("cron-branch-stale", "cron-branch", "—", "—",
                    "unavailable", "",
                    f"crontab -l failed: {type(exc).__name__}")]
    if proc.returncode != 0:
        # "no crontab for <user>" is the only clean failure — rc=1 with
        # that diagnostic on stderr (some builds echo it on stdout).
        # Anything else (permission denied, spool errors, rc>=2, silent
        # rc=1) stays honestly unavailable rather than a false "empty".
        blob = f"{proc.stderr or ''}\n{proc.stdout or ''}".lower()
        if proc.returncode == 1 and "no crontab" in blob:
            return [Row("cron-branch-stale", "cron-branch", "—", "—",
                        "ok", "", "no crontab for this user")]
        return [Row("cron-branch-stale", "cron-branch", "—", "—",
                    "unavailable", "",
                    f"crontab -l rc={proc.returncode}: "
                    f"{(proc.stderr or proc.stdout or '').strip()[:120]}")]
    hits: dict[Path, dict] = {}
    foreign = 0
    current_home = home_path
    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        home_match = _CRON_HOME_RE.match(line)
        if home_match:
            # crontab env line: HOME= applies to every command AFTER it.
            value = next(g for g in home_match.groups() if g is not None)
            current_home = Path(value).expanduser()
            continue
        if _CRON_ENV_RE.match(line):
            continue  # other NAME=value environment line, not a command
        line = _CRON_SHELL_COMMENT_RE.split(line, maxsplit=1)[0].strip()
        if not line:
            continue
        per_line: dict[Path, list[Path]] = {}
        paths, line_foreign = _cron_repo_candidates(
            line, devin_path, current_home)
        foreign += line_foreign
        for cand in paths:
            root = _cron_repo_root(cand, devin_path, timeout)
            if root is not None:
                per_line.setdefault(root, []).append(cand)
        for root, cands in per_line.items():
            slot = hits.setdefault(root, {"paths": set(), "entries": 0})
            slot["paths"].update(cands)
            slot["entries"] += 1
    rows: list[Row] = []
    undetermined = 0
    for root in sorted(hits, key=str):
        info = hits[root]
        ref = _cron_repo_ref(root, timeout)
        if ref is None:
            undetermined += 1
            continue
        shown = sorted(str(p) for p in info["paths"])
        note = (f"{info['entries']} cron "
                f"{'entry' if info['entries'] == 1 else 'entries'}"
                f" -> {', '.join(shown[:3])}"
                + (f" +{len(shown) - 3} more" if len(shown) > 3 else ""))
        local = ref.removeprefix("tag:")
        state = "ok" if ref == "main" or ref.startswith("tag:") else "warn"
        rows.append(Row(root.name or str(root), "cron-branch", local,
                        "main", state, "", note))
    notes: list[str] = []
    if undetermined:
        notes.append(f"{undetermined} repo checkout(s) could not be "
                     "classified")
    if foreign:
        notes.append(f"{foreign} path(s) under a cron HOME outside the "
                     "sync home")
    if notes:
        rows.append(Row("cron-branch-stale", "cron-branch", "—", "—",
                        "unavailable", "", "; ".join(notes)))
    if not hits and not foreign:
        rows.append(Row("cron-branch-stale", "cron-branch", "—", "—",
                        "ok", "", "no repo-script cron entries under "
                                  "~/devin"))
    return rows


# ---------------------------------------------------------------------------
# Freshness / silence sensors
#
# A component that is alive but produces nothing within its expected interval
# is a failure ("sensor works, channel dead" incident class). Each probe
# resolves the newest output timestamp it can prove; silence past the
# component's threshold lands in DRIFT_STATES so --issue and --state-md flag
# it, while an undeterminable timestamp is "unavailable" — honest, not noisy.
#
# Probe result convention: (epoch_or_None, determined, note)
#   determined=True  + epoch   -> last output at epoch (age decides ok/drift)
#   determined=True  + None    -> source exists but produced nothing ("never")
#   determined=False           -> cannot prove freshness ("unavailable")

SILENCE_LABEL = "silence-alert"
SILENCE_REPO_PAS = "Icaro0310/personal-agent-system"
SILENCE_REPO_HUB = "Icaro0310/devin-powerups"

# (product, threshold_hours, repo that owns silence issues)
_FRESHNESS_CHECKS = (
    ("dispatcher", 48, SILENCE_REPO_PAS),
    ("slack-output", 72, SILENCE_REPO_PAS),
    ("scout", 96, SILENCE_REPO_PAS),
    ("review-fallback", 168, SILENCE_REPO_HUB),
    ("heartbeat", 1, SILENCE_REPO_PAS),
)

# Plausible epoch window: 2000-01-01 .. 2100-01-01 — keeps counters like
# "trends": 40 from being read as timestamps.
_EPOCH_MIN = 946_684_800.0
_EPOCH_MAX = 4_102_444_800.0


def _parse_timestamp(value: object) -> float | None:
    """Epoch seconds for a number / numeric string / ISO datetime, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        epoch = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            epoch = float(text)
        except ValueError:
            iso = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
            match = re.search(r"([+-]\d{2})(\d{2})$", iso)
            if match:  # '+0100' -> '+01:00' (fromisoformat wants the colon)
                iso = f"{iso[:match.start()]}{match.group(1)}:{match.group(2)}"
            try:
                parsed = datetime.fromisoformat(iso)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            epoch = parsed.timestamp()
    else:
        return None
    if epoch > 1e12:  # milliseconds epoch
        epoch /= 1000.0
    if not _EPOCH_MIN <= epoch <= _EPOCH_MAX:
        return None
    return epoch


def _timestamps_in_json(obj: object) -> list[float]:
    """Every parseable timestamp found anywhere in a decoded JSON value."""
    found: list[float] = []
    stack: list[object] = [obj]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
        else:
            epoch = _parse_timestamp(current)
            if epoch is not None:
                found.append(epoch)
    return found


def _fmt_age(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    return f"{int(round(seconds / 3600.0))}h"


def _fmt_threshold(hours: float) -> str:
    hours = float(hours)
    if hours < 1:
        return f"<={int(round(hours * 60))}m"
    if hours >= 24 and hours % 24 == 0:
        return f"<={int(hours) // 24}d"
    return f"<={hours:g}h"


def _fresh_row(product: str, repo: str, threshold_h: float,
               probe: tuple[float | None, bool, str], now: float) -> Row:
    """Map one probe result to a freshness Row (ok | drift | unavailable)."""
    remote = _fmt_threshold(threshold_h)
    epoch, determined, note = probe
    if not determined:
        return Row(product, "freshness", "—", remote, "unavailable", repo, note)
    if epoch is None:
        return Row(product, "freshness", "never", remote, "drift", repo, note)
    age = max(0.0, now - epoch)
    state = "ok" if age <= threshold_h * 3600 else "drift"
    return Row(product, "freshness", _fmt_age(age), remote, state, repo, note)


def _probe_dispatcher(roots: list[Path],
                      timeout: int) -> tuple[float | None, bool, str]:
    """qwenpaw-queue last finished task: sqlite MAX(finished_at), else qdispatch."""
    candidates: list[Path] = []
    for root in roots:
        candidates.append(root / "qwenpaw-queue" / "qwenpaw-queue.db")
        candidates.extend(sorted(root.glob("*/qwenpaw-queue/qwenpaw-queue.db")))
    for db in dict.fromkeys(candidates):
        if not db.is_file():
            continue
        try:
            conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        except (OSError, sqlite3.Error):
            continue
        try:
            for column in ("finished_at", "completed_at"):
                try:
                    row = conn.execute(
                        f"SELECT MAX({column}) FROM tasks").fetchone()
                except sqlite3.Error:
                    continue  # schema variant — try the other column
                if row is None or row[0] is None:
                    return None, True, f"{db}: no finished task yet"
                epoch = _parse_timestamp(row[0])
                if epoch is not None:
                    return epoch, True, f"{db.name} tasks.{column}"
                return None, False, f"{db}: unparsable tasks.{column}"
        finally:
            conn.close()
    qdispatch_scripts: list[Path] = []
    for root in roots:
        qdispatch_scripts.append(root / "scripts" / "qdispatch.py")
        qdispatch_scripts.extend(sorted(root.glob("*/scripts/qdispatch.py")))
    for script in dict.fromkeys(qdispatch_scripts):
        if not script.is_file():
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "stats"],
                capture_output=True, text=True, timeout=timeout + 5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            continue
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        last_done = data.get("last_done")
        if last_done is None:
            return None, True, "qdispatch stats: no last_done task"
        if isinstance(last_done, dict):
            for key in ("finished_at", "completed_at", "ts", "time"):
                epoch = _parse_timestamp(last_done.get(key))
                if epoch is not None:
                    return epoch, True, f"qdispatch last_done.{key}"
            return None, False, "qdispatch last_done has no timestamp"
        epoch = _parse_timestamp(last_done)
        if epoch is not None:
            return epoch, True, "qdispatch last_done"
    return None, False, "no qwenpaw-queue.db or qdispatch.py under roots"


def _probe_slack_output() -> tuple[float | None, bool, str]:
    """Last successful Slack send from the slack-notify ledger."""
    xdg = os.environ.get("XDG_STATE_HOME")
    bases = [Path(xdg)] if xdg else []
    bases.append(Path.home() / ".local" / "state")
    candidates: list[Path] = []
    for base in bases:
        candidates.append(base / "devin" / "slack-notify" / "last-sent.json")
        candidates.append(base / "devin" / "slack-notify" / "last-sent.jsonl")
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if path.suffix == ".jsonl":
                line = next(
                    (ln for ln in reversed(text.splitlines()) if ln.strip()), "")
                data = json.loads(line) if line else None
            else:
                data = json.loads(text)
        except (OSError, ValueError):
            return None, False, f"{path}: unreadable send ledger"
        if not isinstance(data, dict):
            return None, False, f"{path}: unreadable send ledger"
        for key in ("ts", "time", "timestamp", "date", "sent_at"):
            epoch = _parse_timestamp(data.get(key))
            if epoch is not None:
                return epoch, True, f"{path.name} {key}"
        found = _timestamps_in_json(data)
        if found:
            return max(found), True, path.name
        return None, False, f"{path}: no timestamp field"
    return None, False, "no send ledger yet"


def _probe_scout(roots: list[Path]) -> tuple[float | None, bool, str]:
    """Newest weekly-scout.jsonl entry timestamp."""
    rel = Path(".config") / "devin" / "repo-maintenance" / "weekly-scout.jsonl"
    candidates: list[Path] = [Path.home() / rel]
    candidates.extend(sorted(Path.home().glob(f"*/{rel.as_posix()}")))
    for root in roots:
        candidates.append(root / rel)
        candidates.extend(sorted(root.glob(f"*/{rel.as_posix()}")))
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            lines = [ln for ln in
                     path.read_text(encoding="utf-8", errors="replace").splitlines()
                     if ln.strip()]
        except OSError:
            continue
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            for key in ("ts", "time", "timestamp", "date", "run_id",
                        "created_at"):
                epoch = _parse_timestamp(entry.get(key))
                if epoch is not None:
                    return epoch, True, f"{path.name} {key}"
            found = _timestamps_in_json(entry)
            if found:
                return max(found), True, path.name
        return None, False, f"{path}: entries without timestamps"
    return None, False, "weekly-scout.jsonl not found"


def _probe_review_fallback(owners: dict[str, str],
                           timeout: int) -> tuple[float | None, bool, str]:
    """Newest completed review-fallback workflow run across the fleet."""
    best: float | None = None
    any_success = False
    for name, owner in sorted(owners.items()):
        try:
            proc = subprocess.run(
                ["gh", "run", "list", "--repo", f"{owner}/{name}",
                 "--workflow", "review-fallback", "--status", "completed",
                 "--limit", "1", "--json", "createdAt"],
                capture_output=True, text=True, timeout=timeout + 5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            # "could not find any workflows named X" is a definitive answer —
            # the repo has no review-fallback, so it contributes no runs.
            if "could not find" in (proc.stderr or proc.stdout or ""):
                any_success = True
            continue
        any_success = True
        try:
            runs = json.loads(proc.stdout)
        except ValueError:
            continue
        for run in runs if isinstance(runs, list) else []:
            epoch = _parse_timestamp(
                run.get("createdAt") if isinstance(run, dict) else None)
            if epoch is not None and (best is None or epoch > best):
                best = epoch
    if not any_success:
        return None, False, "gh run list failed for all repos"
    if best is None:
        return None, True, "no completed review-fallback run found"
    return best, True, "newest completed review-fallback run"


def _probe_heartbeat(roots: list[Path]) -> tuple[float | None, bool, str]:
    """Newest timestamp in heartbeat/state.json (hourly cron)."""
    candidates: list[Path] = []
    for root in roots:
        candidates.append(
            root / "personal-agent-system" / "heartbeat" / "state.json")
        candidates.extend(sorted(root.glob("*/heartbeat/state.json")))
        candidates.append(root / "heartbeat" / "state.json")
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, False, f"{path}: unreadable"
        if not isinstance(data, dict):
            return None, False, f"{path}: unreadable"
        values: list[object] = []
        for key in ("last_cycle_at", "last_run", "ts", "time", "date"):
            value = data.get(key)
            if value is not None:
                values.append(value)
        for key in ("last_notified", "last_sent"):
            value = data.get(key)
            if isinstance(value, dict):
                values.extend(value.values())
        merge_gates = data.get("merge_gates")
        if isinstance(merge_gates, dict):
            values.extend(merge_gates.values())
        found = [ts for ts in (_parse_timestamp(v) for v in values)
                 if ts is not None]
        if not found:
            found = _timestamps_in_json(data)
        if found:
            return max(found), True, path.name
        return None, False, f"{path}: no timestamp fields"
    return None, False, "heartbeat state.json not found"


# ---------------------------------------------------------------------------
# Universal silence matrix (freshness v2)
#
# On top of the five bespoke probes, every ops tool that emits to the shared
# heartbeat ledger ($XDG_STATE_HOME/devin/heartbeats.jsonl, overridable via
# $DEVIN_HEARTBEAT_FILE) gets a row driven by tools/silence-matrix.json:
#     {tool: {"threshold_h": hours, "repo": "owner/issue-repo"}}
# Two failure classes land in DRIFT_STATES:
#   silence    now - last_success_at > threshold        -> "<tool>" row
#   err streak last_failure_at > last_success_at        -> "<tool> (errors)"
# A tool absent from the ledger is "drift/never" when it looks installed
# (crontab/systemd evidence or a scripts|bin path match) and "unavailable"
# otherwise — never-emitted is signal, uninstalled is noise.

SILENCE_MATRIX_PATH = Path(__file__).resolve().parent / "silence-matrix.json"


def _load_silence_matrix(path: Path | None = None) -> dict[str, dict]:
    """Silence matrix ``{tool: {"threshold_h": float, "repo": str}}``.

    Falls back to the built-in five sensors when the shipped JSON is
    missing, unreadable or has no valid entries."""
    source = Path(path) if path else SILENCE_MATRIX_PATH
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    matrix: dict[str, dict] = {}
    if isinstance(data, dict):
        for tool, cfg in data.items():
            if not isinstance(tool, str) or not tool.strip():
                continue
            if not isinstance(cfg, dict):
                continue
            try:
                threshold_h = float(cfg.get("threshold_h"))
            except (TypeError, ValueError):
                continue
            if threshold_h <= 0:
                continue
            host = cfg.get("host")
            matrix[tool.strip()] = {
                "threshold_h": threshold_h,
                "repo": str(cfg.get("repo") or SILENCE_REPO_PAS),
                **({"host": str(host)} if isinstance(host, str)
                    and host.strip() else {}),
            }
    if not matrix:
        matrix = {tool: {"threshold_h": float(h), "repo": repo}
                  for tool, h, repo in _FRESHNESS_CHECKS}
    return matrix


def _heartbeat_ledger_paths(roots: list[Path] | None = None) -> list[Path]:
    """Candidate heartbeats.jsonl locations, deduped in priority order.

    The ledger lives under the service account's state dir, so beside the
    XDG default and $DEVIN_HEARTBEAT_FILE we also scan each checkout root
    (a service home may itself be a root)."""
    paths: list[Path] = []
    env_file = os.environ.get("DEVIN_HEARTBEAT_FILE")
    if env_file:
        paths.append(Path(env_file).expanduser())
    xdg = os.environ.get("XDG_STATE_HOME")
    state_bases = [Path(xdg)] if xdg else []
    state_bases.append(Path.home() / ".local" / "state")
    for base in state_bases:
        paths.append(base / "devin" / "heartbeats.jsonl")
    for root in roots or []:
        root = Path(root)
        paths.append(root / ".local" / "state" / "devin" / "heartbeats.jsonl")
        paths.extend(sorted(
            root.glob("*/.local/state/devin/heartbeats.jsonl")))
    return list(dict.fromkeys(paths))


def _read_heartbeats(roots: list[Path] | None = None) -> dict[str, dict]:
    """Merge every heartbeat ledger into
    ``{tool: {last_success_at, last_failure_at, last_detail}}``.

    Lines are ``{"ts": epoch, "tool": name, "event": "success"|"failure",
    "detail": str}``; malformed lines/files are skipped, never fatal."""
    tools: dict[str, dict] = {}
    for path in _heartbeat_ledger_paths(roots):
        try:
            lines = path.read_text(
                encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool")
            if not isinstance(tool, str) or not tool.strip():
                continue
            ts = _parse_timestamp(entry.get("ts"))
            if ts is None:
                continue
            slot = tools.setdefault(tool.strip(), {
                "last_success_at": None,
                "last_failure_at": None,
                "last_detail": "",
                "_latest_ts": None,
            })
            event = str(entry.get("event") or "").strip().lower()
            if event == "success":
                if slot["last_success_at"] is None or ts > slot["last_success_at"]:
                    slot["last_success_at"] = ts
            elif event == "failure":
                if slot["last_failure_at"] is None or ts > slot["last_failure_at"]:
                    slot["last_failure_at"] = ts
            if slot["_latest_ts"] is None or ts >= slot["_latest_ts"]:
                slot["_latest_ts"] = ts
                detail = entry.get("detail")
                slot["last_detail"] = str(detail)[:200] if detail is not None else ""
    for slot in tools.values():
        slot.pop("_latest_ts", None)
    return tools


def _install_evidence(timeout: int = 5) -> str:
    """Text corpus for the 'is it installed' heuristic.

    User crontab plus systemd --user unit names — the instrumented fleet
    (slack-poll, office, queue-*, autodeploy…) runs as services, so unit
    files count as installation evidence just like crontab lines. Both
    probes tolerate absence."""
    chunks: list[str] = []
    for cmd in (["crontab", "-l"],
                ["systemctl", "--user", "list-unit-files", "--no-legend"]):
        if shutil.which(cmd[0]) is None:
            continue
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0 and proc.stdout:
            chunks.append(proc.stdout)
    return "\n".join(chunks)


def _tool_is_installed(tool: str, roots: list[Path], evidence: str) -> bool:
    """'Installed' heuristic: the name appears in crontab/systemd evidence
    or a ``scripts/<tool>*`` / ``bin/<tool>*`` path exists under a root."""
    if evidence and re.search(
            rf"(?<![A-Za-z0-9]){re.escape(tool)}(?![A-Za-z0-9])", evidence):
        return True
    for root in roots:
        for pattern in (f"scripts/{tool}*", f"bin/{tool}*",
                        f"*/scripts/{tool}*", f"*/bin/{tool}*"):
            try:
                if any(root.glob(pattern)):
                    return True
            except OSError:
                continue
    return False


# (workflow file, threshold_days, kind) — kind routes silence issues:
# "ecosystem" -> devin-powerups, "ops" -> personal-agent-system.
WORKFLOW_CHECKS = (
    ("ai-review-fallback.yml", 7, "ecosystem"),
    ("ci.yml", 14, "ecosystem"),
    ("pypi-publish.yml", 30, "ecosystem"),
    ("release.yml", 30, "ecosystem"),
)
WORKFLOW_KIND_REPOS = {
    "ecosystem": SILENCE_REPO_HUB,
    "ops": SILENCE_REPO_PAS,
}
# Conclusions that count toward an err streak or break it; cancelled /
# skipped / neutral are neither failure nor success for this purpose.
_WORKFLOW_SIG_CONCLUSIONS = {
    "success", "failure", "timed_out", "startup_failure", "action_required",
}


def _this_host() -> str:
    """Which silence-sensor host are we? The VM owns its own tool set."""
    if os.environ.get("DEVIN_HOST"):
        return os.environ["DEVIN_HOST"]
    return "vm" if str(Path.home()) == "/root" or Path(
        "/root/qwenpaw-queue").exists() else "laptop"


def _workflow_freshness(owners: dict[str, str], timeout: int,
                        now: float | None = None) -> list[Row]:
    """Per-workflow GitHub Actions freshness, aggregated across the fleet.

    For each (owner, repo) x workflow the newest 3 runs are inspected;
    per workflow the newest completed run marks last activity and the
    newest ``success`` run marks last success. A newest completed run with
    a non-success conclusion and no newer success is an ``err streak``
    drift. Every repo failing to query makes the row ``unavailable``.
    """
    now = time.time() if now is None else now
    rows: list[Row] = []
    for workflow_file, threshold_d, kind in WORKFLOW_CHECKS:
        threshold_h = threshold_d * 24.0
        repo = WORKFLOW_KIND_REPOS.get(kind, SILENCE_REPO_HUB)
        product = Path(workflow_file).stem
        newest_completed: tuple[float, str] | None = None
        newest_success: float | None = None
        significant: list[tuple[float, str]] = []
        queried = 0
        for name, owner in sorted(owners.items()):
            try:
                proc = subprocess.run(
                    ["gh", "run", "list", "--repo", f"{owner}/{name}",
                     "--workflow", workflow_file, "--limit", "3",
                     "--json", "createdAt,conclusion"],
                    capture_output=True, text=True, timeout=timeout + 5)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if proc.returncode != 0:
                # Absent-workflow errors are definitive answers, not query
                # failures — gh says either "could not find any workflows
                # named X" (name lookup) or "HTTP 404: workflow X not
                # found on the default branch" (file lookup).
                msg = (proc.stderr or proc.stdout or "").lower()
                if "could not find" in msg or "not found" in msg \
                        or "404" in msg:
                    queried += 1
                continue
            queried += 1
            try:
                runs = json.loads(proc.stdout)
            except ValueError:
                continue
            for run in runs if isinstance(runs, list) else []:
                if not isinstance(run, dict):
                    continue
                conclusion = str(run.get("conclusion") or "")
                if not conclusion:  # queued / in_progress — not completed
                    continue
                ts = _parse_timestamp(run.get("createdAt"))
                if ts is None:
                    continue
                if newest_completed is None or ts > newest_completed[0]:
                    newest_completed = (ts, conclusion)
                if conclusion == "success" and (
                        newest_success is None or ts > newest_success):
                    newest_success = ts
                if conclusion in _WORKFLOW_SIG_CONCLUSIONS:
                    significant.append((ts, conclusion))
        remote = _fmt_threshold(threshold_h)
        if queried == 0:
            rows.append(Row(product, "freshness", "—", remote,
                            "unavailable", repo,
                            "gh run list failed for all repos"))
            continue
        note = f"{queried} repo(s) queried for {workflow_file}"
        rows.append(_fresh_row(
            product, repo, threshold_h,
            (newest_completed[0] if newest_completed else None, True, note),
            now))
        # err streak: the newest 3 *significant* runs all failed — a single
        # red PR run or a cancelled duplicate is not pipeline death.
        significant.sort(reverse=True)
        streak = significant[:3]
        if len(streak) == 3 and all(
                c != "success" for _, c in streak):
            rows.append(Row(
                f"{product} (errors)", "freshness", "err streak",
                remote, "drift", repo,
                f"3 consecutive non-success conclusions "
                f"(newest={streak[0][1]})"))
    return rows


def collect_freshness(roots: list[Path], owners: dict[str, str],
                      timeout: int = DEFAULT_TIMEOUT,
                      now: float | None = None) -> list[Row]:
    """Freshness rows for every silence-sensed component.

    ``owners`` maps repo name -> owner (same shape collect_ci_config takes);
    it feeds the review-fallback scan and the workflow roll-up. Matrix
    tools whose name collides with a bespoke probe keep the bespoke probe;
    every other matrix entry is driven by the heartbeat ledger. ``now``
    is injectable for tests — epoch seconds.
    """
    now = time.time() if now is None else now
    matrix = _load_silence_matrix()
    probes = {
        "dispatcher": lambda: _probe_dispatcher(roots, timeout),
        "slack-output": _probe_slack_output,
        "scout": lambda: _probe_scout(roots),
        "review-fallback": lambda: _probe_review_fallback(owners, timeout),
        "heartbeat": lambda: _probe_heartbeat(roots),
    }
    heartbeats = _read_heartbeats(roots)
    evidence = _install_evidence()
    rows: list[Row] = []
    for tool, cfg in matrix.items():
        threshold_h = float(cfg["threshold_h"])
        repo = str(cfg.get("repo") or SILENCE_REPO_PAS)
        host = cfg.get("host")
        if host and host != _this_host():
            continue  # foreign-host tool: not this machine's silence to sense
        if tool in probes:
            rows.append(_fresh_row(tool, repo, threshold_h,
                                   probes[tool](), now))
            continue
        entry = heartbeats.get(tool)
        if entry is None:
            if _tool_is_installed(tool, roots, evidence):
                probe = (None, True,
                         "installed but never emitted to heartbeat ledger")
            else:
                probe = (None, False,
                         "no heartbeat entries; not found installed")
            rows.append(_fresh_row(tool, repo, threshold_h, probe, now))
            continue
        last_success = entry.get("last_success_at")
        last_failure = entry.get("last_failure_at")
        detail = str(entry.get("last_detail") or "")
        note = "heartbeat ledger" + (f": {detail[:120]}" if detail else "")
        rows.append(_fresh_row(tool, repo, threshold_h,
                               (last_success, True, note), now))
        if last_failure is not None and (
                last_success is None or last_failure > last_success):
            rows.append(Row(
                f"{tool} (errors)", "freshness", "err streak",
                _fmt_threshold(threshold_h), "drift", repo,
                detail[:160] or "recent failures dominate"))
    rows.extend(_workflow_freshness(owners, timeout, now=now))
    return rows


def build_rows(products: list[Product], extensions: list[VsCodeExt],
               website_html: str | None, timeout: int, offline: bool,
               opener=urllib.request.urlopen) -> list[Row]:
    rows: list[Row] = []
    tags_cache: dict = {}
    website_checked = website_html is not None

    def website_row(name: str, repo: str) -> Row:
        if not website_checked:
            return Row(name, "website", name, "—", "unavailable", repo)
        state = "ok" if name in website_html else "absent"
        return Row(name, "website", name, "listed" if state == "ok" else "not-found", state, repo)

    for product in products:
        repo = f"{product.repo_owner}/{product.repo_name}"
        local = product.local_version or product.registry_version

        if product.registry_version or product.local_version:
            state = "n/a"
            remote = product.registry_version or "—"
            if product.local_version and product.registry_version:
                state = "ok" if product.local_version == product.registry_version else "drift"
            elif product.local_version:
                remote, state = "—", "n/a"
            rows.append(Row(product.name, "registry", product.local_version or "—",
                            remote, state, repo))

        if offline:
            if product.dist_name:
                rows.append(Row(product.name, product.ecosystem or "remote",
                                local or "—", "—", "skip", repo, "offline"))
            continue

        if product.ecosystem == "pypi" and product.dist_name:
            try:
                remote = pypi_version(product.dist_name, timeout, opener=opener)
            except KeyError:
                remote = ""
            except RuntimeError:
                remote = None
            rows.append(_compare(product.name, "pypi", local, remote, repo))
        elif product.ecosystem == "npm" and product.dist_name:
            try:
                remote = npm_version(product.dist_name, timeout, opener=opener)
            except KeyError:
                remote = ""
            except RuntimeError:
                remote = None
            rows.append(_compare(product.name, "npm", local, remote, repo))

        if local:
            try:
                remote = github_release_version(
                    product.repo_owner, product.repo_name, tag_prefixes(product),
                    timeout, cache=tags_cache,
                )
            except KeyError:
                remote = ""
            except (RuntimeError, subprocess.TimeoutExpired, OSError):
                remote = None
            rows.append(_compare(product.name, "github-release", local, remote, repo))

        rows.append(website_row(product.name, repo))

    owner_by_repo = {p.repo_name: p.repo_owner for p in products}
    for ext in extensions:
        owner = owner_by_repo.get(ext.repo_name, products[0].repo_owner if products else "")
        repo = f"{owner}/{ext.repo_name}" if owner else ext.repo_name
        if offline:
            rows.append(Row(ext.name, "open-vsx", ext.version or "—", "—", "skip", repo, "offline"))
        else:
            try:
                remote = open_vsx_version(ext.name, timeout, opener=opener)
            except KeyError:
                remote = ""
            except RuntimeError:
                remote = None
            rows.append(_compare(ext.name, "open-vsx", ext.version, remote, repo))
            try:
                remote = marketplace_version(ext.name, timeout)
            except RuntimeError:
                remote = None
            rows.append(_compare(ext.name, "vscode-marketplace", ext.version,
                                 remote, repo))
            rows.append(website_row(ext.name, repo))

        for vsix in sorted(ext.manifest.parent.glob("*.vsix")):
            bundled = vsix_version(vsix)
            if not bundled:
                rows.append(Row(ext.name, "vsix", ext.version or "—", "—",
                                "unavailable", repo, f"{vsix.name}: unreadable"))
            else:
                state = "ok" if bundled == ext.version else "stale-vsix"
                rows.append(Row(ext.name, "vsix", ext.version or "—", bundled,
                                state, repo, vsix.name))
    return rows


def render_report(rows: list[Row], health: list[tuple[str, str]],
                  roots: list[Path], generated: datetime) -> str:
    lines = [
        f"ECOSYSTEM SYNC — drift report {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"roots: {', '.join(str(r) for r in roots)}",
        "",
        f"{'product':<24} {'channel':<19} {'local':<12} {'remote':<12} state",
        f"{'-' * 24} {'-' * 19} {'-' * 12} {'-' * 12} {'-' * 14}",
    ]
    for row in rows:
        local, remote = row.local or "—", row.remote or "—"
        suffix = f"  ({row.note})" if row.note else ""
        lines.append(f"{row.product:<24} {row.channel:<19} {local:<12} "
                     f"{remote:<12} {row.state}{suffix}")
    drift = [r for r in rows if r.state in DRIFT_STATES]
    unavailable = [r for r in rows if r.state == "unavailable"]
    lines += [
        "",
        f"summary: {len(drift)} drift row(s), {len(unavailable)} unavailable check(s), "
        f"{len(rows)} total row(s)",
        "",
        "HEALTH",
    ]
    for name, status in health:
        lines.append(f"  {name}: {status}")
    return "\n".join(lines)


def open_drift_issues(rows: list[Row], timeout: int) -> list[str]:
    """One `drift`-labeled GitHub issue per repo with drift, deduped on open issues."""
    messages: list[str] = []
    by_repo: dict[str, list[Row]] = {}
    for row in rows:
        if row.state in DRIFT_STATES and row.repo:
            by_repo.setdefault(row.repo, []).append(row)
    for repo, repo_rows in sorted(by_repo.items()):
        try:
            proc = subprocess.run(
                ["gh", "issue", "list", "--repo", repo, "--label", "drift",
                 "--state", "open", "--json", "number,title", "--limit", "50"],
                capture_output=True, text=True, timeout=timeout + 10,
            )
            open_issues = json.loads(proc.stdout) if proc.returncode == 0 else []
        except (OSError, ValueError, subprocess.TimeoutExpired):
            open_issues = []
        title = f"ecosystem_sync: drift detected in {repo.split('/')[-1]}"
        existing = next(
            (i for i in open_issues if "drift" in str(i.get("title", "")).lower()),
            None,
        )
        if existing:
            try:
                proc = subprocess.run(
                    ["gh", "issue", "view", str(existing["number"]),
                     "--repo", repo, "--json", "body,comments"],
                    capture_output=True, text=True, timeout=timeout + 10)
                seen_text = proc.stdout if proc.returncode == 0 else ""
            except (OSError, subprocess.TimeoutExpired):
                seen_text = ""
            new_rows = [
                r for r in repo_rows
                if f"| {r.product} | {r.channel} |" not in seen_text]
            if not new_rows:
                messages.append(
                    f"{repo}: skipped, open drift issue "
                    f"#{existing['number']} covers all rows")
                continue
            body_lines = [
                "Update — new drift rows not covered by the original",
                "report:",
                "",
                "| product | channel | local | remote | state |",
                "|---|---|---|---|---|",
            ]
            body_lines += [
                f"| {r.product} | {r.channel} | {r.local} | {r.remote} | {r.state} |"
                for r in new_rows]
            body_lines += ["",
                           f"Detected {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}."]
            try:
                proc = subprocess.run(
                    ["gh", "issue", "comment", str(existing["number"]),
                     "--repo", repo, "--body", "\n".join(body_lines)],
                    capture_output=True, text=True, timeout=timeout + 10,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                messages.append(
                    f"{repo}: issue comment failed: "
                    f"{type(exc).__name__}")
                continue
            if proc.returncode == 0:
                messages.append(
                    f"{repo}: commented {len(new_rows)} new row(s) on "
                    f"drift issue #{existing['number']}")
            else:
                messages.append(
                    f"{repo}: issue comment failed: "
                    f"{(proc.stderr or proc.stdout).strip()[:160]}")
            continue
        subprocess.run(
            ["gh", "label", "create", "drift", "--repo", repo,
             "--description", "Version drift detected by ecosystem_sync.py",
             "--color", "d93f0b", "--force"],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        body_lines = [
            "`tools/ecosystem_sync.py` detected drift between expected and",
            "actual state (versions, CI config, PR merge flow):",
            "",
            "| product | channel | local | remote | state |",
            "|---|---|---|---|---|",
        ]
        body_lines += [
            f"| {r.product} | {r.channel} | {r.local} | {r.remote} | {r.state} |"
            for r in repo_rows
        ]
        body_lines += ["", f"Detected {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}."]
        proc = subprocess.run(
            ["gh", "issue", "create", "--repo", repo, "--label", "drift",
             "--title", title, "--body", "\n".join(body_lines)],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        if proc.returncode == 0:
            messages.append(f"{repo}: opened {proc.stdout.strip()}")
        else:
            messages.append(f"{repo}: issue create failed: "
                            f"{(proc.stderr or proc.stdout).strip()[:160]}")
    return messages


def open_silence_issues(rows: list[Row], timeout: int) -> list[str]:
    """One `silence-alert` issue per silent component, deduped by product name.

    ``rows`` should already be filtered to freshness rows in DRIFT_STATES.
    An open issue whose title already names the component suppresses a new
    one — repeated alerts for the same silence are noise."""
    messages: list[str] = []
    for row in rows:
        repo = row.repo or SILENCE_REPO_PAS
        try:
            proc = subprocess.run(
                ["gh", "issue", "list", "--repo", repo, "--label",
                 SILENCE_LABEL, "--state", "open", "--json", "number,title",
                 "--limit", "50"],
                capture_output=True, text=True, timeout=timeout + 10,
            )
            open_issues = json.loads(proc.stdout) if proc.returncode == 0 else []
        except (OSError, ValueError, subprocess.TimeoutExpired):
            open_issues = []
        existing = next(
            (i for i in open_issues
             if row.product.lower() in str(i.get("title", "")).lower()),
            None,
        )
        if existing:
            messages.append(
                f"{repo}: skipped, open silence issue #{existing['number']} "
                f"covers {row.product}")
            continue
        subprocess.run(
            ["gh", "label", "create", SILENCE_LABEL, "--repo", repo,
             "--description", "Component produced no output within its "
                              "expected interval (ecosystem_sync.py)",
             "--color", "b60205", "--force"],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        title = f"[silence] {row.product}: {row.local} without output"
        body_lines = [
            "`tools/ecosystem_sync.py` freshness sensor: this component is",
            "reachable but has produced no output within its expected",
            "interval — the sensor works, the channel looks dead.",
            "",
            "| component | channel | silent for | threshold | state |",
            "|---|---|---|---|---|",
            f"| {row.product} | {row.channel} | {row.local} | {row.remote} "
            f"| {row.state} |",
            "",
            f"Detected {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}."
            + (f" Probe: {row.note}." if row.note else ""),
        ]
        proc = subprocess.run(
            ["gh", "issue", "create", "--repo", repo, "--label",
             SILENCE_LABEL, "--title", title, "--body",
             "\n".join(body_lines)],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        if proc.returncode == 0:
            messages.append(f"{repo}: opened {proc.stdout.strip()}")
        else:
            messages.append(f"{repo}: silence issue create failed: "
                            f"{(proc.stderr or proc.stdout).strip()[:160]}")
    return messages


def notify_silence_slack(rows: list[Row], roots: list[Path]) -> bool:
    """Best-effort Slack alert for silent components via the PAS notifier.

    Failure is logged to stderr only — a failed notify itself corroborates
    the silence and must never mask the report."""
    notifier: Path | None = None
    for root in roots:
        direct = root / "gateways" / "src" / "slack-notify.js"
        for candidate in [direct, *sorted(root.glob("*/gateways/src/slack-notify.js"))]:
            if candidate.is_file():
                notifier = candidate
                break
        if notifier is not None:
            break
    detail = ", ".join(f"{r.product} silent {r.local}" for r in rows)
    message = f"ecosystem_sync silence-alert: {detail}"
    if notifier is None:
        print("::warning::silence slack notify skipped: no "
              "gateways/src/slack-notify.js under roots", file=sys.stderr)
        return False
    try:
        proc = subprocess.run(
            ["node", str(notifier), message],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"::warning::silence slack notify failed: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    if proc.returncode != 0:
        print(f"::warning::silence slack notify rc={proc.returncode}: "
              f"{(proc.stderr or proc.stdout).strip()[:160]}",
              file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------- remediate
# --remediate: the sensor's first responder is the agent, not the Owner.
# Drift rows become auto_remediate tasks in the qwenpaw queue; the worker's
# handler bridges them to an ACP session which investigates and fixes.
# Slack/issues stay as the audit trail, not the primary signal.

_REMEDIATE_TTL_S = 24 * 3600


def _remediate_state_path() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "devin" / "remediate-sent.json"


def _load_qdispatch(roots: list[Path]):
    """Import scripts/qdispatch.py from a checkout under roots, if any."""
    for root in roots:
        direct = root / "scripts" / "qdispatch.py"
        for script in [direct,
                       *sorted(root.glob("*/scripts/qdispatch.py"))]:
            if not script.is_file():
                continue
            spec = importlib.util.spec_from_file_location(
                "qdispatch", script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


def _load_orchestrator_queue(roots: list[Path]):
    """Import devin_orchestrator.queue_db from a devin-control checkout
    under roots — the laptop-side task-queue.db the remediate-runner
    claims from. Absent on the VM (no devin-control there)."""
    pattern = "packages/orchestrator/src/devin_orchestrator/queue_db.py"
    for root in roots:
        direct = root / "devin-control" / pattern
        for script in [direct, *sorted(root.glob(f"*/{pattern}"))]:
            if not script.is_file():
                continue
            sys.path.insert(0, str(script.parent.parent))
            try:
                import devin_orchestrator.queue_db as queue_db
            except ImportError:
                sys.path.pop(0)
                continue
            return queue_db
    return None


def _failure_class(row: "Row") -> str:
    if row.local == "err streak":
        return "ci_errors"
    if row.channel == "freshness":
        return "silence"
    if row.channel == "pr-merge":
        return "pr_stuck"
    return "version_drift"


def enqueue_remediations(rows: list["Row"], roots: list[Path],
                         now: float | None = None) -> list[str]:
    """One auto_remediate task per drift row with a repo, deduped 24h.

    Preferred sink is the laptop task-queue.db (devin-orchestrator) —
    native dedup via ``idempotency_key = auto_remediate:<repo>:<class>:
    <yyyymmdd>``. When the orchestrator is absent (the freshness cron
    runs on the VM), falls back to the qwenpaw queue: that handler
    relays to the same laptop db over ssh.

    The sensor keeps reporting drift while a fix is in flight — dedup
    prevents re-paging the agent on the same (repo, failure_class) on
    the same day. A submit failure never masks the row; it is logged
    and the next run retries."""
    messages: list[str] = []
    candidates = [r for r in rows if r.state in DRIFT_STATES and r.repo]
    if not candidates:
        return messages
    now = time.time() if now is None else now
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    queue_db = _load_orchestrator_queue(roots)
    state_path = _remediate_state_path()
    sent: dict[str, float] = {}
    qdispatch = None
    if queue_db is None:
        qdispatch = _load_qdispatch(roots)
        if qdispatch is None:
            return ["remediate: neither task-queue.db (orchestrator) "
                    "nor qdispatch.py reachable — nothing enqueued"]
        try:
            if state_path.is_file():
                sent = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sent = {}
    changed = False
    for row in candidates:
        failure_class = _failure_class(row)
        payload = {
            "repo": row.repo,
            "failure_class": failure_class,
            "product": row.product,
            "channel": row.channel,
            "local": row.local,
            "remote": row.remote,
            "state": row.state,
            "detail": row.note,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "source": "ecosystem_sync",
        }
        if queue_db is not None:
            key = f"auto_remediate:{row.repo}:{failure_class}:{day}"
            try:
                con = queue_db.connect(queue_db.default_queue_path())
                try:
                    out = queue_db.submit(
                        con, payload, kind="auto_remediate",
                        repo=row.repo, batch=f"sync-{day}",
                        idempotency_key=key, max_attempts=3)
                finally:
                    con.close()
            except Exception as exc:
                messages.append(
                    f"remediate: {row.repo} queue submit failed: "
                    f"{type(exc).__name__}")
                continue
            if out.get("deduplicated"):
                messages.append(
                    f"remediate: {row.repo} {failure_class} already "
                    f"queued today — dedup")
                continue
            messages.append(
                f"remediate: {row.repo} {failure_class} -> task "
                f"{out.get('id')}")
            continue
        key = f"{row.product}|{row.channel}|{row.repo}"
        last = sent.get(key)
        if isinstance(last, (int, float)) and now - last < _REMEDIATE_TTL_S:
            messages.append(
                f"remediate: {key} enqueued {int(now - last)}s ago — skip")
            continue
        try:
            task_id = qdispatch.submit_task("auto_remediate", payload)
        except Exception as exc:  # queue down — report, retry next run
            messages.append(
                f"remediate: {key} submit failed: {type(exc).__name__}")
            continue
        sent[key] = now
        changed = True
        messages.append(f"remediate: {key} -> task {task_id}")
    if changed:
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(sent), encoding="utf-8")
        except OSError:
            pass
    return messages


# ---------------------------------------------------------------------------
# Runtime registry drift (--runtime)
#
# ``runtime-registry.json`` (PAS repo, read from ``origin/main`` — never the
# shared working tree, which can sit on a feature branch) is the declarative
# inventory of everything that must be running: ~83 components across
# ``laptop``, ``vm-qwenpaw`` and ``github-actions``, each carrying
# ``host``/``deploy``/``deploy_path``/``staleness_policy`` and a
# ``heartbeat {source, key, max_age}``. For every component this sweep
# verifies:
#
#   heartbeat  ``heartbeats.jsonl`` — last ``success`` for ``key`` (the
#              ledger's ``tool`` field) in the host's ledger vs ``max_age``;
#              laptop ledger read locally, VM ledger gathered inside one
#              batched ssh probe. A key found ONLY on the other host's
#              ledger is host drift -> warn.
#              ``pm2`` — process exists in ``pm2 jlist``; ``cron_restart``
#              jobs legitimately sit ``stopped`` between ticks (registry
#              conventions), so freshness is ``pm_uptime`` (last scheduled
#              start) vs ``max_age``; plain daemons must be ``online``.
#              ``cron-log`` — newest evidence wins: a cron-daemon journal
#              ``CMD`` line containing ``key`` (``journalctl -u cron`` on
#              the laptop; the VM has no journald, so VM evidence is the
#              per-job log files only) or a dedicated log file's mtime /
#              key match under ``~/logs`` or beside ``deploy_path``.
#              ``gh-run`` — newest Actions run whose workflow path/name
#              matches ``key``. ``github-actions`` deploys check their own
#              repo; ``github-reusable`` heartbeats live in CALLER repos,
#              so every local checkout carrying a matching
#              ``.github/workflows/*<key>*`` file is scanned too.
#              ``systemd`` — ``is-active``; timer-driven oneshots fall back
#              to the ``.timer``'s ``LastTriggerUSec`` vs ``max_age``
#              (``inactive`` between runs is normal, ``failed`` warns).
#              ``none`` — skip.
#   deploy     ``deploy`` in {git-pull-ff-only, pas-vm-cron, vm-cron,
#              working-tree} and ``deploy_path`` inside a git repo ->
#              ``HEAD`` vs ``origin/main`` (behind/ahead via
#              ``rev-list --count --left-right``). Divergence warns per
#              ``staleness_policy``: ``abort-if-stale``/``alert-if-stale``
#              -> warn, ``accepted`` -> ok-with-note, ``none`` -> skip.
#              VM deploy paths are checked inside the same ssh probe.
#
# Findings are WARN rows — visible in the report and STATE.md but outside
# DRIFT_STATES: runtime drift is ops signal for the Owner, not a repo
# defect for --remediate to patch. An unreachable probe (VM down, gh api
# failure) warns per component, never crashes — fail-open. Only a
# malformed runtime-registry fails the run (rc 2). Designed to run on the
# laptop; on the VM the vm-qwenpaw probes run locally instead of ssh.

RUNTIME_GIT_DEPLOYS = {"git-pull-ff-only", "pas-vm-cron", "vm-cron",
                       "working-tree"}
RUNTIME_VM_HOST = "vm-qwenpaw"
RUNTIME_VM_SSH = "devin-vm"
DEFAULT_PAS_DIR = Path.home() / "devin" / "personal-agent-system"
_LOGICAL_HOSTS = {"laptop", "vm-qwenpaw", "github-actions"}

# Remote probe: gathers every VM-side signal in ONE ssh round-trip so a
# dead VM costs a single timeout, not 24. Reads the whole heartbeat ledger
# (small), ``pm2 jlist``, stat+tail-greps the requested cron log candidates,
# resolves each git deploy dir to HEAD/branch/upstream/behind/ahead, and
# greps the cron journal for the requested keys. Prints one JSON doc.
_VM_PROBE_SCRIPT = r'''
import json, os, subprocess, sys
req = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
res = {"hostname": "", "heartbeats": {}, "pm2": {}, "cron_files": {},
       "git": {}, "cron_journal": {}}
try:
    res["hostname"] = os.uname().nodename
except Exception:
    pass
hb = {}
try:
    with open("/root/.local/state/devin/heartbeats.jsonl",
              encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if not isinstance(e, dict):
                continue
            tool = e.get("tool")
            if not isinstance(tool, str) or not tool.strip():
                continue
            try:
                ts = float(e.get("ts"))
            except Exception:
                continue
            slot = hb.setdefault(tool.strip(), {
                "last_success_at": None, "last_failure_at": None,
                "last_host": None})
            event = str(e.get("event") or "").strip().lower()
            if event == "success" and (slot["last_success_at"] is None
                                       or ts > slot["last_success_at"]):
                slot["last_success_at"] = ts
            elif event == "failure" and (slot["last_failure_at"] is None
                                         or ts > slot["last_failure_at"]):
                slot["last_failure_at"] = ts
            host = e.get("host") or e.get("hostname") or e.get("source_host")
            if host and slot["last_host"] is None:
                slot["last_host"] = str(host)[:80]
except OSError:
    pass
res["heartbeats"] = hb
try:
    proc = subprocess.run(["pm2", "jlist"], capture_output=True, text=True,
                          timeout=30)
    if proc.returncode == 0:
        procs = json.loads(proc.stdout)
        pm = {}
        for item in procs if isinstance(procs, list) else []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            env = item.get("pm2_env") or {}
            pm[str(item["name"])] = {
                "status": env.get("status"),
                "pm_uptime": env.get("pm_uptime"),
                "cron_restart": env.get("cron_restart"),
                "hostname": env.get("hostname"),
            }
        res["pm2"] = pm
except Exception:
    pass
for item in req.get("cron_files") or []:
    if not isinstance(item, (list, tuple)) or len(item) != 2:
        continue
    path, key = str(item[0]), str(item[1])
    try:
        st = os.stat(path)
        ent = {"mtime": float(st.st_mtime), "size": int(st.st_size),
               "key_found": None}
        try:
            with open(path, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 131072))
                tail = fh.read().decode("utf-8", "replace")
            ent["key_found"] = key in tail
        except OSError:
            pass
        res["cron_files"][path] = ent
    except OSError:
        res["cron_files"][path] = None
def _git(dirpath, *args):
    try:
        p = subprocess.run(["git", "-C", dirpath, *args],
                           capture_output=True, text=True, timeout=15)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None
for d in req.get("git_dirs") or []:
    try:
        top = _git(d, "rev-parse", "--show-toplevel")
        if not top:
            continue
        head = _git(top, "rev-parse", "HEAD")
        branch = _git(top, "rev-parse", "--abbrev-ref", "HEAD")
        up = (_git(top, "rev-parse", "--verify", "origin/main")
              or _git(top, "rev-parse", "--verify", "origin/HEAD"))
        behind = ahead = None
        if head and up:
            counts = _git(top, "rev-list", "--count", "--left-right",
                          head + "..." + up)
            if counts:
                parts = counts.split()
                if len(parts) == 2 and all(x.isdigit() for x in parts):
                    ahead, behind = int(parts[0]), int(parts[1])
        res["git"][d] = {"toplevel": top, "head": head, "branch": branch,
                         "upstream": up, "ahead": ahead, "behind": behind}
    except Exception:
        continue
try:
    proc = subprocess.run(
        ["journalctl", "-u", "cron", "--since",
         str(req.get("cron_since") or "45 days ago"),
         "--no-pager", "-o", "short-iso", "-q"],
        capture_output=True, text=True, timeout=40)
    lines = proc.stdout.splitlines() if proc.returncode == 0 else []
except Exception:
    lines = []
hits = {}
for key in req.get("cron_keys") or []:
    newest = None
    for line in lines:
        if "CMD" not in line or key not in line:
            continue
        ts = line[:32]
        if newest is None or ts > newest:
            newest = ts
    hits[key] = newest
res["cron_journal"] = hits
print(json.dumps(res))
'''


def _parse_max_age(value: object) -> float | None:
    """``max_age`` strings (``30min``, ``1h``, ``7d``) -> seconds, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = re.match(
        r"^\s*(\d+(?:\.\d+)?)\s*"
        r"(min|mins|m|h|hr|hrs|d|day|days|w|week|s|sec|secs)?\s*$",
        str(value or "").lower())
    if not match:
        return None
    units = {"s": 1, "sec": 1, "secs": 1, "m": 60, "min": 60, "mins": 60,
             "h": 3600, "hr": 3600, "hrs": 3600, "d": 86400, "day": 86400,
             "days": 86400, "w": 604800, "week": 604800}
    mult = units.get(match.group(2) or "s")
    return float(match.group(1)) * mult if mult else None


def _runtime_registry_text(explicit: str | None, pas_dir: str | None,
                           timeout: int) -> str:
    """Raw runtime-registry.json text.

    Resolution order: explicit path (``--runtime-registry`` /
    ``$RUNTIME_REGISTRY``) -> ``git show origin/main:`` inside the PAS
    checkout (fresh published truth, best-effort fetch first) -> the
    working-tree file as fallback."""
    if explicit:
        return Path(explicit).expanduser().read_text(encoding="utf-8")
    pas = (Path(pas_dir).expanduser() if pas_dir
           else Path(os.environ.get("PAS_DIR") or DEFAULT_PAS_DIR
                     ).expanduser())
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0",
               GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=8")
    try:  # refresh origin/main when possible; the ref alone is acceptable
        subprocess.run(
            ["git", "-C", str(pas), "fetch", "--quiet", "origin", "main"],
            capture_output=True, timeout=min(timeout + 5, 20), env=env)
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        proc = subprocess.run(
            ["git", "-C", str(pas), "show",
             "origin/main:runtime-registry.json"],
            capture_output=True, text=True, timeout=timeout + 5, env=env)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    return (pas / "runtime-registry.json").read_text(encoding="utf-8")


def load_runtime_registry(path: str | None = None,
                          pas_dir: str | None = None,
                          timeout: int = DEFAULT_TIMEOUT) -> dict:
    """runtime-registry.json -> validated dict.

    ``path`` short-circuits resolution (arg or ``$RUNTIME_REGISTRY``);
    otherwise the PAS checkout (``pas_dir`` arg, ``$PAS_DIR`` or
    ``~/devin/personal-agent-system``) is read via ``git show
    origin/main:`` with a working-tree fallback. Raises
    ``ValueError``/``OSError`` on malformed input — the caller maps that
    to rc 2 (the only FAIL this sweep produces)."""
    raw = _runtime_registry_text(
        path or os.environ.get("RUNTIME_REGISTRY"), pas_dir, timeout)
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"runtime-registry.json: invalid JSON: {exc}")
    if not isinstance(data, dict):
        raise ValueError("runtime-registry.json: top level must be an object")
    comps = data.get("components")
    if not isinstance(comps, list) or not comps:
        raise ValueError("runtime-registry.json: 'components' must be a "
                         "non-empty list")
    seen: set[str] = set()
    for i, comp in enumerate(comps):
        if not isinstance(comp, dict):
            raise ValueError(f"runtime-registry.json: components[{i}] "
                             "must be an object")
        name = comp.get("name")
        host = comp.get("host")
        hb = comp.get("heartbeat")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"components[{i}]: 'name' must be a "
                             "non-empty string")
        if not isinstance(host, str) or not host.strip():
            raise ValueError(f"components[{i}] ({name}): 'host' must be a "
                             "non-empty string")
        if name in seen:
            raise ValueError(f"components[{i}]: duplicate name {name!r}")
        seen.add(name)
        if (not isinstance(hb, dict)
                or not isinstance(hb.get("source"), str)
                or not hb["source"].strip()):
            raise ValueError(f"components[{i}] ({name}): "
                             "heartbeat.source must be a non-empty string")
        for field_name in ("deploy", "staleness_policy", "deploy_path"):
            if not isinstance(comp.get(field_name), str):
                raise ValueError(f"components[{i}] ({name}): "
                                 f"'{field_name}' must be a string")
    return data


def _runtime_probe_run(request: dict, timeout: int) -> dict | None:
    """Run ``_VM_PROBE_SCRIPT`` — over ssh to ``devin-vm``, or locally when
    the sync itself runs on the VM (``_this_host() == 'vm'``). ``None`` on
    any transport/parse failure — callers mark components warn, never
    crash."""
    payload = json.dumps(request)
    if _this_host() == "vm":
        cmd = ["python3", "-c", _VM_PROBE_SCRIPT, payload]
    else:
        # ssh joins trailing args with spaces and the REMOTE shell
        # re-parses them — a bare list would shatter the -c script and
        # the JSON payload. Quote each arg for the remote shell and
        # hand ssh one command string.
        remote = " ".join(shlex.quote(a) for a in
                          ["python3", "-c", _VM_PROBE_SCRIPT, payload])
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
               RUNTIME_VM_SSH, remote]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout + 45)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
    return None


def _hb_key(comp: dict) -> str:
    """Heartbeat lookup key: ``heartbeat.key`` else the component name."""
    hb = comp.get("heartbeat") or {}
    key = hb.get("key")
    return str(key).strip() if key else str(comp.get("name") or "")


def _hb_max_age(comp: dict) -> tuple[float | None, str]:
    """(max_age seconds, display) — display ``<=Xh`` via _fmt_threshold."""
    max_age = _parse_max_age((comp.get("heartbeat") or {}).get("max_age"))
    remote = (_fmt_threshold(max_age / 3600.0)
              if max_age else "—")
    return max_age, remote


def _cron_log_candidates(comp: dict, key: str,
                         home: Path) -> list[Path]:
    """Per-job cron log guesses: ``<home>/logs/<key>.log`` plus
    ``<deploy_dir>/logs/<key>.log`` and ``<deploy_dir>/<key>.log`` —
    covers ~/logs (laptop), /root/logs (VM) and bridge-style dirs."""
    cands = [home / "logs" / f"{key}.log"]
    deploy_path = comp.get("deploy_path") or ""
    if deploy_path:
        deploy_dir = Path(deploy_path).expanduser().parent
        cands += [deploy_dir / "logs" / f"{key}.log",
                  deploy_dir / f"{key}.log"]
    out: list[Path] = []
    for cand in cands:
        if cand not in out:
            out.append(cand)
    return out


def _cron_file_entry(path: Path, key: str) -> dict | None:
    """Local cron-log candidate -> {mtime, size, key_found} or None."""
    try:
        st = path.stat()
    except OSError:
        return None
    ent = {"mtime": float(st.st_mtime), "size": int(st.st_size),
           "key_found": None}
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 131072))
            tail = fh.read().decode("utf-8", "replace")
        ent["key_found"] = key in tail
    except OSError:
        pass
    return ent


def _cron_journal_hits(keys: list[str], since_iso: str,
                       timeout: int) -> dict[str, str | None]:
    """{key: newest cron ``CMD`` ISO ts containing key} from the local
    cron journal. Empty dict when journalctl is missing or fails —
    cron-log components then fall back to file evidence alone."""
    if not keys or shutil.which("journalctl") is None:
        return {}
    hits: dict[str, str | None] = {}
    for unit in ("cron", "crond"):
        try:
            proc = subprocess.run(
                ["journalctl", "-u", unit, "--since", since_iso,
                 "--no-pager", "-o", "short-iso", "-q"],
                capture_output=True, text=True, timeout=timeout + 20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            if "CMD" not in line:
                continue
            for key in keys:
                if key in line:
                    ts = line[:32]
                    if hits.get(key) is None or ts > hits[key]:
                        hits[key] = ts
        if hits:
            break
    return hits


def _cron_lookback_iso(comps: list[dict], now: float) -> str:
    """``--since`` ISO for cron journal greps: ~3x the widest max_age,
    floored at 2h past it, capped at 45d."""
    lookbacks = []
    for comp in comps:
        max_age = _parse_max_age((comp.get("heartbeat") or {})
                                 .get("max_age"))
        if max_age:
            lookbacks.append(min(max(3 * max_age, max_age + 7200),
                                 45 * 86400))
    secs = max(lookbacks) if lookbacks else 3 * 86400
    return datetime.fromtimestamp(now - secs,
                                  timezone.utc).isoformat()


def _vm_probe_request(comps: list[dict], now: float) -> dict:
    """Payload for ``_VM_PROBE_SCRIPT``: cron log candidates, git deploy
    dirs and journal keys for every vm-qwenpaw component."""
    cron_files: list[list[str]] = []
    git_dirs: list[str] = []
    cron_keys: list[str] = []
    for comp in comps:
        hb = comp.get("heartbeat") or {}
        if str(hb.get("source") or "") == "cron-log":
            key = _hb_key(comp)
            cron_keys.append(key)
            for cand in _cron_log_candidates(comp, key, Path("/root")):
                pair = [str(cand), key]
                if pair not in cron_files:
                    cron_files.append(pair)
        if (comp.get("deploy") in RUNTIME_GIT_DEPLOYS
                and comp.get("deploy_path")):
            git_dirs.append(str(comp["deploy_path"]))
    return {"cron_files": cron_files,
            "git_dirs": list(dict.fromkeys(git_dirs)),
            "cron_keys": sorted(set(cron_keys)),
            "cron_since": _cron_lookback_iso(comps, now)}


def _runtime_git_state(path: str, timeout: int,
                       cache: dict) -> dict | None:
    """HEAD/branch vs origin/main for the repo containing ``path``.

    No devin-root restriction (unlike ``_cron_repo_root``) — deploy paths
    may live anywhere (``/root/...`` on the VM, ``~/.local/bin`` is NOT a
    repo and simply returns None). Cached per toplevel."""
    cand = Path(path).expanduser()
    probe = cand if cand.is_dir() else cand.parent
    while not probe.is_dir() and probe != probe.parent:
        probe = probe.parent
    if not probe.is_dir():
        return None
    cursor = probe
    top = None
    for _ in range(8):
        proc = _git(cursor, "rev-parse", "--show-toplevel",
                   timeout=timeout)
        if proc is not None and proc.returncode == 0 \
                and proc.stdout.strip():
            top = proc.stdout.strip()
            break
        if cursor == cursor.parent:
            break
        cursor = cursor.parent
    if not top:
        return None
    if top in cache:
        return cache[top]
    state = {"toplevel": top, "head": None, "branch": None,
             "upstream": None, "ahead": None, "behind": None}
    head = _git(top, "rev-parse", "HEAD", timeout=timeout)
    if head is not None and head.returncode == 0:
        state["head"] = head.stdout.strip() or None
    branch = _git(top, "rev-parse", "--abbrev-ref", "HEAD",
                  timeout=timeout)
    if branch is not None and branch.returncode == 0:
        name = branch.stdout.strip()
        state["branch"] = name if name and name != "HEAD" else None
    up = _git(top, "rev-parse", "--verify", "origin/main",
              timeout=timeout)
    if up is None or up.returncode != 0:
        up = _git(top, "rev-parse", "--verify", "origin/HEAD",
                  timeout=timeout)
    if up is not None and up.returncode == 0:
        state["upstream"] = up.stdout.strip() or None
    if state["head"] and state["upstream"]:
        counts = _git(top, "rev-list", "--count", "--left-right",
                      f"{state['head']}...{state['upstream']}",
                      timeout=timeout)
        if counts is not None and counts.returncode == 0:
            parts = counts.stdout.split()
            if len(parts) == 2 and all(x.isdigit() for x in parts):
                # --left-right: left = HEAD-only (ahead), right =
                # upstream-only (behind)
                state["ahead"], state["behind"] = (int(parts[0]),
                                                 int(parts[1]))
    cache[top] = state
    return state


def _deploy_state_row(g: dict, policy: str) -> tuple[str, str]:
    """Git state dict -> (level, summary) per staleness_policy."""
    branch = g.get("branch") or (g.get("head") or "?")[:7]
    behind, ahead = g.get("behind"), g.get("ahead")
    if behind is None or ahead is None:
        return ("warn", f"{branch}: HEAD vs origin/main undetermined")
    if behind == 0 and ahead == 0:
        return ("ok", f"{branch} == origin/main")
    div = ", ".join(p for p in (
        f"{behind} behind" if behind else "",
        f"{ahead} ahead" if ahead else "") if p)
    if policy == "accepted":
        return ("ok", f"{branch}: {div} origin/main "
                      "(staleness accepted)")
    return ("warn", f"{branch}: {div} origin/main ({policy})")


def _runtime_deploy_eval(comp: dict, host: str,
                         ctx: dict) -> tuple[str, str]:
    """Deploy-freshness check -> (level, summary); ``skip``+"" when the
    deploy type is not git-managed or has no staleness concept."""
    deploy = comp.get("deploy") or ""
    policy = comp.get("staleness_policy") or ""
    if deploy not in RUNTIME_GIT_DEPLOYS:
        return ("skip", "")
    if policy == "none":
        return ("skip", "staleness_policy=none")
    path = comp.get("deploy_path") or ""
    if not path:
        return ("skip", "no deploy_path")
    if host == RUNTIME_VM_HOST:
        if ctx["vm"] is None:
            if ctx["offline"]:
                return ("skip", "offline")
            return ("warn", "vm unreachable — deploy state unknown")
        g = (ctx["vm"].get("git") or {}).get(path)
        if g is None:
            return ("skip", "deploy_path not inside a git repo on VM")
        return _deploy_state_row(g, policy)
    if host == "github-actions":
        return ("skip", "github-hosted deploy")
    state = _runtime_git_state(path, ctx["timeout"], ctx["git_cache"])
    if state is None:
        return ("skip", "deploy_path not inside a git repo")
    return _deploy_state_row(state, policy)


def _hb_jsonl_eval(comp: dict, host: str, key: str, max_age: float | None,
                   remote: str, ctx: dict, now: float) -> tuple[str, str, str]:
    """heartbeats.jsonl check -> (level, local, note)."""
    if host == RUNTIME_VM_HOST:
        vm_hb = (ctx["vm"] or {}).get("heartbeats") or {}
        entry = vm_hb.get(key)
        foreign = ctx["laptop_hb"].get(key)
        foreign_host = "laptop"
    elif host == "laptop":
        entry = ctx["laptop_hb"].get(key)
        vm_hb = (ctx["vm"] or {}).get("heartbeats") or {}
        foreign = vm_hb.get(key)
        foreign_host = RUNTIME_VM_HOST
    else:
        entry = foreign = None
        foreign_host = host
    if host == RUNTIME_VM_HOST and ctx["vm"] is None:
        if ctx["offline"]:
            return ("skip", "—", "offline")
        return ("warn", "—", "vm unreachable — heartbeat ledger unknown")
    if entry is None:
        if foreign is not None:
            return ("warn", "never",
                    f"'{key}' only on {foreign_host} ledger — host drift")
        return ("warn", "never", f"no '{key}' heartbeat entries")
    last_ok = entry.get("last_success_at")
    last_fail = entry.get("last_failure_at")
    detail = str(entry.get("last_detail") or "")
    ehost = entry.get("last_host")
    notes: list[str] = []
    level = "ok"
    if last_ok is None:
        level = "warn"
        local = "never"
        if last_fail is not None:
            notes.append(f"only failure events (last "
                         f"{_fmt_age(now - last_fail)} ago)")
        else:
            notes.append("entries without usable timestamps")
    else:
        age = max(0.0, now - last_ok)
        local = _fmt_age(age)
        if max_age and age > max_age:
            level = "warn"
            notes.append(f"stale: last success {local} ago > {remote}")
        else:
            notes.append(f"last success {local} ago")
        if last_fail is not None and last_fail > last_ok:
            level = "warn"
            notes.append(f"err streak: last failure "
                         f"{_fmt_age(now - last_fail)} ago")
    if isinstance(ehost, str) and ehost in _LOGICAL_HOSTS \
            and ehost != host:
        level = "warn"
        notes.append(f"ledger host={ehost} != component host={host}")
    if detail:
        notes.append(detail[:80])
    return (level, local, "; ".join(notes)[:180])


def _local_pm2(timeout: int) -> dict | None:
    """Local ``pm2 jlist`` -> {name: {status, pm_uptime, cron_restart}},
    same shape as the VM probe's ``pm2`` block. None on failure."""
    if shutil.which("pm2") is None:
        return None
    try:
        proc = subprocess.run(["pm2", "jlist"], capture_output=True,
                              text=True, timeout=timeout + 15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        procs = json.loads(proc.stdout)
    except ValueError:
        return None
    out = {}
    for item in procs if isinstance(procs, list) else []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        env = item.get("pm2_env") or {}
        out[str(item["name"])] = {
            "status": env.get("status"),
            "pm_uptime": env.get("pm_uptime"),
            "cron_restart": env.get("cron_restart"),
            "hostname": env.get("hostname"),
        }
    return out


def _pm2_uptime_seconds(proc: dict) -> float | None:
    """``pm_uptime`` is ms epoch (tolerate s) -> epoch seconds."""
    up = proc.get("pm_uptime")
    if not isinstance(up, (int, float)) or isinstance(up, bool):
        return None
    return up / 1000.0 if up > 1e12 else float(up)


def _hb_pm2_eval(comp: dict, host: str, key: str, max_age: float | None,
                 remote: str, ctx: dict, now: float) -> tuple[str, str, str]:
    """pm2 check -> (level, local, note)."""
    if host == RUNTIME_VM_HOST:
        if ctx["vm"] is None:
            if ctx["offline"]:
                return ("skip", "—", "offline")
            return ("warn", "—", "vm unreachable — pm2 state unknown")
        procs = ctx["vm"].get("pm2") or {}
    else:
        if ctx["local_pm2"] is None:
            ctx["local_pm2"] = _local_pm2(ctx["timeout"])
        if ctx["local_pm2"] is None:
            return ("warn", "—", "pm2 probe unavailable on this host")
        procs = ctx["local_pm2"]
    proc = procs.get(key)
    if proc is None:
        return ("warn", "absent", f"'{key}' not in pm2")
    status = str(proc.get("status") or "unknown")
    cron = proc.get("cron_restart")
    up_s = _pm2_uptime_seconds(proc)
    if cron:
        # cron_restart jobs sit 'stopped' between ticks by design —
        # freshness is the last scheduled start (pm_uptime) vs max_age.
        if up_s and max_age:
            age = max(0.0, now - up_s)
            if age > max_age:
                return ("warn", _fmt_age(age),
                        f"cron_restart '{cron}' last start "
                        f"{_fmt_age(age)} ago > {remote} "
                        f"(status={status})")
            return ("ok", _fmt_age(age),
                    f"cron_restart '{cron}' (status={status})")
        return ("ok", "present",
                f"cron_restart '{cron}' (status={status})")
    if status == "online":
        upnote = (f", up {_fmt_age(now - up_s)}" if up_s else "")
        return ("ok", "online", f"pm2 online{upnote}")
    return ("warn", status, f"pm2 status={status}")


def _hb_cronlog_eval(comp: dict, host: str, key: str,
                     max_age: float | None, remote: str, ctx: dict,
                     now: float) -> tuple[str, str, str]:
    """cron-log check -> (level, local, note)."""
    candidates = _cron_log_candidates(
        comp, key, Path("/root") if host == RUNTIME_VM_HOST
        else ctx["home"])
    journal_ts: str | None = None
    file_entries: list[tuple[Path, dict | None]] = []
    if host == RUNTIME_VM_HOST:
        if ctx["vm"] is None:
            if ctx["offline"]:
                return ("skip", "—", "offline")
            return ("warn", "—",
                    "vm unreachable — cron log state unknown")
        journal_ts = (ctx["vm"].get("cron_journal") or {}).get(key)
        vm_files = ctx["vm"].get("cron_files") or {}
        file_entries = [(c, vm_files.get(str(c))) for c in candidates]
    elif host == "laptop":
        journal_ts = (ctx["journal"] or {}).get(key)
        file_entries = [(c, _cron_file_entry(c, key)) for c in candidates]
    else:
        return ("skip", "—", "cron-log n/a on this host")
    evidence: list[float] = []
    jepoch = _parse_timestamp(journal_ts) if journal_ts else None
    if jepoch is not None:
        evidence.append(jepoch)
    for path, ent in file_entries:
        if not ent:
            continue
        mtime = ent.get("mtime")
        if not mtime:
            continue
        dedicated = path.name == f"{key}.log" or key in path.name
        if dedicated or ent.get("key_found"):
            evidence.append(float(mtime))
    if not evidence:
        return ("warn", "never",
                f"no cron-log evidence for '{key}' "
                "(journal + log files)")
    newest = max(evidence)
    age = max(0.0, now - newest)
    local = _fmt_age(age)
    if max_age and age > max_age:
        return ("warn", local,
                f"last cron-log activity {local} ago > {remote}")
    return ("ok", local, f"last cron-log activity {local} ago")


def _systemctl_is_active(base: list[str], unit: str,
                         timeout: int) -> str:
    """``systemctl [--user] is-active <unit>`` -> state string."""
    if shutil.which("systemctl") is None:
        return "n/a"
    try:
        proc = subprocess.run(base + ["is-active", unit],
                              capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return "error"
    return proc.stdout.strip() or "unknown"


def _timer_last_trigger(base: list[str], timer: str,
                        timeout: int) -> float | None:
    """``LastTriggerUSec`` of a .timer -> epoch seconds.

    systemctl renders it humanized (``Wed 2026-11-11 05:30:01 WET``) in
    LOCAL time — the datetime part is parsed and interpreted as local."""
    try:
        proc = subprocess.run(base + ["show", timer, "-p",
                                      "LastTriggerUSec"],
                              capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
                      proc.stdout)
    if not match:
        return None
    try:
        dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt.replace(
        tzinfo=datetime.now().astimezone().tzinfo).timestamp()


def _hb_systemd_eval(comp: dict, host: str, key: str,
                     max_age: float | None, remote: str, ctx: dict,
                     now: float) -> tuple[str, str, str]:
    """systemd check -> (level, local, note)."""
    if host != "laptop":
        return ("skip", "—", "systemd check is laptop-local")
    system = (comp.get("deploy") or "") == "systemd-system"
    base = ["systemctl"] + ([] if system else ["--user"])
    state = _systemctl_is_active(base, key, ctx["timeout"])
    if state == "n/a":
        return ("warn", "—", "systemctl unavailable")
    if state == "active":
        return ("ok", "active", f"systemd {key} active")
    # Oneshot/timer units sit 'inactive' between runs — the .timer's last
    # trigger is the real heartbeat.
    timer = (re.sub(r"\.(service|timer|socket)$", ".timer", key)
             if key.endswith((".service", ".timer", ".socket"))
             else key + ".timer")
    tstate = (_systemctl_is_active(base, timer, ctx["timeout"])
              if timer != key else "unknown")
    if tstate == "active":
        last = _timer_last_trigger(base, timer, ctx["timeout"])
        if last is not None and max_age:
            age = max(0.0, now - last)
            if age <= max_age:
                if state == "failed":
                    return ("warn", "failed",
                            f"timer-driven; last trigger "
                            f"{_fmt_age(age)} ago but {key} "
                            "state=failed")
                return ("ok", "timer",
                        f"timer-driven; last trigger "
                        f"{_fmt_age(age)} ago")
            return ("warn", _fmt_age(age),
                    f"timer stale: last trigger {_fmt_age(age)} ago "
                    f"> {remote}")
        if state == "failed":
            return ("warn", "failed",
                    f"{key} state=failed (timer active, "
                    "trigger unknown)")
        return ("ok", "timer",
                "timer-driven unit; last trigger unknown")
    return ("warn", state,
            f"systemd {key} state={state or 'unknown'}")


def _repo_for_deploy_path(deploy_path: str, roots: list[Path],
                          owners: dict[str, str]
                          ) -> tuple[str, str] | None:
    """(owner, name) of the git repo containing ``deploy_path``.

    Walks the path relative to each root and keeps the DEEPEST dir with a
    ``.git`` — deploy_path's own repo, not an ancestor container."""
    try:
        p = Path(deploy_path).expanduser().resolve()
    except OSError:
        return None
    for root in roots:
        try:
            root_r = Path(root).expanduser().resolve()
            rel = p.relative_to(root_r)
        except (OSError, ValueError):
            continue
        cur = root_r
        found = None
        for part in rel.parts:
            cur = cur / part
            if (cur / ".git").exists():
                found = cur
        if found is not None:
            return (owners.get(found.name, "Icaro0310"), found.name)
    return None


def _local_workflow_files(repo_name: str, key: str,
                          roots: list[Path]) -> list[str]:
    """Workflow file names under any local checkout of ``repo_name``
    whose stem matches ``key`` — same exact/bounded-suffix rule as
    ``_wf_key_match``. ``release-qa-pack`` does NOT match key
    ``release``; ``ai-review-fallback`` DOES match ``review-fallback``."""
    k = key.lower()
    found: set[str] = set()
    for root in roots:
        wf_dir = Path(root) / repo_name / ".github" / "workflows"
        try:
            if not wf_dir.is_dir():
                continue
            for f in wf_dir.iterdir():
                if f.suffix not in (".yml", ".yaml"):
                    continue
                stem = f.stem.lower()
                if stem == k or (len(stem) > len(k)
                                 and stem.endswith(k)
                                 and stem[-len(k) - 1] in "-_ "):
                    found.add(f.name)
        except OSError:
            continue
    return sorted(found)


def _fleet_workflow_repos(key: str, roots: list[Path],
                          owners: dict[str, str],
                          deploy_repo: tuple[str, str] | None
                          ) -> list[tuple[str, str]]:
    """Repos to scan for ``<key>`` runs: the deploy repo plus every known
    checkout carrying a matching caller workflow — reusable-workflow
    heartbeats live in callers, not in the reusable's own repo."""
    repos: dict[str, tuple[str, str]] = {}
    if deploy_repo is not None:
        repos[deploy_repo[1]] = deploy_repo
    for name in sorted(set(owners) | set(EXTRA_REPOS)):
        if name in repos:
            continue
        if _local_workflow_files(name, key, roots):
            repos[name] = (owners.get(name, "Icaro0310"), name)
    return sorted(repos.values())


def _wf_key_match(run: dict, key: str) -> bool:
    """Workflow path-stem or display name matches ``key`` — exact, or a
    ``-``/``_``/space-bounded suffix (``ai-review-fallback`` matches
    ``review-fallback``, ``registry-refresh`` matches its ``(weekly)``
    display name via the path stem)."""
    k = key.lower()
    stem = Path(str(run.get("path") or "")).stem.lower()
    name = str(run.get("name") or "").lower()
    for cand in (stem, name):
        if not cand:
            continue
        if cand == k:
            return True
        if len(cand) > len(k) and cand.endswith(k) \
                and cand[-len(k) - 1] in "-_ ":
            return True
    return False


def _gh_workflow_file_runs(owner: str, name: str, wf_file: str,
                           timeout: int,
                           cache: dict) -> list | None:
    """Recent runs of ONE workflow file, newest first (cached per
    repo+file). ``/actions/runs?per_page=100`` is unusable here: PR-bot
    workflows flood the page and scheduled jobs fall outside it — the
    per-workflow endpoint is the only precise source. ``[]`` when the
    workflow does not exist (404) or has no runs; ``None`` on gh
    failure."""
    k = (owner, name, wf_file)
    if k in cache:
        return cache[k]
    quoted = urllib.parse.quote(wf_file, safe="")
    try:
        data = _gh_api(owner, name,
                       f"/actions/workflows/{quoted}/runs?per_page=5",
                       timeout)
        runs = data.get("workflow_runs") if isinstance(data, dict) \
            else None
        cache[k] = runs if isinstance(runs, list) else []
    except Exception as exc:
        msg = str(exc)
        cache[k] = [] if ("404" in msg or "Not Found" in msg) else None
    return cache[k]


def _hb_ghrun_eval(comp: dict, key: str, max_age: float | None,
                   remote: str, ctx: dict, now: float) -> tuple[str, str, str]:
    """gh-run check -> (level, local, note).

    Targets are (owner, repo, workflow_file) triples discovered from
    LOCAL checkouts: ``github-actions`` deploys point at their own
    workflow file (``deploy_path`` basename); ``github-reusable``
    heartbeats live in CALLER workflows, so every checkout carrying a
    ``*<key>*`` file contributes its matching files."""
    if ctx["offline"]:
        return ("skip", "—", "offline")
    deploy = comp.get("deploy") or ""
    deploy_path = comp.get("deploy_path") or ""
    deploy_repo = _repo_for_deploy_path(deploy_path, ctx["roots"],
                                        ctx["owners"])
    targets: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(repo: tuple[str, str] | None, wf_file: str | None) -> None:
        if repo is None or not wf_file:
            return
        t = (repo[0], repo[1], wf_file)
        if t not in seen:
            seen.add(t)
            targets.append(t)

    def add_fleet() -> None:
        for owner, name in _fleet_workflow_repos(
                key, ctx["roots"], ctx["owners"], deploy_repo):
            for wf in _local_workflow_files(name, key, ctx["roots"]):
                add((owner, name), wf)

    if deploy == "github-actions" and deploy_repo is not None:
        base = Path(deploy_path).name
        if base.endswith((".yml", ".yaml")):
            add(deploy_repo, base)
        if not targets:
            add_fleet()
    else:
        add_fleet()
    if not targets:
        return ("warn", "—",
                f"cannot map '{key}' to any workflow")
    newest: tuple[float, str, dict] | None = None
    failures = 0
    checked = 0
    for owner, name, wf_file in targets:
        runs = _gh_workflow_file_runs(owner, name, wf_file,
                                      ctx["timeout"], ctx["gh_cache"])
        if runs is None:
            failures += 1
            continue
        checked += 1
        for run in runs:
            if not isinstance(run, dict) or not _wf_key_match(run, key):
                continue
            ts = _parse_timestamp(run.get("created_at"))
            if ts is None:
                continue
            if newest is None or ts > newest[0]:
                newest = (ts, f"{owner}/{name}:{wf_file}", run)
    if newest is None:
        if checked == 0 and failures:
            return ("warn", "—",
                    "gh api unreachable for all candidate repos")
        return ("warn", "never",
                f"no '{key}' workflow runs in last 5 runs/workflow")
    ts, where, run = newest
    age = max(0.0, now - ts)
    local = _fmt_age(age)
    concl = str(run.get("conclusion") or run.get("status") or "")
    if max_age and age > max_age:
        return ("warn", local,
                f"last '{key}' run {local} ago > {remote} "
                f"({where}{', ' + concl if concl else ''})")
    return ("ok", local,
            f"last '{key}' run {local} ago "
            f"({where}{', ' + concl if concl else ''})")


def _runtime_component_row(comp: dict, ctx: dict) -> Row:
    """One runtime Row per registry component (channel ``runtime``)."""
    name = str(comp.get("name") or "?")
    host = str(comp.get("host") or "")
    hb = comp.get("heartbeat") or {}
    source = str(hb.get("source") or "").strip()
    key = _hb_key(comp)
    max_age, remote = _hb_max_age(comp)
    now = ctx["now"]
    findings: list[tuple[str, str]] = []
    local = "—"

    foreign = host == "laptop" and _this_host() == "vm"
    if host not in _LOGICAL_HOSTS:
        findings.append(("warn", f"unrecognized host {host!r}"))
    elif foreign:
        # Running on the VM: laptop-side probes (systemctl --user,
        # local pm2, ~/logs, local git checkouts) would read the WRONG
        # host — skip the component entirely, one skip row says why.
        findings.append(("skip", "foreign host — run on laptop"))

    if not foreign:
        if source in ("", "none"):
            findings.append(("skip", "heartbeat.source=none"))
        elif source == "heartbeats.jsonl":
            lvl, local, note = _hb_jsonl_eval(comp, host, key, max_age,
                                              remote, ctx, now)
            findings.append((lvl, f"heartbeat: {note}"))
        elif source == "pm2":
            lvl, local, note = _hb_pm2_eval(comp, host, key, max_age,
                                            remote, ctx, now)
            findings.append((lvl, f"heartbeat: {note}"))
        elif source == "cron-log":
            lvl, local, note = _hb_cronlog_eval(comp, host, key, max_age,
                                                remote, ctx, now)
            findings.append((lvl, f"heartbeat: {note}"))
        elif source == "gh-run":
            lvl, local, note = _hb_ghrun_eval(comp, key, max_age, remote,
                                              ctx, now)
            findings.append((lvl, f"heartbeat: {note}"))
        elif source == "systemd":
            lvl, local, note = _hb_systemd_eval(comp, host, key, max_age,
                                                remote, ctx, now)
            findings.append((lvl, f"heartbeat: {note}"))
        else:
            findings.append(("warn",
                             f"unknown heartbeat.source {source!r}"))

        lvl, summary = _runtime_deploy_eval(comp, host, ctx)
        if lvl != "skip" or summary:
            findings.append((lvl, f"deploy: {summary or 'n/a'}"))

    if any(l == "warn" for l, _ in findings):
        state = "warn"
    elif any(l == "ok" for l, _ in findings):
        state = "ok"
    else:
        state = "skip"
    note = "; ".join(t for _, t in findings if t)[:220]
    return Row(name, "runtime", local, remote, state, "", note)


def collect_runtime(registry: dict, owners: dict[str, str],
                    roots: list[Path], timeout: int = DEFAULT_TIMEOUT,
                    now: float | None = None, offline: bool = False,
                    home: Path | None = None,
                    vm_probe=None) -> list[Row]:
    """Runtime-registry drift rows — one per component, channel
    ``runtime``.

    ``registry`` is the validated dict from ``load_runtime_registry()``;
    ``owners`` maps repo name -> owner (same shape the other collectors
    take) for gh-run repo resolution; ``now`` is injectable epoch seconds
    for tests; ``vm_probe`` is injectable ``(request, timeout) ->
    dict | None`` replacing the ssh/local probe."""
    now = time.time() if now is None else now
    home_path = (Path(home).expanduser() if home is not None
                 else Path.home())
    components = [c for c in (registry.get("components") or [])
                  if isinstance(c, dict)]
    on_vm = _this_host() == "vm"
    ctx: dict = {
        "now": now, "timeout": timeout, "offline": offline,
        "roots": roots, "owners": owners, "home": home_path,
        "git_cache": {}, "gh_cache": {}, "journal": {},
        "laptop_hb": {}, "vm": None, "local_pm2": None,
    }
    vm_comps = [c for c in components
                if c.get("host") == RUNTIME_VM_HOST]
    # The VM probe also serves host-drift detection for LAPTOP
    # heartbeats.jsonl components (a key found only on the VM ledger
    # means the component migrated hosts) — one batched ssh call either
    # way, so probe whenever either side needs it.
    needs_vm_probe = bool(vm_comps) or any(
        c.get("host") == "laptop"
        and str((c.get("heartbeat") or {}).get("source") or "")
            == "heartbeats.jsonl"
        for c in components)
    if needs_vm_probe and not offline:
        request = _vm_probe_request(vm_comps, now)
        probe = vm_probe or _runtime_probe_run
        ctx["vm"] = probe(request, timeout)
    laptop_comps = [c for c in components
                    if c.get("host") == "laptop" and not on_vm]
    # Load the laptop ledger whenever ANY heartbeats.jsonl component
    # exists — VM components also consult it for host-drift detection.
    if not on_vm and any(
            str((c.get("heartbeat") or {}).get("source") or "")
            == "heartbeats.jsonl" for c in components):
        ctx["laptop_hb"] = _read_heartbeats()
    cron_keys = sorted({_hb_key(c) for c in laptop_comps
                        if str((c.get("heartbeat") or {})
                               .get("source") or "") == "cron-log"})
    if cron_keys:
        cron_comps = [c for c in laptop_comps
                      if str((c.get("heartbeat") or {})
                             .get("source") or "") == "cron-log"]
        ctx["journal"] = _cron_journal_hits(
            cron_keys, _cron_lookback_iso(cron_comps, now), timeout)
    return [_runtime_component_row(comp, ctx) for comp in components]


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", default=str(HUB / "registry.json"))
    parser.add_argument(
        "--ecosystem-root",
        default=os.environ.get("ECOSYSTEM_ROOT", str(Path.home() / "devin" / "devin-ecosystem")),
        help="directory holding the local repo checkouts (env ECOSYSTEM_ROOT)",
    )
    parser.add_argument(
        "--extra-root", action="append", default=[],
        help="extra checkout root to search after --ecosystem-root "
             "(default also tries ~/devin)",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--offline", action="store_true",
                        help="local scan only; external channels are marked skip")
    parser.add_argument("--issue", action="store_true",
                        help="open a deduplicated 'drift' GitHub issue per affected repo")
    parser.add_argument("--no-silence-alerts", action="store_true",
                        help="with --issue: skip silence-alert issues and the "
                             "slack notify for stale freshness sensors")
    parser.add_argument("--freshness", action="store_true",
                        help="silence-sensor sweep only: skip version/channel "
                             "probes, run freshness rows + health + alerts "
                             "(cheap enough for hourly cron)")
    parser.add_argument("--runtime", action="store_true",
                        help="runtime-registry sweep only: skip "
                             "version/channel probes and the freshness "
                             "sweep, check runtime-registry.json "
                             "components (heartbeat/host/deploy drift) "
                             "+ health; combine with --freshness for "
                             "both sweeps")
    parser.add_argument("--runtime-registry", metavar="PATH",
                        help="runtime-registry.json path (default: "
                             "$RUNTIME_REGISTRY, else git show "
                             "origin/main:runtime-registry.json in the "
                             "PAS checkout — $PAS_DIR or "
                             "~/devin/personal-agent-system — with "
                             "working-tree fallback)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--state-md", metavar="PATH",
                        help="write a markdown state snapshot (agent push-memory)")
    parser.add_argument("--remediate", action="store_true",
                        help="enqueue an auto_remediate task per drift row "
                             "(agent is first responder; deduped 24h)")
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error("--timeout must be a positive integer")

    roots = [Path(args.ecosystem_root).expanduser()]
    extra = [Path(p).expanduser() for p in args.extra_root]
    default_extra = Path.home() / "devin"
    if default_extra not in roots:
        extra.append(default_extra)
    roots += [r for r in extra if r not in roots]

    try:
        entries = load_products(Path(args.registry))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"::error::registry problem: {exc}", file=sys.stderr)
        return 2

    sweep = args.freshness or args.runtime
    repo_names = {_repo_basename(e["url"])[1] for e in entries}
    products = [] if sweep else resolve_products(entries, roots)
    extensions = [] if sweep else scan_vscode_extensions(roots, repo_names)

    website_html: str | None = None
    if not args.offline and not sweep:
        try:
            website_html = fetch_website(args.timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"::warning::website fetch failed: {exc}", file=sys.stderr)

    rows = [] if sweep else build_rows(
        products, extensions, website_html,
        timeout=args.timeout, offline=args.offline)
    owners = {name: owner for owner, name in
              (_repo_basename(e["url"]) for e in entries)}
    if not args.offline:
        if not sweep:
            rows += collect_ci_config({**owners, **EXTRA_REPOS}, args.timeout)
            rows += collect_repo_settings({**owners, **EXTRA_REPOS},
                                          args.timeout)
        # pr-merge + the freshness sweep run in full mode and --freshness;
        # a runtime-only sweep skips them — compose --freshness --runtime
        # for both. They stay out of --runtime so the sweep stays cheap
        # and focused on the registry.
        if args.freshness or not args.runtime:
            # pr-merge runs in BOTH modes: the hourly --freshness sweeps
            # are the only automated callers, so gating it behind the
            # full sync would leave stuck approved PRs unsensed. ~1 gh
            # call per repo, same cost class as the freshness roll-up.
            rows += collect_pr_ready_not_merged({**owners, **EXTRA_REPOS},
                                                args.timeout)
            rows += collect_freshness(roots, {**owners, **EXTRA_REPOS},
                                      args.timeout)
    if args.runtime:
        # Runs even under --offline: local probes (ledgers, systemd, git,
        # cron journal) still work; ssh/gh parts self-skip inside.
        try:
            runtime_registry = load_runtime_registry(
                args.runtime_registry, timeout=args.timeout)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"::error::runtime registry problem: {exc}",
                  file=sys.stderr)
            return 2
        rows += collect_runtime(runtime_registry,
                                {**owners, **EXTRA_REPOS}, roots,
                                timeout=args.timeout,
                                offline=args.offline)
    # cron_branch_stale is pure-local (crontab -l + git) — like a health
    # probe it runs in every mode, including --freshness and --offline.
    rows += collect_cron_branch_stale(timeout=args.timeout)
    health = [] if args.offline else collect_health(roots, args.timeout)

    if args.json:
        print(json.dumps(
            {
                "generated": datetime.now(timezone.utc).isoformat(),
                "rows": [r.__dict__ for r in rows],
                "health": [{"name": n, "status": s} for n, s in health],
            },
            indent=2,
        ))
    else:
        print(render_report(rows, health, roots, datetime.now(timezone.utc)))

    generated = datetime.now(timezone.utc)
    if args.state_md:
        prs = collect_open_prs(owners, args.timeout)
        write_state_md(Path(args.state_md).expanduser(), rows, health, prs, generated)

    drift_rows = [r for r in rows if r.state in DRIFT_STATES]
    if args.issue:
        version_drift = [r for r in drift_rows if r.channel != "freshness"]
        for message in open_drift_issues(version_drift, args.timeout):
            print(f"issue: {message}")
        silence_rows = [r for r in drift_rows if r.channel == "freshness"]
        if silence_rows and not args.no_silence_alerts:
            for message in open_silence_issues(silence_rows, args.timeout):
                print(f"silence: {message}")
            notify_silence_slack(silence_rows, roots)
    if args.remediate:
        for message in enqueue_remediations(drift_rows, roots):
            print(message)
    return 1 if drift_rows else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)

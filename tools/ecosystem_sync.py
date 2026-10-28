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

Usage:
    python tools/ecosystem_sync.py [--registry registry.json]
                                   [--ecosystem-root ~/devin/devin-ecosystem]
                                   [--timeout 10] [--offline] [--json]
                                   [--issue] [--no-silence-alerts]

Without --issue the report is printed and the exit code is 1 when any drift
is found (0 otherwise). With --issue, one GitHub Issue labeled ``drift`` is
opened per affected physical repo, deduplicated against open ``drift``
issues first.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
    """systemctl --user is-active <unit>; 'skip' when the unit is absent."""
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
    checks.append(("ollama (via devin-vm)", "ok" if failure is None else f"DAEMON-DOWN {failure}"))
    failure = check_slack_auth(roots or [], timeout)
    checks.append(("slack auth.test", "ok" if failure is None else f"DAEMON-DOWN {failure}"))
    for unit in SYSTEMD_USER_UNITS:
        state = systemd_unit_state(unit)
        if state == "skip":
            checks.append((unit, "skip (unit absent)"))
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
            matrix[tool.strip()] = {
                "threshold_h": threshold_h,
                "repo": str(cfg.get("repo") or SILENCE_REPO_PAS),
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
        title = f"ecosystem_sync: version drift detected in {repo.split('/')[-1]}"
        existing = next(
            (i for i in open_issues if "drift" in str(i.get("title", "")).lower()),
            None,
        )
        if existing:
            messages.append(f"{repo}: skipped, open drift issue #{existing['number']} exists")
            continue
        subprocess.run(
            ["gh", "label", "create", "drift", "--repo", repo,
             "--description", "Version drift detected by ecosystem_sync.py",
             "--color", "d93f0b", "--force"],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        body_lines = [
            "`tools/ecosystem_sync.py` detected version drift between local",
            "manifests and published channels:",
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


def main(argv: list[str] | None = None) -> int:
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
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--state-md", metavar="PATH",
                        help="write a markdown state snapshot (agent push-memory)")
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

    repo_names = {_repo_basename(e["url"])[1] for e in entries}
    products = [] if args.freshness else resolve_products(entries, roots)
    extensions = [] if args.freshness else scan_vscode_extensions(roots, repo_names)

    website_html: str | None = None
    if not args.offline and not args.freshness:
        try:
            website_html = fetch_website(args.timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"::warning::website fetch failed: {exc}", file=sys.stderr)

    rows = [] if args.freshness else build_rows(
        products, extensions, website_html,
        timeout=args.timeout, offline=args.offline)
    owners = {name: owner for owner, name in
              (_repo_basename(e["url"]) for e in entries)}
    if not args.offline:
        if not args.freshness:
            rows += collect_ci_config({**owners, **EXTRA_REPOS}, args.timeout)
        rows += collect_freshness(roots, {**owners, **EXTRA_REPOS},
                                  args.timeout)
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
        write_state_md(Path(args.state_md), rows, health, prs, generated)

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
    return 1 if drift_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())

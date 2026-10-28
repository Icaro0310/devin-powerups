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

Usage:
    python tools/ecosystem_sync.py [--registry registry.json]
                                   [--ecosystem-root ~/devin/devin-ecosystem]
                                   [--timeout 10] [--offline] [--json]
                                   [--issue]

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
import subprocess
import sys
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


def collect_health() -> list[tuple[str, str]]:
    """Daemon probes -> [(name, status)]; failures read DAEMON-DOWN."""
    checks: list[tuple[str, str]] = []
    failure = check_daemon(HEALTHZ_URL)
    checks.append(("mcp-hub/office healthz", "ok" if failure is None else f"DAEMON-DOWN {failure}"))
    failure = check_ollama_via_vm()
    checks.append(("ollama (via devin-vm)", "ok" if failure is None else f"DAEMON-DOWN {failure}"))
    for unit in SYSTEMD_USER_UNITS:
        state = systemd_unit_state(unit)
        if state == "skip":
            checks.append((unit, "skip (unit absent)"))
        elif state == "active":
            checks.append((unit, "ok"))
        else:
            checks.append((unit, f"DAEMON-DOWN is-active={state}"))
    return checks


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
    parser.add_argument("--json", action="store_true", help="machine-readable output")
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
    products = resolve_products(entries, roots)
    extensions = scan_vscode_extensions(roots, repo_names)

    website_html: str | None = None
    if not args.offline:
        try:
            website_html = fetch_website(args.timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"::warning::website fetch failed: {exc}", file=sys.stderr)

    rows = build_rows(products, extensions, website_html,
                      timeout=args.timeout, offline=args.offline)
    health = [] if args.offline else collect_health()

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

    drift_rows = [r for r in rows if r.state in DRIFT_STATES]
    if args.issue:
        for message in open_drift_issues(drift_rows, args.timeout):
            print(f"issue: {message}")
    return 1 if drift_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())

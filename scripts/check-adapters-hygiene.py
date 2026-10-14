#!/usr/bin/env python3
"""Check that distributed adapter files do not leak internals or drift
from their package's public contract.

secrets-scan catches literal token values anywhere in the tree; this
sensor covers the rest of the failure class for the files we ship to
end users — SKILL.md manifests, plugin.json manifests, VS Code
extensions, daemon units and pre-commit hooks:

* forbidden patterns — personal paths (``/home/<user>``,
  ``/Users/<user>``, ``C:\\Users``, ``Utilizador``), internal
  host/port literals in non-doc files, internal project names and
  token-shaped values that secrets-scan also greps;
* command coherence — every ``devin-*`` token used as a CLI invocation
  inside ``adapters/**/SKILL.md`` must resolve against the owning
  package: present in ``pyproject.toml`` ``[project.scripts]`` or
  documented in the package ``README.md``. A skill that promises a
  command the package does not ship is a lie at the boundary.

Scan roots are explicit (no recursive ``**/adapters`` — vendored or
nested checkouts under the root are never scanned):

* ``adapters/``                       (repo-root adapter dir)
* ``packages/*/adapters/``            (per-package adapter dir)
* ``.devin/skills/``                  (repo-level distributed skills)
* ``packages/*/.devin/skills/``       (per-package distributed skills)

Doc files (``.md``/``.rst``/``.txt``/``.markdown``) are exempt from the
loopback ``host:port`` rules only — a daemon README documenting the
product's own ``127.0.0.1:8788`` bind is the public contract, not a
leak. Every other rule applies to every file.

Known-legitimate hits are pinned per file in a repo-root
``.adapters-hygiene-allow`` (one ``path sha256=<hex>`` line each, ``#``
comments allowed) — the same mechanism as ``.secrets-scan-allow``: the
hash pin means editing an allowlisted file re-triggers the scan, and a
malformed entry (no ``sha256=``) never allows anything. The allowlist
suppresses forbidden-pattern findings only; command coherence is a
contract check and cannot be allowlisted away.

Usage:
    python3 scripts/check-adapters-hygiene.py [--root <repo-root>]
    python3 scripts/check-adapters-hygiene.py --selftest

Exit code is non-zero when any check fails. When no adapter/skill dirs
exist the script prints a notice and exits 0.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tempfile
import tomllib
from pathlib import Path

ALLOWLIST = ".adapters-hygiene-allow"

# Directory names that are never scanned even if they sit inside a scan
# root — build/cache output is not a distributed file.
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "dist", "build", ".venv"}

DOC_SUFFIXES = {".md", ".markdown", ".rst", ".txt"}

# (rule-name, compiled regex, applies-to) — applies-to is "all" files or
# "non-doc" files only. Keep pattern names stable: they appear in the
# failure report and in allowlist comments.
FORBIDDEN: list[tuple[str, re.Pattern[str], str]] = [
    # Personal paths — the author's home dir is never part of the
    # product's contract.
    ("personal-path/home", re.compile(r"/home/\w+"), "all"),
    ("personal-path/users", re.compile(r"/Users/\w+"), "all"),
    ("personal-path/cusers", re.compile(r"C:\\{1,2}Users"), "all"),
    ("personal-path/utilizador", re.compile(r"Utilizador"), "all"),
    # Internal host:port literals — an internal endpoint is a leak when
    # it lands in a shipped config or executable file. Docs are exempt:
    # a README documenting the daemon's own loopback bind describes the
    # product, not the author's machine.
    ("internal-endpoint/loopback", re.compile(r"127\.0\.0\.1:\d+"), "non-doc"),
    ("internal-endpoint/localhost", re.compile(r"localhost:\d+"), "non-doc"),
    ("internal-endpoint/wildcard", re.compile(r"0\.0\.0\.0:\d+"), "non-doc"),
    # Internal project names — private tooling must not leak into
    # distributed surfaces.
    ("internal-name/pw-gsc", re.compile(r"pw-gsc"), "all"),
    ("internal-name/gateways", re.compile(r"\bgateways\b"), "all"),
    (
        "internal-name/personal-agent-system",
        re.compile(r"personal-agent-system"),
        "all",
    ),
    ("internal-name/obsidianvault", re.compile(r"ObsidianVault"), "all"),
    ("internal-name/heartbeat", re.compile(r"\bheartbeat\b"), "all"),
    # Token-shaped values — subset of secrets-scan plus Slack refs, kept
    # as defense in depth at the distribution boundary.
    ("token/github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "all"),
    ("token/gh-oauth", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "all"),
    ("token/openai", re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "all"),
    ("token/aws-akid", re.compile(r"\bAKIA[0-9A-Z]{16}"), "all"),
    ("token/private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "all"),
    ("token/slack", re.compile(r"\bxox[baprs]-|hooks\.slack\.com"), "all"),
    (
        "token/api-key-value",
        re.compile(r"""api[_-]?key["']?\s*[:=]\s*["'][A-Za-z0-9_-]{16,}"""),
        "all",
    ),
]

# A devin-* token counts as a CLI invocation when it sits in command
# position inside a fenced code block or inline backticks — the first
# word of a shell segment, or a token following a launcher such as
# ``uvx``/``uv run``/``pipx run``/``npx``. Prose, install lines
# (``pip install devin-foo``) and comments do not promise a command.
CMD_TOKEN_RE = re.compile(r"\bdevin-\w[\w-]*")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
FENCE_RE = re.compile(r"\s*([`~])\1{2,}")
SHELL_SEP_RE = re.compile(r"&&|\|\||[|;]")
QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
ENV_ASSIGN_RE = re.compile(r"\w+=\S+")
LAUNCHERS = {"uvx", "npx", "bunx"}


def is_doc(path: Path) -> bool:
    return path.suffix.lower() in DOC_SUFFIXES


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\0" in fh.read(8192)
    except OSError:
        return True


def scan_roots(root: Path) -> list[Path]:
    """Explicit scan roots that exist under ``root``."""
    roots: list[Path] = []
    for rel in ("adapters", ".devin/skills"):
        if (root / rel).is_dir():
            roots.append(root / rel)
    packages = root / "packages"
    if packages.is_dir():
        for pkg in sorted(packages.iterdir()):
            if not pkg.is_dir():
                continue
            for rel in ("adapters", ".devin/skills"):
                if (pkg / rel).is_dir():
                    roots.append(pkg / rel)
    return roots


def iter_files(roots: list[Path]):
    for base in roots:
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            # Only dirs *inside* the scan root count — ancestor dirs of the
            # checkout itself (e.g. a parent literally named "build") must
            # not hide the tree.
            rel_parents = path.relative_to(base).parts[:-1]
            if SKIP_DIRS & set(rel_parents):
                continue
            yield path


def load_allowlist(root: Path) -> dict[str, str]:
    """``path -> sha256`` pins from .adapters-hygiene-allow.

    An entry without ``sha256=`` is malformed and never allows anything
    (same rule as .secrets-scan-allow).
    """
    pins: dict[str, str] = {}
    allow = root / ALLOWLIST
    if not allow.is_file():
        return pins
    for line in allow.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path_part, sep, hash_part = line.partition(" ")
        if not sep or "sha256=" not in hash_part:
            continue  # malformed — do not allow
        pins[path_part] = hash_part.split("sha256=", 1)[1].split()[0]
    return pins


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_forbidden(root: Path, files, pins: dict[str, str]) -> list[str]:
    findings: list[str] = []
    for path in files:
        binary = is_binary(path)
        rel = path.relative_to(root).as_posix()
        text = path.read_bytes().decode("utf-8", errors="replace")
        hits: list[str] = []
        doc = is_doc(path)
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pattern, scope in FORBIDDEN:
                # Binary adapter assets are not text-searchable in full —
                # but token-shaped values are still greppable, so only
                # the token/* rules apply there.
                if binary and not name.startswith("token/"):
                    continue
                if scope == "non-doc" and doc:
                    continue
                for m in pattern.finditer(line):
                    hits.append(f"{rel}:{lineno}: {name}: '{m.group(0)}'")
        if not hits:
            continue
        pin = pins.get(rel)
        if pin is not None and file_sha256(path) == pin:
            continue  # hash-pinned known-legitimate file
        findings.extend(hits)
    return findings


def strip_frontmatter(text: str) -> str:
    """Drop the leading --- ... --- block: name/description are metadata,
    not CLI invocations."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :])
    return text


def _segment_tokens(segment: str) -> set[str]:
    """devin-* tokens in command position within one shell segment."""
    if segment.lstrip().startswith("#"):
        return set()
    words = segment.split()
    while words and (
        words[0] in {"$", ">", "sudo", "command", "env"}
        or ENV_ASSIGN_RE.fullmatch(words[0])
    ):
        words.pop(0)
    if not words:
        return set()
    first = words[0]
    if CMD_TOKEN_RE.fullmatch(first):
        return {first}
    if first in LAUNCHERS:
        rest = " ".join(words[1:])
    elif first == "uv" and words[1:2] == ["run"]:
        rest = " ".join(words[2:])
    elif first == "uv" and words[1:3] == ["tool", "run"]:
        rest = " ".join(words[3:])
    elif first == "pipx" and words[1:2] == ["run"]:
        rest = " ".join(words[2:])
    else:
        return set()
    # Quoted spans in launcher lines are package specs/options
    # (``--from 'devin-doctor[mcp]'``), not invoked commands.
    return set(CMD_TOKEN_RE.findall(QUOTED_RE.sub(" ", rest)))


def _command_tokens(text: str) -> set[str]:
    """devin-* invocations across shell segments of one text block."""
    tokens: set[str] = set()
    for segment in SHELL_SEP_RE.split(text):
        tokens.update(_segment_tokens(segment))
    return tokens


def cli_tokens(skill: Path) -> set[str]:
    """devin-* tokens used as CLI invocations (fenced or inline code)."""
    tokens: set[str] = set()
    fence_char = ""
    for line in strip_frontmatter(skill.read_text(errors="replace")).splitlines():
        fence = FENCE_RE.match(line)
        if fence:
            if not fence_char:
                fence_char = fence.group(1)
            elif fence.group(1) == fence_char:
                fence_char = ""
            continue
        if fence_char:
            tokens.update(_command_tokens(line))
        else:
            for span in INLINE_CODE_RE.findall(line):
                tokens.update(_command_tokens(span))
    return tokens


def package_dir_for(root: Path, skill: Path) -> Path:
    """The package that owns an adapter file: packages/<pkg>/… -> the
    package dir; anything else -> the repo root."""
    rel = skill.relative_to(root).parts
    if len(rel) > 2 and rel[0] == "packages":
        return root / rel[0] / rel[1]
    return root


def check_commands(root: Path, files) -> list[str]:
    findings: list[str] = []
    for skill in files:
        rel = skill.relative_to(root).as_posix()
        if skill.name != "SKILL.md" or "/adapters/" not in f"/{rel}":
            continue  # coherence applies to adapters/**/SKILL.md only
        tokens = cli_tokens(skill)
        if not tokens:
            continue
        pkg = package_dir_for(root, skill)
        scripts: set[str] = set()
        pyproject = pkg / "pyproject.toml"
        if pyproject.is_file():
            data = tomllib.loads(pyproject.read_text())
            scripts = set(data.get("project", {}).get("scripts", {}))
        # Whole-word tokens only — a README that names the longer
        # ``devin-checker`` must not silently validate ``devin-check``.
        readme_tokens: set[str] = set()
        readme = pkg / "README.md"
        if readme.is_file():
            readme_tokens = set(
                CMD_TOKEN_RE.findall(readme.read_text(errors="replace"))
            )
        for token in sorted(tokens):
            if token not in scripts and token not in readme_tokens:
                findings.append(
                    f"{rel}: '{token}' invoked but not in "
                    f"{pyproject.relative_to(root)} [project.scripts] "
                    f"nor {readme.relative_to(root)}"
                )
    return findings


# --- hardcoded version pins in extension sources -----------------------------
# A VS Code extension must read its own version at runtime
# (``context.extension.packageJSON.version``); a literal semver assigned to
# a ``*version*`` identifier drifts from package.json the next bump — this
# exact class shipped once already (an endpoint advertising 0.1.0 for a
# 0.1.2 build). Scope: source files of a real extension only — a directory
# whose package.json declares ``engines.vscode``. package.json itself,
# tests and build output are exempt; non-version constants (CLI compat
# ranges, API levels) are not matched.

EXT_SRC_SUFFIXES = {".ts", ".cts", ".mts", ".js", ".cjs", ".mjs"}
EXT_SRC_SKIP_PARTS = {
    "node_modules", "out", "dist", "build", "test", "tests",
    "__tests__", "fixtures",
}
VERSION_PIN_RE = re.compile(
    r"(?:^|[\s{,])(?:export\s+)?(?:const|let|var|readonly)\s+"
    r"(\w*version\w*)\s*(?::\s*[^=;]+?)?\s*=\s*"
    r"['\"](\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]*)?)['\"]",
    re.IGNORECASE,
)
VERSION_PROP_RE = re.compile(
    r"[\s{,]['\"]?version['\"]?\s*:\s*"
    r"['\"](\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]*)?)['\"]",
    re.IGNORECASE,
)


def is_extension_source(root: Path, f: Path) -> bool:
    """True when the nearest package.json walking up from ``f`` declares
    ``engines.vscode`` — covers package-root extensions whose manifest
    sits outside the adapter scan roots."""
    import json

    d = f.parent
    while d == root or root in d.parents:
        pkg = d / "package.json"
        if pkg.is_file():
            try:
                data = json.loads(pkg.read_text(errors="replace"))
            except ValueError:
                data = {}
            return (
                isinstance(data.get("engines"), dict)
                and "vscode" in data["engines"]
            )
        d = d.parent
    return False


def _iter_code_lines(text: str):
    """Yield ``(lineno, line)`` with ``//`` and ``/* */`` comments
    stripped. ``//`` inside a string literal on the same line hides the
    rest of that line — accepted: commented-out examples are the common
    case, URLs adjacent to pins are not."""
    in_block = False
    for lineno, line in enumerate(text.splitlines(), 1):
        out: list[str] = []
        j = 0
        while j < len(line):
            if in_block:
                k = line.find("*/", j)
                if k == -1:
                    j = len(line)
                else:
                    in_block = False
                    j = k + 2
            elif line.startswith("//", j):
                break
            elif line.startswith("/*", j):
                in_block = True
                j += 2
            else:
                out.append(line[j])
                j += 1
        yield lineno, "".join(out)


def check_version_pins(root: Path, files) -> list[str]:
    findings: list[str] = []
    for f in files:
        if f.name == "package.json" or f.suffix.lower() not in EXT_SRC_SUFFIXES:
            continue
        if f.name.endswith(".d.ts"):
            continue
        parts = set(f.relative_to(root).parts)
        if parts & EXT_SRC_SKIP_PARTS or f.stem.endswith((".test", ".spec")):
            continue
        if not is_extension_source(root, f):
            continue
        rel = f.relative_to(root).as_posix()
        for lineno, line in _iter_code_lines(
            f.read_text(errors="replace")
        ):
            hit = VERSION_PIN_RE.search(line) or VERSION_PROP_RE.search(line)
            if hit:
                findings.append(
                    f"{rel}:{lineno}: version-pin — hardcoded semver in an "
                    f"extension source drifts from package.json "
                    f"(use context.extension.packageJSON.version)"
                )
    return findings


def run(root: Path) -> tuple[list[str], int]:
    """Return (findings, scanned-file-count)."""
    roots = scan_roots(root)
    if not roots:
        return [], 0
    files = list(iter_files(roots))
    pins = load_allowlist(root)
    findings = check_forbidden(root, files, pins)
    findings += check_commands(root, files)
    findings += check_version_pins(root, files)
    return findings, len(files)


def selftest() -> int:
    """Run the scanner against synthetic fixtures: a dirty tree must
    fail, a clean tree and an allowlisted tree must pass."""
    failures: list[str] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"  {status} {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # ---- fixture: clean package -------------------------------
        clean = base / "clean"
        skill = clean / "packages/demo/adapters/skills/devin-demo/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: devin-demo\n---\n\n```bash\ndevin-demo check --json\n```\n"
        )
        (clean / "packages/demo/pyproject.toml").write_text(
            '[project]\nname = "devin-demo"\n'
            '[project.scripts]\ndevin-demo = "devin_demo.cli:main"\n'
        )
        (clean / "packages/demo/README.md").write_text("# devin-demo\n")
        plugin = clean / "adapters/plugin/.devin-plugin/plugin.json"
        plugin.parent.mkdir(parents=True)
        plugin.write_text('{"name": "devin-demo"}\n')
        findings, nfiles = run(clean)
        expect("clean fixture passes", findings == [] and nfiles == 2,
               f"findings={findings}")

        # ---- fixture: dirty ----------------------------------------
        dirty = base / "dirty"
        dskill = dirty / "packages/demo/adapters/skills/devin-demo/SKILL.md"
        dskill.parent.mkdir(parents=True)
        dskill.write_text(
            "---\nname: devin-demo\n---\n\n```bash\ndevin-ghost run\n```\n"
        )
        (dirty / "packages/demo/pyproject.toml").write_text(
            '[project]\nname = "devin-demo"\n'
            '[project.scripts]\ndevin-demo = "devin_demo.cli:main"\n'
        )
        (dirty / "packages/demo/README.md").write_text("# devin-demo\n")
        leak = dirty / "adapters/skill/SKILL.md"
        leak.parent.mkdir(parents=True)
        leak.write_text("scrapes via /home/me/pw-gsc\n")
        svc = dirty / "adapters/daemon/demo.service"
        svc.parent.mkdir(parents=True)
        svc.write_text("ExecStart=curl 127.0.0.1:9223\n")
        findings, _ = run(dirty)
        joined = "\n".join(findings)
        expect("dirty fixture fails", len(findings) >= 4, f"{len(findings)}")
        expect("personal-path reported", "personal-path/home" in joined)
        expect("loopback reported", "internal-endpoint/loopback" in joined)
        expect("internal-name reported", "internal-name/pw-gsc" in joined)
        expect("phantom command reported", "devin-ghost" in joined)

        # ---- fixture: allowlisted dirty file -----------------------
        allow = base / "allow"
        aleak = allow / "adapters/vscode/test/extension.test.js"
        aleak.parent.mkdir(parents=True)
        aleak.write_text('const cwd = "/home/u/repo";\n')
        (allow / ".adapters-hygiene-allow").write_text(
            f"# fixture pin\nadapters/vscode/test/extension.test.js "
            f"sha256={file_sha256(aleak)}\n"
        )
        findings, _ = run(allow)
        expect("allowlisted file passes", findings == [], f"{findings}")

        # ---- allowlist does not mask command coherence -------------
        coh = base / "coh"
        cskill = coh / "adapters/skills/x/SKILL.md"
        cskill.parent.mkdir(parents=True)
        cskill.write_text("```bash\ndevin-phantom go\n```\n")
        (coh / "README.md").write_text("# x\n")
        findings, _ = run(coh)
        expect("coherence cannot be allowlisted",
               any("devin-phantom" in f for f in findings), f"{findings}")

        # ---- fixture: no adapters -> clean skip --------------------
        empty = base / "empty"
        (empty / "src").mkdir(parents=True)
        findings, nfiles = run(empty)
        expect("no-adapter repo skips clean", findings == [] and nfiles == 0)

        # ---- fixture: README substring must not validate ------------
        sub = base / "substr"
        sskill = sub / "adapters/skills/x/SKILL.md"
        sskill.parent.mkdir(parents=True)
        sskill.write_text("```bash\ndevin-check --json\n```\n")
        (sub / "README.md").write_text("# demo\n\nUse `devin-checker`.\n")
        findings, _ = run(sub)
        expect("longer README name does not validate",
               any("devin-check" in f for f in findings), f"{findings}")

        # ---- fixture: tilde fences and shell-position tokens ---------
        tilde = base / "tilde"
        tskill = tilde / "adapters/skills/x/SKILL.md"
        tskill.parent.mkdir(parents=True)
        tskill.write_text(
            "~~~bash\ndevin-ghost check\n~~~\n\n"
            "```bash\npip install devin-other\n# devin-comment\n"
            "echo ok && devin-inline run\n```\n"
        )
        (tilde / "README.md").write_text("# x\n")
        findings, _ = run(tilde)
        joined = "\n".join(findings)
        expect("tilde-fenced command flagged", "devin-ghost" in joined)
        expect("install line not a command", "devin-other" not in joined)
        expect("fence comment not a command", "devin-comment" not in joined)
        expect("post-separator command flagged", "devin-inline" in joined)

        # ---- fixture: launcher segment -------------------------------
        lau = base / "launcher"
        lskill = lau / "adapters/skills/x/SKILL.md"
        lskill.parent.mkdir(parents=True)
        lskill.write_text(
            "```bash\nuvx --from 'devin-doctor[mcp]' devin-ghost\n```\n"
        )
        (lau / "README.md").write_text("# x\n")
        findings, _ = run(lau)
        joined = "\n".join(findings)
        expect("launcher target flagged", "devin-ghost" in joined)
        expect("quoted --from spec not a command",
               "devin-doctor" not in joined)

        # ---- fixture: binary token + single-backslash path ----------
        misc = base / "misc"
        blob = misc / "adapters/bin/blob.bin"
        blob.parent.mkdir(parents=True)
        blob.write_bytes(
            b"\x00\x01ghp_" + b"a" * 40 + b"\x00"
        )
        leak = misc / "adapters/cfg/win.txt"
        leak.parent.mkdir(parents=True)
        leak.write_text("home=C:\\Users\\alice\n")
        findings, _ = run(misc)
        joined = "\n".join(findings)
        expect("binary token flagged", "token/gh-oauth" in joined)
        expect("single-backslash C:\\Users flagged",
               "personal-path/cusers" in joined)

        # ---- fixture: version pins in extension sources --------------
        ext = base / "ext"
        extpkg = ext / "adapters/vscode/package.json"
        extpkg.parent.mkdir(parents=True)
        extpkg.write_text(
            '{"name": "demo-ext", "version": "0.1.2",'
            ' "engines": {"vscode": "^1.90.0"}}\n'
        )
        bad = ext / "adapters/vscode/src/extension.ts"
        bad.parent.mkdir(parents=True)
        bad.write_text(
            'const VERSION = "0.1.0";\n'
            'const manifest = { version: "1.0.0" };\n'
            'const meta = { "version": "1.0.1" };\n'
            'const VERSION: string = "0.1.2";\n'
            'const VERSION2 = "0.1.3";\n'
            '// const VERSION = "0.1.0"; — historical note\n'
            '/* const VERSION = "9.9.9"; */\n'
            'const runtime = context.extension.packageJSON.version;\n'
            'const COMPATIBLE_CLI = { min: [0, 1], max: [1, 9] };\n'
            'export function parseCompat(v: string): number[] { return []; }\n'
        )
        testfile = ext / "adapters/vscode/test/version.test.js"
        testfile.parent.mkdir(parents=True)
        testfile.write_text('assert.equal(VERSION, "0.1.0");\n')
        built = ext / "adapters/vscode/out/extension.js"
        built.parent.mkdir(parents=True)
        built.write_text('const VERSION = "0.1.0";\n')
        nonext = ext / "packages/tool/src/x.ts"
        nonext.parent.mkdir(parents=True)
        nonext.write_text('const VERSION = "9.9.9";\n')
        findings, _ = run(ext)
        joined = "\n".join(findings)
        expect("const VERSION pin flagged", "version-pin" in joined)
        expect("quoted-key pin flagged", ":3:" in joined)
        expect("typed-annotation pin flagged", ":4:" in joined)
        expect("digit-suffix pin flagged", ":5:" in joined)
        expect("line comment ignored", ":6:" not in joined)
        expect("block comment ignored", ":7:" not in joined)
        expect("test file exempt", "version.test.js" not in joined)
        expect("build output exempt", "out/extension.js" not in joined)
        expect("non-extension source exempt", "tool/src/x.ts" not in joined)

        # ---- fixture: package-root extension (manifest above scan root)
        pkgroot = base / "pkgroot"
        rootpkg = pkgroot / "packages/demo/package.json"
        rootpkg.parent.mkdir(parents=True)
        rootpkg.write_text(
            '{"name": "demo", "engines": {"vscode": "^1.90.0"}}\n'
        )
        src = pkgroot / "packages/demo/adapters/vscode/src/ext.ts"
        src.parent.mkdir(parents=True)
        src.write_text('const EXT_VERSION = "2.0.0";\n')
        findings, _ = run(pkgroot)
        expect("package-root extension flagged",
               any("version-pin" in f for f in findings), f"{findings}")

    if failures:
        print(f"selftest: {len(failures)} case(s) FAILED", file=sys.stderr)
        return 1
    print("selftest: all cases passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        default=".",
        help="repo root to scan (default: %(default)s)",
    )
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="run the scanner against synthetic fixtures and exit",
    )
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    root = Path(args.root).resolve()
    findings, nfiles = run(root)
    if nfiles == 0 and not findings:
        print("adapters-check: no adapters/.devin skill dirs found — skipped.")
        return 0
    if findings:
        for line in findings:
            print(line)
        print(
            f"::error::adapters-check found {len(findings)} violation(s). "
            f"Sanitize the file, or pin a known-legitimate hit in "
            f"{ALLOWLIST} as 'path sha256=<hash>'.",
            file=sys.stderr,
        )
        return 1
    print(f"adapters-check: {nfiles} distributed adapter file(s) clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

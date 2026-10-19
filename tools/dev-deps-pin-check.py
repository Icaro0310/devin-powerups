#!/usr/bin/env python3
"""dev-deps-pin-check.py — fail when a dev/test/lint tool floats.

Pins alone did not close the drift class (ruff was silently bumped three
times; 0.17 broke two repos' main by flagging previously-valid ``# noqa``
directives): pins get added once and then edited, and the resolution
points that actually fetch the tool (``pip install``, ``uvx``,
``astral-sh/ruff-action`` with no ``version:``) float by default. This
sensor scans one checkout and fails while any declaration site resolves
"a newer whatever" instead of a fixed version.

Checked names are lint/test/build tools only — runtime deps are
whitelisted by absence from the list. Defaults:

    ruff, pytest, pytest-cov, mypy, bandit, black, coverage,
    hatch, hatchling, setuptools, wheel, build, twine

Override with ``--tools name1,name2`` (e.g. add ``uv`` to also catch
``pipx run uv`` lines).

Declaration sites scanned, recursively under the repo dir:

* ``pyproject.toml`` — ``[build-system].requires``,
  ``[project].dependencies``, ``[project.optional-dependencies]``,
  ``[dependency-groups]``, ``[tool.uv].dev-dependencies`` and
  ``[tool.hatch.envs.*].dependencies``.
* ``requirements*.txt`` — one requirement per line.
* ``.github/workflows/*.{yml,yaml}`` — ``pip install`` / ``pipx install``
  / ``pipx run`` / ``uvx`` / ``uv tool run`` / ``uv tool install`` args
  (incl. ``--spec``/``--from``/``--with`` values), and
  ``uses: astral-sh/ruff-action`` steps without a ``version:`` input —
  the action SHA is pinned but the ruff it installs floats to latest,
  which is where the 0.17 surprise actually came from.
  ``uv run ruff`` is covered transitively: it resolves through the
  project env, whose specifiers are already checked above.

Floating: no specifier, a bare ``>=``/``>``/``!=`` (lower bounds only),
``*``, ``latest``, a direct reference with no ref or a moving ref
(``@main``/``@master``/``@HEAD``/``@trunk``). Non-floating: ``==``,
``===``, ``~=``, any spec with an upper bound (``<``/``<=``), a fixed
``pkg@X.Y``/``pkg@vX.Y``/``pkg@<sha>`` ref, or an archive-URL direct
reference. Note ``~=X.Y`` on a 0.x tool still floats across minors
(``~=0.9`` allows 0.17) — patch-precision ``~=X.Y.Z`` or ``==`` is the
pin that actually closes the 0.x minor-bump class.

Usage:
    python3 tools/dev-deps-pin-check.py [<repo-dir>] [--tools a,b,c]
    python3 tools/dev-deps-pin-check.py --selftest

Exit codes: 0 = clean, 1 = floating specifier found, 2 = bad root.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent

# Lint/test/build tools whose specifiers must not float. Normalized
# (PEP 503) — entries match case-insensitively across -/_/. spellings.
DEFAULT_TOOLS = (
    "ruff",
    "pytest",
    "pytest-cov",
    "mypy",
    "bandit",
    "black",
    "coverage",
    "hatch",
    "hatchling",
    "setuptools",
    "wheel",
    "build",
    "twine",
)

# Directory names that are never scanned — build/cache output and the
# .powerups-sensor fetch dir are not declaration sites.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", "dist", "build",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox", ".nox", ".powerups-sensor",
}

_NAME = r"[A-Za-z][A-Za-z0-9._-]*"
REQ_NAME_RE = re.compile(rf"^\s*({_NAME})\s*(\[[^\]]*\])?\s*(.*)$")
CLAUSE_RE = re.compile(r"(===|==|~=|!=|>=|<=|>|<)")
FLOATING_REFS = {"", "latest", "main", "master", "head", "trunk", "stable"}
VERSIONISH_RE = re.compile(r"^v?\d[0-9A-Za-z.\-]*$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
ARCHIVE_RE = re.compile(r"\.(whl|zip|tar\.gz|tgz|tar\.bz2|tar\.xz)$", re.IGNORECASE)

PIP_INSTALL_RE = re.compile(
    r"\b(?:python3?|py)\s+-m\s+pip3?\s+install\b"
    r"|\buv\s+pip\s+install\b"
    r"|\bpip3?\s+install\b"
)
UV_RUN_RE = re.compile(r"\b(?:uvx|uv\s+tool\s+run)\b")
UV_INSTALL_RE = re.compile(r"\buv\s+tool\s+install\b")
PIPX_RUN_RE = re.compile(r"\bpipx\s+run\b")
PIPX_INSTALL_RE = re.compile(r"\bpipx\s+(?:install|inject)\b")
RUFF_ACTION_RE = re.compile(r"\buses:\s*astral-sh/ruff-action(?:@|\b)")

# Options that consume the NEXT token (which is then never a
# requirement). --spec/--from/--with are deliberately absent: their
# values ARE package specs and get checked.
_VALUE_OPTIONS = {
    "-r", "--requirement", "-c", "--constraint", "-e", "--editable",
    "-t", "--target", "-f", "--find-links", "-i", "--index-url",
    "--extra-index-url", "-d", "--download", "--src", "--root",
    "--prefix", "-p", "--python", "--platform", "--abi",
    "--implementation",
}
SPEC_OPTIONS = {"--spec", "--from", "--with"}


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _strip_inline_comment(text: str) -> str:
    # Cut ` #...` (a `#` without preceding space stays — `#egg=` is a
    # fragment, not a comment).
    return re.split(r"\s#|\t#", text, maxsplit=1)[0]


def ref_is_floating(ref: str) -> bool:
    """A ``@ref`` floats when it names a moving target: latest, a branch
    default, or anything that is not version-shaped/SHA-shaped (a branch
    name like ``@fix-thing`` moves just like ``main`` does)."""
    ref = ref.strip()
    if ref.lower() in FLOATING_REFS:
        return True
    return not (VERSIONISH_RE.match(ref) or SHA_RE.match(ref))


def spec_is_floating(spec: str) -> bool:
    """PEP 440 specifier part: floating = bare, wildcard, or lower
    bounds only (``>=x`` with no ceiling drifts to every new release)."""
    s = spec.strip()
    if not s or s == "*":
        return True
    if re.fullmatch(r"==\s*\*", s):
        return True
    ops = set(CLAUSE_RE.findall(s))
    if not ops:
        return True  # unparseable — fail closed, not silently ok
    return ops <= {">=", ">", "!="}


def _url_spec_floating(target: str) -> bool:
    """Direct reference target: an archive URL is immutable, a bare repo
    URL tracks the default branch, ``@ref`` defers to ref_is_floating."""
    if ARCHIVE_RE.search(target):
        return False
    if "@" in target:
        return ref_is_floating(target.rsplit("@", 1)[1])
    return True


def _egg_name(target: str) -> str | None:
    m = re.search(rf"#egg=({_NAME})", target)
    if m:
        return m.group(1)
    base = re.sub(r"[?#].*$", "", target).rstrip("/").rsplit("/", 1)[-1]
    base = base.split("@", 1)[0]  # a VCS @ref is not part of the name
    base = re.sub(r"\.git$|\.(whl|zip|tar\.gz|tgz|tar\.bz2|tar\.xz)$", "", base)
    return base if re.fullmatch(_NAME, base) else None


def requirement_finding(req: str, tools: set[str], where: str) -> str | None:
    """Return a finding detail when `req` names a checked tool with a
    floating specifier, else None."""
    s = _strip_inline_comment(req.strip().rstrip("\\").strip())
    s = s.split(";", 1)[0].strip()  # environment markers
    if not s or s.startswith("$"):
        return None
    # VCS/URL requirement without a `name @` split (requirements.txt
    # allows bare URLs): name comes from #egg= or the last path segment.
    if re.match(r"^(?:git|hg|svn|bzr)\+|https?://|file:", s):
        name = _egg_name(s)
        if name is None or normalize(name) not in tools:
            return None
        if _url_spec_floating(s):
            return f"{where}: '{req}' resolves to a moving target (no pinned ref)"
        return None
    m = REQ_NAME_RE.match(s)
    if not m:
        return None
    name, _, spec = m.groups()
    if normalize(name) not in tools:
        return None
    spec = spec.strip()
    if spec.startswith("@"):
        # `name@X` — uvx-style ref, or `name @ target` direct reference
        target = spec.lstrip("@").strip()
        floating = (
            _url_spec_floating(target)
            if re.match(r"^(?:git|hg|svn|bzr)\+|https?://|file:", target)
            else ref_is_floating(target)
        )
        if floating:
            return f"{where}: '{req}' resolves to a moving target (no pinned ref)"
        return None
    if spec_is_floating(spec):
        return f"{where}: '{req}' has no upper bound — floats to newest release"
    return None


def _line_no(text: str, needle: str) -> int:
    """Best-effort line number of a requirement string for reports."""
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return 0


def _toml_sites(pyproject: Path) -> list[tuple[str, str]] | str:
    """(section, requirement) pairs from every dep-declaring table,
    or an error string when the file cannot be parsed."""
    try:
        import tomllib
        text = pyproject.read_text(encoding="utf-8")
        # new-repo.py renders template/pyproject.toml's {{name}} /
        # {{module}} / {{description}} placeholders at scaffold time —
        # the template is itself a declaration site, so scrub them to a
        # TOML-safe token rather than failing on unrendered syntax.
        text = re.sub(r"\{\{[^}]*\}\}", "placeholder", text)
        data = tomllib.loads(text)
    except Exception as exc:  # fail closed: unparseable is a finding
        return f"cannot parse {pyproject.name}: {exc}"
    sites: list[tuple[str, str]] = []
    build = data.get("build-system") or {}
    sites += [("build-system.requires", r) for r in build.get("requires") or []]
    project = data.get("project") or {}
    sites += [("project.dependencies", r) for r in project.get("dependencies") or []]
    for group, reqs in (project.get("optional-dependencies") or {}).items():
        sites += [
            (f"project.optional-dependencies.{group}", r) for r in reqs or []
        ]
    for group, reqs in (data.get("dependency-groups") or {}).items():
        sites += [
            (f"dependency-groups.{group}", r)
            for r in reqs or []
            if isinstance(r, str)  # PEP 735 {include-group=...} entries
        ]
    tool = data.get("tool") or {}
    for r in ((tool.get("uv") or {}).get("dev-dependencies")) or []:
        sites.append(("tool.uv.dev-dependencies", r))
    for env, cfg in ((tool.get("hatch") or {}).get("envs") or {}).items():
        for r in (cfg or {}).get("dependencies") or []:
            sites.append((f"tool.hatch.envs.{env}.dependencies", r))
    return sites


def check_pyproject(pyproject: Path, tools: set[str]) -> list[str]:
    sites = _toml_sites(pyproject)
    if isinstance(sites, str):
        return [f"{pyproject}: {sites}"]
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    findings = []
    for section, req in sites:
        if not isinstance(req, str):
            continue  # non-string table entries are not requirements
        finding = requirement_finding(req, tools, f"[{section}]")
        if finding:
            findings.append(f"{pyproject}:{_line_no(text, req)}: {finding}")
    return findings


def check_requirements_file(path: Path, tools: set[str]) -> list[str]:
    findings = []
    text = path.read_text(encoding="utf-8", errors="replace")
    # join `\` continuations (hash-pinned blocks) before per-line parse
    logical: list[tuple[int, str]] = []
    pending = ""
    start = 0
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if pending:
            pending += " " + line.lstrip()
        else:
            pending, start = line, i
        if pending.endswith("\\"):
            pending = pending[:-1]
            continue
        logical.append((start, pending))
        pending = ""
    if pending:
        logical.append((start, pending))
    for lineno, line in logical:
        s = _strip_inline_comment(line).strip()
        if not s or s.startswith("#"):
            continue
        token = s.split()[0]
        if token.startswith("-"):  # -r/-c/-e/--option lines
            continue
        finding = requirement_finding(s, tools, "requirements")
        if finding:
            findings.append(f"{path}:{lineno}: {finding}")
    return findings


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """(lineno, line) with trailing-`\\` continuations joined — a
    `pip install \\` block in a workflow is one logical install line."""
    out: list[tuple[int, str]] = []
    pending, start = "", 0
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        pending = pending + " " + line.lstrip() if pending else line
        start = start or i
        if pending.endswith("\\"):
            pending = pending[:-1]
            continue
        out.append((start, pending))
        pending, start = "", 0
    if pending:
        out.append((start, pending))
    return out


def _shell_tokens(text: str) -> list[str]:
    try:
        return shlex.split(_strip_inline_comment(text), comments=False)
    except ValueError:
        return text.split()


def _install_args(tokens: list[str]) -> list[str]:
    """Requirement tokens from an install command tail: skip flags and
    the values of value-consuming options; keep --spec/--from/--with
    values (they are the spec) and every positional."""
    specs: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("$") or tok.startswith("${"):
            i += 1
            continue
        if tok.startswith("--") and "=" in tok:
            opt, val = tok.split("=", 1)
            if opt in SPEC_OPTIONS:
                specs.append(val)
            i += 1
            continue
        if tok in SPEC_OPTIONS:
            if i + 1 < len(tokens):
                specs.append(tokens[i + 1])
            i += 2
            continue
        if tok.startswith("-"):
            i += 2 if tok in _VALUE_OPTIONS else 1
            continue
        specs.append(tok)
        i += 1
    return specs


def _run_args(tokens: list[str]) -> list[str]:
    """Specs from a run command tail (uvx/uv tool run/pipx run): the
    first positional is the resolved tool unless --spec/--from names
    the package — positionals after it are the tool's own argv."""
    spec_values: list[str] = []
    first_positional: str | None = None
    has_name_opt = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--") and "=" in tok:
            opt, val = tok.split("=", 1)
            if opt in SPEC_OPTIONS:
                spec_values.append(val)
                has_name_opt = has_name_opt or opt != "--with"
            i += 1
            continue
        if tok in SPEC_OPTIONS:
            if i + 1 < len(tokens):
                spec_values.append(tokens[i + 1])
            has_name_opt = has_name_opt or tok != "--with"
            i += 2
            continue
        if tok.startswith("-"):
            i += 2 if tok in _VALUE_OPTIONS else 1
            continue
        first_positional = tok
        break
    if not has_name_opt and first_positional is not None:
        spec_values.append(first_positional)
    return spec_values


def _ruff_action_version(lines: list[tuple[int, str]], index: int) -> str | None:
    """`version:` input of the ruff-action step starting at `index`,
    or None. Step keys (with:, name:, if:, env:) sit deeper than the
    ``- uses:`` line, so the step ends at the first non-blank line at
    or below that indent — the next ``- step``, job or jobs: key."""
    _, first = lines[index]
    indent = len(first) - len(first.lstrip())
    for _, line in lines[index + 1 : index + 15]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if len(line) - len(line.lstrip()) <= indent:
            break
        m = re.match(r"version\s*:\s*(.+?)\s*$", stripped)
        if m:
            return m.group(1).strip("'\"")
    return None


def check_workflow(path: Path, tools: set[str]) -> list[str]:
    findings = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = _logical_lines(text)
    for idx, (lineno, line) in enumerate(lines):
        if line.strip().startswith("#"):
            continue  # commented-out workflow lines declare nothing
        if RUFF_ACTION_RE.search(line):
            version = _ruff_action_version(lines, idx)
            if version is None:
                findings.append(
                    f"{path}:{lineno}: astral-sh/ruff-action has no 'version:'"
                    " input — installs the latest ruff every run"
                )
            elif version.lower() in FLOATING_REFS:
                findings.append(
                    f"{path}:{lineno}: ruff-action version '{version}' is not a pin"
                )
        for regex, argger in (
            (PIP_INSTALL_RE, _install_args),
            (UV_INSTALL_RE, _install_args),
            (PIPX_INSTALL_RE, _install_args),
            (UV_RUN_RE, _run_args),
            (PIPX_RUN_RE, _run_args),
        ):
            m = regex.search(line)
            if not m:
                continue
            for spec in argger(_shell_tokens(line[m.end() :])):
                finding = requirement_finding(spec, tools, "workflow install")
                if finding:
                    findings.append(f"{path}:{lineno}: {finding}")
    return findings


def iter_files(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """(pyprojects, requirements files, workflow files) under root."""
    pyprojects: list[Path] = []
    reqs: list[Path] = []
    workflows: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        base = Path(dirpath)
        for name in filenames:
            p = base / name
            if name == "pyproject.toml":
                pyprojects.append(p)
            elif name.startswith("requirements") and name.endswith(".txt"):
                reqs.append(p)
            elif (
                name.endswith((".yml", ".yaml"))
                and base.parent.name == ".github"
                and base.name == "workflows"
            ):
                workflows.append(p)
    return pyprojects, reqs, workflows


def check_tree(root: Path, tools: set[str]) -> tuple[list[str], int]:
    """(findings, files-scanned) — the whole sensor, reusable by tests."""
    pyprojects, reqs, workflows = iter_files(root)
    findings: list[str] = []
    for p in pyprojects:
        findings += check_pyproject(p, tools)
    for p in reqs:
        findings += check_requirements_file(p, tools)
    for p in workflows:
        findings += check_workflow(p, tools)
    return findings, len(pyprojects) + len(reqs) + len(workflows)


def selftest() -> int:
    """Synthetic fixtures: floating specs must fail, pinned specs and
    non-tool deps must pass."""
    failures: list[str] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"  {status} {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    tools = set(DEFAULT_TOOLS)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # ---- fixture: every site pinned ----------------------------
        clean = base / "clean"
        (clean / ".github/workflows").mkdir(parents=True)
        (clean / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools>=77,<82"]\n'
            '[project]\nname = "x"\ndependencies = ["requests>=2"]\n'
            '[project.optional-dependencies]\n'
            'dev = ["pytest==8.3.5", "ruff~=0.9.0"]\n'
            '[dependency-groups]\nlint = ["mypy>=1.0,<2"]\n'
            '[tool.uv]\ndev-dependencies = ["coverage==7.6.1"]\n'
        )
        (clean / "requirements-dev.txt").write_text(
            "black==24.10.0\n-r base.txt\n"
        )
        (clean / ".github/workflows/ci.yml").write_text(
            "steps:\n"
            "  - run: pip install 'ruff==0.9.0' pytest-cov~=5.0\n"
            "  - run: uvx ruff@0.9.0 check .\n"
            "  - run: uv tool run 'ruff@0.9.0' check .\n"
            "  - run: pipx install 'ruff==0.9.0'\n"
            "  - uses: astral-sh/ruff-action@abc123\n"
            "    with:\n      version: \"0.9.0\"\n      args: check .\n"
            "  - run: pip install -U devin-redact requests\n"
        )
        findings, _ = check_tree(clean, tools)
        expect("all-pinned fixture passes", findings == [], f"{findings}")

        # ---- fixture: floating in every site -----------------------
        dirty = base / "dirty"
        (dirty / ".github/workflows").mkdir(parents=True)
        (dirty / "pyproject.toml").write_text(
            '[project.optional-dependencies]\ndev = ["ruff"]\n'
            '[dependency-groups]\ndev = ["pytest>=8", "ruff>=0.9"]\n'
            '[build-system]\nrequires = ["hatchling"]\n'
            '[tool.uv]\ndev-dependencies = ["mypy>=1"]\n'
        )
        (dirty / "requirements-tools.txt").write_text("bandit\n")
        (dirty / ".github/workflows/ci.yml").write_text(
            "steps:\n"
            "  - run: uv tool run ruff check .\n"
            "  - run: pip install --upgrade black\n"
            "  - run: pipx run ruff check .\n"
            "  - uses: astral-sh/ruff-action@abc123\n"
            "    with:\n      args: check .\n"
        )
        findings, _ = check_tree(dirty, tools)
        joined = "\n".join(findings)
        expect("bare ruff in optional-deps flagged", "'ruff'" in joined)
        expect("pytest>=8 in dep-group flagged", "'pytest>=8'" in joined)
        expect("ruff>=0.9 bare lower bound flagged", "'ruff>=0.9'" in joined)
        expect("bare hatchling in build requires flagged", "'hatchling'" in joined)
        expect("tool.uv dev-dep flagged", "'mypy>=1'" in joined)
        expect("requirements bandit flagged", "'bandit'" in joined)
        expect("uv tool run ruff flagged", "uv tool run" in joined or "'ruff'" in joined)
        expect("pip install black flagged", "'black'" in joined)
        expect("pipx run ruff flagged", "'ruff'" in joined)
        expect("ruff-action without version flagged", "ruff-action" in joined)

        # ---- fixture: bounded/exact pass, moving refs fail -----------
        refs = base / "refs"
        (refs / ".github/workflows").mkdir(parents=True)
        (refs / "pyproject.toml").write_text(
            '[project.optional-dependencies]\n'
            'dev = ["ruff>=0.9,<0.10", "coverage<=7", "pytest~=9.0"]\n'
        )
        (refs / ".github/workflows/ci.yml").write_text(
            "steps:\n"
            "  - run: uvx ruff@main check .\n"
            "  - run: uvx ruff@latest check .\n"
            "  - run: pipx run 'ruff==0.9.0' check .\n"
            "  - run: pip install 'git+https://github.com/x/ruff@main'\n"
            "  - uses: astral-sh/ruff-action@abc123\n"
            "    with:\n      version: latest\n"
        )
        findings, _ = check_tree(refs, tools)
        joined = "\n".join(findings)
        expect("bounded ranges pass", "0.9,<0.10" not in joined and "~=9.0" not in joined)
        expect("uvx @main flagged", "ruff@main" in joined)
        expect("uvx @latest flagged", "ruff@latest" in joined)
        expect("git+...@main flagged", "@main" in joined)
        expect("ruff-action version:latest flagged", "version" in joined)

        # ---- fixture: unparseable pyproject fails closed -----------
        bad = base / "bad"
        bad.mkdir()
        (bad / "pyproject.toml").write_text("[project\nname = !!!\n")
        findings, _ = check_tree(bad, tools)
        expect("unparseable pyproject is a finding",
               any("cannot parse" in f for f in findings), f"{findings}")

        # ---- fixture: no declaration sites -> clean skip -----------
        empty = base / "empty"
        (empty / "src").mkdir(parents=True)
        findings, nfiles = check_tree(empty, tools)
        expect("empty repo skips clean", findings == [] and nfiles == 0)

    if failures:
        print(f"selftest: {len(failures)} case(s) FAILED", file=sys.stderr)
        return 1
    print("selftest: all cases passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="repo dir to scan (default: %(default)s)",
    )
    ap.add_argument(
        "--tools",
        help="comma-separated tool names to check "
        f"(default: {', '.join(DEFAULT_TOOLS)})",
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
    if not root.is_dir():
        print(f"::error::{root} is not a directory", file=sys.stderr)
        return 2
    tools = (
        {normalize(t) for t in args.tools.split(",") if t.strip()}
        if args.tools
        else {normalize(t) for t in DEFAULT_TOOLS}
    )
    findings, nfiles = check_tree(root, tools)
    if nfiles == 0 and not findings:
        print("dev-deps-pin-check: no pyproject/requirements/workflow "
              "declaration sites found — skipped.")
        return 0
    if findings:
        print(
            f"{root}: {len(findings)} floating dev-dep spec(s):",
            file=sys.stderr,
        )
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print(f"ok: {nfiles} declaration file(s) scanned under {root}, "
          "no floating tool specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

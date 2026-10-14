#!/usr/bin/env python3
"""Check that every VS Code extension in the repo declares
``capabilities.untrustedWorkspaces`` and that ``limited`` extensions
gate all of their workspace configuration in Restricted Mode.

The failure class this sensor covers:

* A manifest without ``capabilities.untrustedWorkspaces`` is silently
  inert in Restricted Mode — the exact mode corporate environments
  force. The absence is invisible everywhere else.
* A ``supported: "limited"`` extension that reads workspace settings
  outside ``restrictedConfigurations`` re-opens the
  ``execFile(configuration.get("executable"))`` vector: a hostile
  ``.vscode/settings.json`` points the wrapper at an arbitrary binary.
  Key-by-key review cannot see the evolution case — a new ``.get()``
  added later without a matching entry — so the gate is
  restricted-by-default rather than restricted-by-review.

Rules, for every ``package.json`` carrying ``engines.vscode`` (outside
``node_modules``):

1. ``capabilities.untrustedWorkspaces.supported`` must be declared
   (``true`` | ``"limited"`` | ``false``). Missing is a violation.
2. ``supported: "limited"`` is restricted-by-default: every key in
   ``contributes.configuration.properties`` AND every key read via
   ``workspace.getConfiguration("<ns>").get("<key>")`` in the
   extension's own sources must appear in
   ``restrictedConfigurations``. A new contributed or newly-read key
   fails the gate until it is restricted.
3. ``supported: true`` / ``false`` carry no configuration rule — the
   declaration itself is the gate.
4. Helper lockstep: a ``limited`` extension whose sources spawn a
   process (``child_process``/``execFile``/``spawn``) must resolve the
   executable through the shared ``safe-executable.cjs`` helper — the
   Windows CreateProcess cwd-search would otherwise run a binary
   planted inside an untrusted repo. The file must sit next to the
   manifest, be required/imported by a source file, and be
   byte-identical to the canonical copy shipped with this scanner
   (``adapters/shared/safe-executable.cjs``). Any copy found in the
   repo that is not byte-identical is drift and fails.

Sources scanned are ``*.js``/``*.ts``/``*.mjs``/``*.cjs`` under the
extension directory (the directory containing the manifest), excluding
``node_modules/``, ``out/``, ``dist/``. ``.get()`` calls on non-config
objects can produce false positives — the finding names file and key so
the reviewer can judge; the fix is restricting or renaming, never
widening the pattern.

Usage:
    python3 scripts/check_config_restricted.py [--root <repo-root>]
    python3 scripts/check_config_restricted.py --selftest

Exit code is non-zero when any check fails. When no VS Code extension
manifests exist the script prints a notice and exits 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

SKIP_DIRS = {"node_modules", "out", "dist", ".git", ".powerups-sensor"}
SRC_SUFFIXES = {".js", ".ts", ".mjs", ".cjs"}

HELPER_NAME = "safe-executable.cjs"
# Spawning = actually importing child_process. A comment or test that
# merely names execFile/spawn must not trip the rule (false positive
# flagged in review).
SPAWN_RE = re.compile(
    r"""require\(\s*["'](?:node:)?child_process["']\s*\)"""
    r"""|from\s+["'](?:node:)?child_process["']"""
    r"""|import\s*\(\s*["'](?:node:)?child_process["']"""
)
HELPER_IMPORT_RE = re.compile(r"""safe-executable(\.cjs)?["']""")

GET_CONFIGURATION = re.compile(r'getConfiguration\(\s*["\']([^"\']+)["\']')
GET_KEY = re.compile(r'\.get\(\s*["\']([^"\']+)["\']')
# getConfiguration() unscoped, or called on a dynamic (non-literal)
# namespace: the static check cannot tell which section the .get() reads.
UNSCOPED_CONFIGURATION = re.compile(
    r'getConfiguration\(\s*\)|getConfiguration\(\s*[^"\'\s)]')


def _skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def extension_manifests(root: Path):
    for path in sorted(root.rglob("package.json")):
        if _skipped(path):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "vscode" in (data.get("engines") or {}):
            yield path, data


def contributed_keys(data: dict) -> set[str]:
    conf = (data.get("contributes") or {}).get("configuration")
    nodes = conf if isinstance(conf, list) else [conf]
    keys: set[str] = set()
    for node in nodes:
        if isinstance(node, dict):
            keys.update((node.get("properties") or {}).keys())
    return keys


def read_keys(manifest_dir: Path, root: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Return ``{<ns>.<key>: [file:line, ...]}`` pairs read via scoped
    getConfiguration calls in the extension's sources, plus a list of
    ``file:line`` diagnostics for unscoped/dynamic-namespace reads the
    static check cannot attribute. Namespace is every
    getConfiguration("<ns>") in the file — our adapters use exactly one
    per file; more is reported as the cross-product, which fails loudly
    rather than silently missing."""
    keys: dict[str, list[str]] = {}
    unscoped: list[str] = []
    for src in sorted(manifest_dir.rglob("*")):
        if not src.is_file() or src.suffix not in SRC_SUFFIXES or _skipped(src):
            continue
        try:
            text = src.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        namespaces = GET_CONFIGURATION.findall(text)
        got_keys = [(m.group(1), m.start()) for m in GET_KEY.finditer(text)]
        if not got_keys and not UNSCOPED_CONFIGURATION.search(text):
            continue
        rel = src.relative_to(root)
        if UNSCOPED_CONFIGURATION.search(text):
            line = text[: UNSCOPED_CONFIGURATION.search(text).start()].count("\n") + 1
            unscoped.append(f"{rel}:{line}")
        for key, pos in got_keys:
            line = text[:pos].count("\n") + 1
            for ns in namespaces:
                keys.setdefault(f"{ns}.{key}", []).append(f"{rel}:{line}")
    return keys, unscoped


def canonical_helper(root: Path) -> Path | None:
    """The canonical safe-executable.cjs shipped next to this scanner —
    <repo>/adapters/shared/ locally, .powerups-sensor/adapters/shared/
    when the script was fetched for a caller."""
    script_dir = Path(__file__).resolve().parent
    cand = script_dir.parent / "adapters" / "shared" / HELPER_NAME
    return cand if cand.is_file() else None


def helper_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root: Path) -> tuple[list[str], int]:
    findings: list[str] = []
    checked = 0
    for mpath, data in extension_manifests(root):
        rel = mpath.relative_to(root)
        caps = (data.get("capabilities") or {}).get("untrustedWorkspaces")
        if not isinstance(caps, dict) or "supported" not in caps:
            findings.append(
                f"{rel}: missing capabilities.untrustedWorkspaces.supported — "
                f"the extension is silently inert in Restricted Mode"
            )
            continue
        supported = caps.get("supported")
        if supported is not True and supported is not False and supported != "limited":
            findings.append(
                f"{rel}: invalid untrustedWorkspaces.supported="
                f"{supported!r} — accepted values: true | false | \"limited\""
            )
            continue
        if supported != "limited":
            checked += 1
            continue
        restricted = set(caps.get("restrictedConfigurations") or [])
        read, unscoped = read_keys(mpath.parent, root)
        exposed = sorted((contributed_keys(data) | set(read)) - restricted)
        if exposed:
            detail = ", ".join(
                f"{k} ({', '.join(read[k][:3])})" if k in read else k
                for k in exposed
            )
            findings.append(
                f"{rel}: limited extension exposes workspace config — "
                f"add to restrictedConfigurations: {detail}"
            )
        for loc in unscoped:
            findings.append(
                f"{rel}: unscoped/dynamic getConfiguration() read at {loc} "
                f"— the static check cannot tell which section it reads; "
                f"use getConfiguration(\"<ns>\") or restrict the key"
            )
        if not exposed and not unscoped:
            checked += 1

    # --- helper lockstep ----------------------------------------------------
    canonical = canonical_helper(root)
    canonical_sha = helper_sha(canonical) if canonical else None
    for helper in sorted(root.rglob(HELPER_NAME)):
        if _skipped(helper):
            continue
        if canonical and helper.resolve() != canonical.resolve():
            if helper_sha(helper) != canonical_sha:
                findings.append(
                    f"{helper.relative_to(root)}: {HELPER_NAME} drifted "
                    f"from the canonical copy — re-copy from "
                    f"adapters/shared/{HELPER_NAME}"
                )

    for mpath, data in extension_manifests(root):
        rel = mpath.relative_to(root)
        caps = (data.get("capabilities") or {}).get("untrustedWorkspaces")
        if not isinstance(caps, dict) or caps.get("supported") != "limited":
            continue
        mdir = mpath.parent
        sources = [
            s for s in sorted(mdir.rglob("*"))
            if s.is_file() and s.suffix in SRC_SUFFIXES and not _skipped(s)
        ]
        spawns = False
        imports_helper = False
        for src in sources:
            try:
                text = src.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if src.name == HELPER_NAME:
                continue
            # Full-line // comments can still name the module; drop them
            # before matching so docs never mark a file as spawning.
            code = "\n".join(
                line
                for line in text.splitlines()
                if not line.lstrip().startswith("//")
            )
            if SPAWN_RE.search(code):
                spawns = True
            if "safe-executable" in text and HELPER_IMPORT_RE.search(text):
                imports_helper = True
        if not spawns:
            continue
        helper = mdir / HELPER_NAME
        if not helper.is_file():
            findings.append(
                f"{rel}: limited extension spawns a process without the "
                f"shared resolver — copy adapters/shared/{HELPER_NAME} "
                f"next to the manifest and resolve through it (Windows "
                f"CreateProcess searches cwd before PATH)"
            )
        elif not imports_helper:
            findings.append(
                f"{rel}: {HELPER_NAME} present but no source imports it "
                f"— resolve spawn targets through resolveSafeExecutable"
            )
    return findings, checked


def selftest() -> int:
    failures: list[str] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'} {name}"
              f"{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    def ext_pkg(capabilities, configuration=None, engines_vscode=True):
        pkg = {"name": "demo", "main": "./extension.js",
               "engines": {"vscode": "^1.85.0"} if engines_vscode else {}}
        if capabilities is not None:
            pkg["capabilities"] = capabilities
        if configuration is not None:
            pkg["contributes"] = {"configuration": {
                "title": "demo", "properties": configuration}}
        return pkg

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # clean: limited with every contributed+read key restricted
        clean = base / "clean/adapters/vscode"
        clean.mkdir(parents=True)
        (clean / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable", "demo.extraArgs"]}},
            {"demo.executable": {"type": "string"},
             "demo.extraArgs": {"type": "array"}})))
        (clean / "extension.js").write_text(
            'const c = require("vscode").workspace.getConfiguration("demo");\n'
            'const exe = c.get("executable");\nconst extra = c.get("extraArgs");\n')

        # no-declaration: engines.vscode but no capabilities
        nodecl = base / "nodecl/adapters/vscode"
        nodecl.mkdir(parents=True)
        (nodecl / "package.json").write_text(json.dumps(ext_pkg(None)))
        (nodecl / "extension.js").write_text("// nothing\n")

        # gap: contributed key missing from restrictedConfigurations
        gap = base / "gap/adapters/vscode"
        gap.mkdir(parents=True)
        (gap / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable"]}},
            {"demo.executable": {"type": "string"},
             "demo.extraArgs": {"type": "array"}})))
        (gap / "extension.js").write_text(
            'const c = require("vscode").workspace.getConfiguration("demo");\n'
            'const exe = c.get("executable");\n')

        # srcgap: key read in source, neither contributed nor restricted
        srcgap = base / "srcgap/adapters/vscode"
        srcgap.mkdir(parents=True)
        (srcgap / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable"]}},
            {"demo.executable": {"type": "string"}})))
        (srcgap / "extension.js").write_text(
            'const c = require("vscode").workspace.getConfiguration("demo");\n'
            'const exe = c.get("executable");\n'
            'const onstart = c.get("checkOnStartup");\n')

        # supported: declared true — no configuration rule
        supported = base / "supported/adapters/vscode"
        supported.mkdir(parents=True)
        (supported / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {"supported": True}})))
        (supported / "extension.js").write_text("// ui only\n")

        # badvalue: supported: "true" string is not the accepted shape
        badvalue = base / "badvalue/adapters/vscode"
        badvalue.mkdir(parents=True)
        (badvalue / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {"supported": "true"}})))
        (badvalue / "extension.js").write_text("// ui only\n")

        # unscoped: getConfiguration() with no literal namespace
        unscoped = base / "unscoped/adapters/vscode"
        unscoped.mkdir(parents=True)
        (unscoped / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable"]}},
            {"demo.executable": {"type": "string"}})))
        (unscoped / "extension.js").write_text(
            'const c = require("vscode").workspace.getConfiguration();\n'
            'const exe = c.get("demo.executable");\n')

        # helper-required: limited + child_process without the shared
        # resolver is a violation (the Windows cwd-search vector)
        nohelp = base / "nohelp/adapters/vscode"
        nohelp.mkdir(parents=True)
        (nohelp / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable"]}},
            {"demo.executable": {"type": "string"}})))
        (nohelp / "extension.js").write_text(
            'const cp = require("child_process");\n'
            'cp.execFile("demo", [], {cwd: "/x"}, () => {});\n')

        # helper-ok: limited + spawn resolved through the shared helper
        canonical_src = canonical_helper(base.parent) or (
            Path(__file__).resolve().parent.parent
            / "adapters" / "shared" / HELPER_NAME)
        helperok = base / "helperok/adapters/vscode"
        helperok.mkdir(parents=True)
        (helperok / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable"]}},
            {"demo.executable": {"type": "string"}})))
        (helperok / "extension.js").write_text(
            'const cp = require("child_process");\n'
            'const { resolveSafeExecutable } = require("./safe-executable.cjs");\n')
        (helperok / HELPER_NAME).write_bytes(canonical_src.read_bytes())

        # commented: naming child_process in a comment is not spawning
        commented = base / "commented/adapters/vscode"
        commented.mkdir(parents=True)
        (commented / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable"]}},
            {"demo.executable": {"type": "string"}})))
        (commented / "extension.js").write_text(
            '// we never call child_process or execFile here\n'
            'const x = 1;\n')

        # helper-drift: a mutated copy is a finding
        helperdrift = base / "helperdrift/adapters/vscode"
        helperdrift.mkdir(parents=True)
        (helperdrift / "package.json").write_text(json.dumps(ext_pkg(
            {"untrustedWorkspaces": {
                "supported": "limited",
                "restrictedConfigurations": ["demo.executable"]}},
            {"demo.executable": {"type": "string"}})))
        (helperdrift / "extension.js").write_text(
            'const cp = require("child_process");\n'
            'const { resolveSafeExecutable } = require("./safe-executable.cjs");\n')
        (helperdrift / HELPER_NAME).write_bytes(
            canonical_src.read_bytes() + b"// drifted\n")

        for name, expect_findings in (
            ("clean", 0), ("nodecl", 1), ("gap", 1), ("srcgap", 1),
            ("supported", 0), ("badvalue", 1), ("unscoped", 1),
            ("nohelp", 1), ("helperok", 0), ("helperdrift", 1),
            ("commented", 0),
        ):
            findings, _ = run(base / name)
            expect(name, len(findings) == expect_findings,
                   "; ".join(findings) if findings else "")

        # non-vscode package.json must be ignored entirely
        plain = base / "plain/pkg"
        plain.mkdir(parents=True)
        (plain / "package.json").write_text(json.dumps(
            {"name": "not-an-extension", "engines": {"node": ">=18"}}))
        findings, checked = run(base / "plain")
        expect("non-vscode manifest ignored", checked == 0 and not findings)

    if failures:
        print(f"selftest: {len(failures)} failure(s)")
        return 1
    print("selftest: all fixtures behaved as expected")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".",
                    help="repo root to scan (default: %(default)s)")
    ap.add_argument("--selftest", action="store_true",
                    help="run the scanner against synthetic fixtures and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    root = Path(args.root).resolve()
    findings, checked = run(root)
    manifests = sum(1 for _ in extension_manifests(root))
    if manifests == 0:
        print("config-restricted-check: no VS Code extension manifests "
              "found — skipped.")
        return 0
    if findings:
        for line in findings:
            print(line)
        print(f"::error::config-restricted-check found {len(findings)} "
              f"violation(s). Declare untrustedWorkspaces, or restrict the "
              f"key in capabilities.untrustedWorkspaces.restrictedConfigurations.",
              file=sys.stderr)
        return 1
    print(f"config-restricted-check: {checked}/{manifests} VS Code "
          f"extension manifest(s) clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

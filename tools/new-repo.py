#!/usr/bin/env python3
"""new-repo.py — bootstrap a new devin-* repo from template/.

Usage:
    python tools/new-repo.py [options] <name> "<description>"

Example:
    python tools/new-repo.py history "Session history exporter..."
    python tools/new-repo.py --dry-run history "Session history exporter..."

Creates ../devin-<name>/ next to this repo, fills {{name}} / {{module}} /
{{description}} placeholders, renames src/devin_template -> src/devin_<module>,
and runs `git init -b main`. Unless --no-register is given, it also appends a
registry entry to registry.json — the merged document is validated against
registry.schema.json *before* anything is written, and registry.json is only
updated after the scaffold + git init succeed (atomic write). Does NOT create
the GitHub remote — do that with:
    gh repo create Icaro0310/devin-<name> --public --source=. --push

Exit codes: 0 ok · 1 validation drift (name, schema) or git failure ·
2 input/file problem (missing template, unreadable registry, existing dest).
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
ECOSYSTEM = HUB.parent
TEMPLATE = HUB / "template"
REGISTRY_PATH = HUB / "registry.json"
SCHEMA_PATH = HUB / "registry.schema.json"

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}


def fill(text: str, name: str, module: str, description: str) -> str:
    return (
        text.replace("{{name}}", name)
        .replace("{{module}}", module)
        .replace("{{description}}", description)
        .replace("devin_template", f"devin_{module}")
    )


def template_files(template_dir: Path, module: str) -> list[tuple[Path, str]]:
    """Return ``(source, destination-relative-name)`` pairs for the template."""
    files = []
    for src in sorted(Path(template_dir).rglob("*")):
        if any(part in SKIP_DIRS for part in src.parts) or src.is_dir():
            continue
        rel = src.relative_to(template_dir)
        files.append(
            (src, str(rel).replace("devin_template", f"devin_{module}"))
        )
    return files


def scaffold(
    template_dir: Path, dest: Path, name: str, module: str, description: str
) -> list[str]:
    """Copy the template into ``dest``; returns the relative file names."""
    written = []
    for src, rel_str in template_files(template_dir, module):
        dst = dest / rel_str
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = src.read_text(encoding="utf-8")
            dst.write_text(fill(content, name, module, description),
                           encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src, dst)
        written.append(rel_str)
    return written


def _load_validator(tools_dir: Path):
    """Import the sibling validate_registry.py by file location."""
    spec = importlib.util.spec_from_file_location(
        "validate_registry", tools_dir / "validate_registry.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_entry(
    name: str,
    description: str,
    owner: str,
    kind: str = "project",
    visibility: str = "public",
    wave: int = 0,
) -> dict:
    """Registry entry for a freshly scaffolded ``devin-<name>`` checkout."""
    artifact = {
        "project": "tool",
        "infra": "infrastructure",
        "distribution": "distribution",
        "system": "system",
    }[kind]
    interfaces = {
        "project": ["cli"],
        "infra": ["cli", "registry"],
        "distribution": ["cli", "installer"],
        "system": ["automation"],
    }[kind]
    audiences = {
        "project": ["developers"],
        "infra": ["maintainers"],
        "distribution": ["developers", "end-users"],
        "system": ["maintainers"],
    }[kind]
    return {
        "name": f"devin-{name}",
        "url": f"https://github.com/{owner}/devin-{name}",
        "kind": kind,
        "artifact": artifact,
        "interfaces": interfaces,
        "audiences": audiences,
        "platforms": ["windows", "linux"],
        "visibility": visibility,
        "wave": wave,
        "status": "active",
        "stack": "python",
        "local_dir": f"../devin-{name}",
        "description": description,
    }


def merge_registry(registry_path: Path, entry: dict) -> dict:
    """Return the registry document with ``entry`` appended.

    Refuses duplicate names and bumps the ``generated`` date. Raises
    ValueError on unreadable/malformed input — nothing is written here.
    """
    registry_path = Path(registry_path)
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {registry_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{registry_path}: invalid JSON: {exc}") from exc
    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError(f"{registry_path}: 'repositories' must be a list")
    known = {
        item.get("name")
        for item in repositories
        if isinstance(item, dict)
    }
    if entry["name"] in known:
        raise ValueError(
            f"{registry_path}: '{entry['name']}' is already registered"
        )
    registry["repositories"] = [*repositories, entry]
    registry["generated"] = date.today().isoformat()
    return registry


def write_registry(registry_path: Path, registry: dict) -> None:
    """Atomically replace ``registry_path`` with the merged document."""
    registry_path = Path(registry_path)
    tmp = registry_path.with_suffix(registry_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, registry_path)


def _git_init(dest: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=dest, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="new-repo.py",
        description=__doc__.splitlines()[0],
    )
    parser.add_argument(
        "name",
        help="kebab-case repo name; the devin- prefix is optional",
    )
    parser.add_argument("description", help="one-line project description")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be created/registered; create nothing",
    )
    parser.add_argument(
        "--no-register",
        action="store_true",
        help="scaffold only; do not touch registry.json",
    )
    parser.add_argument(
        "--kind",
        choices=["project", "infra", "system"],
        default="project",
        help="registry kind for the new entry (default: project)",
    )
    parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
        help="registry visibility for the new entry (default: public)",
    )
    parser.add_argument(
        "--wave",
        type=int,
        default=0,
        help="registry delivery wave (default: 0 = standalone)",
    )
    parser.add_argument(
        "--registry",
        default=str(REGISTRY_PATH),
        help="registry JSON to update (default: this repo's registry.json)",
    )
    parser.add_argument(
        "--schema",
        default=str(SCHEMA_PATH),
        help="JSON Schema to validate the merged registry against",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    name = args.name.removeprefix("devin-")
    if not re.fullmatch(r"[a-z0-9-]+", name):
        print(f"error: invalid name: {name!r} (kebab-case only)",
              file=sys.stderr)
        return 1
    if args.wave < 0:
        print("error: --wave must be >= 0", file=sys.stderr)
        return 1
    module = name.replace("-", "_")
    dest = ECOSYSTEM / f"devin-{name}"
    if dest.exists():
        print(f"error: already exists: {dest}", file=sys.stderr)
        return 2
    if not TEMPLATE.is_dir():
        print(f"error: template dir not found: {TEMPLATE}", file=sys.stderr)
        return 2

    files = template_files(TEMPLATE, module)

    # Resolve the registration up-front: the merged registry is validated
    # before anything is created or written, so a schema violation fails
    # fast with zero side effects.
    registry_path = Path(args.registry)
    merged = None
    entry = None
    if not args.no_register:
        try:
            schema = json.loads(
                Path(args.schema).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot load schema {args.schema}: {exc}",
                  file=sys.stderr)
            return 2
        owner = None
        try:
            owner = json.loads(
                registry_path.read_text(encoding="utf-8")
            ).get("owner")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read {registry_path}: {exc}",
                  file=sys.stderr)
            return 2
        if not isinstance(owner, str) or not owner:
            print(f"error: {registry_path}: missing 'owner' field",
                  file=sys.stderr)
            return 2
        entry = build_entry(
            name, args.description, owner,
            kind=args.kind, visibility=args.visibility, wave=args.wave,
        )
        try:
            merged = merge_registry(registry_path, entry)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        errors = _load_validator(Path(__file__).resolve().parent).validate(
            merged, schema
        )
        if errors:
            print(
                f"error: merged registry fails {args.schema} "
                f"({len(errors)} violation(s)):",
                file=sys.stderr,
            )
            for error in errors:
                print(f"  {error}", file=sys.stderr)
            return 1

    if args.dry_run:
        print(f"dry-run: would scaffold {dest} from {TEMPLATE} "
              f"({len(files)} files):")
        for _, rel_str in files:
            print(f"  create {rel_str}")
        print(f"would run: git init -b main  (cwd={dest})")
        if entry is not None:
            print(f"would append to {registry_path} "
                  "(schema-validated before write):")
            print(json.dumps(entry, indent=2, ensure_ascii=False))
        else:
            print("would NOT touch registry.json (--no-register)")
        print("dry-run: nothing was created or modified")
        return 0

    scaffold(TEMPLATE, dest, name, module, args.description)
    try:
        _git_init(dest)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"error: git init failed in {dest}: {exc}", file=sys.stderr)
        print("note: registry.json was left unchanged", file=sys.stderr)
        return 1

    if merged is not None:
        try:
            write_registry(registry_path, merged)
        except OSError as exc:
            print(f"error: cannot write {registry_path}: {exc}",
                  file=sys.stderr)
            print("note: scaffold succeeded; register the repo manually",
                  file=sys.stderr)
            return 2
        print(f"registered devin-{name} in {registry_path}")

    print(f"created {dest}")
    print(f"next: cd {dest} && git add -A && git commit -m init && "
          f"gh repo create Icaro0310/devin-{name} --public --source=. --push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

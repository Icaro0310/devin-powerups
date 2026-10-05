#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
REGISTRY = HUB / "registry.json"
ENVIRONMENTS = ["linux", "personal_windows", "corporate_windows"]
LABELS = {
    "linux": "Linux",
    "personal_windows": "Personal Windows",
    "corporate_windows": "Corporate Windows",
}


def _escape(value: str) -> str:
    return " ".join(value.replace("|", "\\|").split())


def _cell(metadata: dict | None) -> str:
    if not metadata:
        return "N/A"
    if not metadata.get("supported"):
        return "Unsupported"
    if metadata.get("runtime") == "extended":
        return "Extended"
    if metadata.get("runtime") == "local-only":
        return "Local only"
    return "Supported"


def render_compatibility_matrix(registry: dict) -> str:
    executable = {"tool", "service", "suite", "distribution", "infrastructure"}
    repos = [
        repo for repo in registry["repositories"]
        if repo.get("visibility") == "public" and repo.get("artifact") in executable
    ]
    lines = [
        "| Artifact | Linux | Personal Windows | Corporate Windows |",
        "|---|---|---|---|",
    ]
    for repo in repos:
        environments = repo.get("environments", {})
        cells = [_cell(environments.get(name)) for name in ENVIRONMENTS]
        lines.append(f"| [`{repo['name']}`]({repo['url']}) | " + " | ".join(cells) + " |")
    lines.extend([
        "",
        "`Extended` means local execution plus optional delegated workloads when the selected tool supports them. `Local only` means the tool works without a VM, QwenPaw, external compute, workload delegation, or required external integrations. `Unsupported` values include an explicit reason in `registry.json`.",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the registry-derived environment compatibility matrix.")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args(argv)

    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        rendered = render_compatibility_matrix(registry) + "\n"
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            current = args.check.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read {args.check}: {exc}", file=sys.stderr)
            return 1
        if rendered.rstrip() not in current:
            print(f"stale compatibility matrix: {args.check}", file=sys.stderr)
            return 1
        print(f"ok: compatibility matrix in {args.check} matches registry.json")
        return 0

    if args.out:
        try:
            args.out.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

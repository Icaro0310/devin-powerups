#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import validate_registry

HUB = Path(__file__).resolve().parent.parent
DEFAULT_OUT = HUB.parent / "devin-devkit" / "packages" / "devkit" / "src" / "devin_devkit" / "manifest.json"
_SHA = re.compile(r"^[0-9a-f]{40}$")


class ManifestError(ValueError):
    pass


def _repository_index(registry: dict) -> dict[str, dict]:
    return {item["name"]: item for item in registry.get("repositories", [])}


def validate_devkit(registry: dict) -> list[str]:
    schema = json.loads((HUB / "registry.schema.json").read_text(encoding="utf-8"))
    errors = validate_registry.registry_errors(registry, schema)
    if errors:
        return errors

    repos = _repository_index(registry)
    devkit = registry["devkit"]
    tools = devkit["tools"]
    spec_git = {
        name
        for name, tool in tools.items()
        if (repo := repos.get(name)) is not None and _needs_git(tool, repo)
    }
    declared_git = set(devkit.get("git_required_tools", []))
    if declared_git != spec_git:
        errors.append(
            "devkit.git_required_tools must match the tools whose install spec "
            f"needs Git: missing={sorted(spec_git - declared_git)}, "
            f"extra={sorted(declared_git - spec_git)}"
        )
    for name, tool in tools.items():
        repo = repos.get(name)
        if repo is None:
            errors.append(f"devkit.tools.{name}: missing repository entry")
        elif repo.get("visibility") != "public" or repo.get("kind") != "project":
            errors.append(f"devkit.tools.{name}: must refer to a public project")
        else:
            environments = repo.get("environments", {})
            for environment_name in ("linux", "personal_windows", "corporate_windows"):
                if environment_name not in environments:
                    errors.append(f"devkit.tools.{name}: missing environment {environment_name}")
            corporate = environments.get("corporate_windows", {})
            if corporate.get("supported") and corporate.get("delegation") not in {"forbidden", "unavailable"}:
                errors.append(f"devkit.tools.{name}: corporate_windows must forbid delegation")
            if corporate.get("supported") and corporate.get("external_dependencies"):
                errors.append(f"devkit.tools.{name}: corporate_windows cannot depend on external integrations")
        if tool["source"] == "github" and not _SHA.fullmatch(tool.get("ref", "")):
            errors.append(f"devkit.tools.{name}.ref: expected a 40-character commit SHA")
        if tool["source"] == "pypi" and tool["manager"] != "uv":
            errors.append(f"devkit.tools.{name}: PyPI packages must use uv")
        if tool["manager"] == "manual" and tool["status"] != "manual":
            errors.append(f"devkit.tools.{name}: manual manager must have manual status")

    for profile_name, profile in devkit["profiles"].items():
        for name in profile.get("tools", []):
            if name not in tools:
                errors.append(f"devkit.profiles.{profile_name}: unknown tool {name}")
            elif tools[name]["status"] == "manual":
                errors.append(f"devkit.profiles.{profile_name}: {name} is manual, list it under manual")
        for name in profile.get("manual", []):
            if name not in tools or tools[name]["status"] != "manual":
                errors.append(f"devkit.profiles.{profile_name}: {name} is not a manual tool")
        alias = profile.get("alias_of")
        if alias and alias not in devkit["profiles"]:
            errors.append(f"devkit.profiles.{profile_name}: unknown alias target {alias}")

    first_party = {
        name for name, repo in repos.items()
        if name.startswith("devin-") and name != "devin-powerups"
        and repo.get("visibility") == "public" and repo.get("kind") == "project"
    }
    declared = {name for name in tools if name.startswith("devin-") and name != "devin-powerups"}
    if first_party != declared:
        errors.append(
            "devkit.tools does not match public first-party Devin tools: "
            f"missing={sorted(first_party - declared)}, extra={sorted(declared - first_party)}"
        )
    return errors


def _install_spec(tool: dict, repo: dict) -> str | None:
    source = tool["source"]
    if source == "manual":
        return None
    if source == "pypi":
        extras = tool.get("extras", [])
        suffix = f"[{','.join(extras)}]" if extras else ""
        return f"{tool['package']}{suffix}=={tool['version']}"
    if source == "npm":
        return f"{tool['package']}@{tool['version']}"
    pkg_path = (repo.get("package") or {}).get("path")
    if pkg_path:
        return f"git+{repo['url']}.git@{tool['ref']}#subdirectory={pkg_path}"
    return f"{repo['url']}/archive/{tool['ref']}.tar.gz"


def _needs_git(tool: dict, repo: dict) -> bool:
    # Skip spec derivation when the ref is missing or invalid — validate_devkit
    # already reports that error; indexing tool["ref"] here would KeyError first.
    if tool.get("source") == "github" and not _SHA.fullmatch(tool.get("ref", "")):
        return False
    spec = _install_spec(tool, repo)
    return bool(spec) and spec.startswith("git+")


def build_manifest(registry: dict) -> dict:
    errors = validate_devkit(registry)
    if errors:
        raise ManifestError("\n".join(errors))

    devkit = registry["devkit"]
    git_required = set(devkit.get("git_required_tools", []))
    repos = _repository_index(registry)
    tools = []
    for name, tool in devkit["tools"].items():
        repo = repos[name]
        install_spec = _install_spec(tool, repo)
        tools.append({
            "id": name,
            "label": name,
            "description": repo["description"],
            "category": tool["category"],
            "artifact": repo["artifact"],
            "interfaces": repo["interfaces"],
            "audiences": repo["audiences"],
            "environments": repo["environments"],
            "manager": tool["manager"],
            "source": tool["source"],
            "package": tool["package"],
            "version": tool["version"],
            "commands": tool["commands"],
            "runtime": tool["runtime"],
            "platforms": tool["platforms"],
            "requires_git": bool(install_spec) and install_spec.startswith("git+"),
            "status": tool["status"],
            "extras": tool.get("extras", []),
            "manual_note": tool.get("manual_note"),
            "install_spec": install_spec,
        })

    public_repos = [r for r in registry["repositories"] if r.get("visibility") == "public"]
    devin_tools = [
        r for r in public_repos
        if r.get("kind") == "project" and r["name"].startswith("devin-")
        and r["name"] != "devin-powerups"
    ]
    hubs = [r for r in public_repos if r.get("kind") == "infra"]
    distributions = [r for r in public_repos if r.get("kind") == "distribution"]
    related = [r for r in public_repos if r.get("kind") == "project" and not r["name"].startswith("devin-")]

    return {
        "schema": "devin-devkit-manifest/0.1",
        "registry_version": registry["version"],
        "generated": registry["generated"],
        "installer": devkit["installer"],
        "supported_platforms": devkit["supported_platforms"],
        "planned_platforms": devkit["planned_platforms"],
        "environments": registry["environments"],
        "git_required_tools": sorted(git_required),
        "catalog": {
            "tool_count": len(devin_tools),
            "distribution_count": len(distributions),
            "hub_count": len(hubs),
            "related_count": len(related),
            "entry_count": len(public_repos),
        },
        "profiles": devkit["profiles"],
        "tools": tools,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the public DevKit manifest from registry.json.")
    parser.add_argument("--registry", type=Path, default=HUB / "registry.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        manifest = build_manifest(registry)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        try:
            current = args.out.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read {args.out}: {exc}", file=sys.stderr)
            return 1
        if current != rendered:
            print(f"stale manifest: {args.out}", file=sys.stderr)
            return 1
        print(f"ok: {args.out} matches registry.json ({manifest['catalog']['tool_count']} tools)")
        return 0

    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=args.out.parent, delete=False
        ) as handle:
            handle.write(rendered)
            tmp = Path(handle.name)
        os.replace(tmp, args.out)
    except OSError as exc:
        print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {args.out}: {manifest['catalog']['tool_count']} tools, {len(manifest['profiles'])} profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

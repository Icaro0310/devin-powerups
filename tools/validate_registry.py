#!/usr/bin/env python3
"""validate_registry.py — validate registry.json against registry.schema.json.

Dependency-free (stdlib only): implements the JSON Schema draft 2020-12 subset
used by registry.schema.json:

    type, enum, const, required, properties, additionalProperties, items,
    minItems, minProperties, minLength, pattern, minimum, $ref (local),
    allOf, anyOf, not, if/then/else

Annotation keywords ($schema, $id, $defs, $comment, title, description,
default, examples, deprecated) are accepted and ignored. Any other keyword makes
the schema check fail instead of being skipped silently, so a constraint
written into the schema can never go unenforced. (An earlier version ignored
unknown keywords, which hid a real violation behind an ``if``/``then`` rule.)

On top of the schema, ``semantic_errors`` checks the rules JSON Schema cannot
express across entries: unique names and exactly one control-plane entry.
``registry_errors`` combines both layers (schema first, cross-entry rules only
on a structurally valid document); consumers such as ``new-repo.py`` and
``export_devkit_manifest.py`` validate through it, not through ``validate``
alone.

Usage:
    python tools/validate_registry.py [registry.json] [--schema registry.schema.json]

Exit codes: 0 = valid, 1 = validation errors, 2 = file/JSON/schema problems.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent

ANNOTATIONS = frozenset({
    "$schema", "$id", "$defs", "$comment", "title", "description",
    "default", "examples", "deprecated",
})
SUPPORTED = frozenset({
    "type", "enum", "const", "required", "properties", "additionalProperties",
    "items", "minItems", "minProperties", "minLength", "pattern", "minimum",
    "$ref", "allOf", "anyOf", "not", "if", "then", "else",
})

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _type_name(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "null"


def _same(a, b) -> bool:
    """JSON equality: ``True`` is not ``1`` and ``1`` is not ``"1"``."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def _resolve(ref: str, root: dict):
    """Resolve a local ``#/a/b`` JSON pointer; raise KeyError when missing."""
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def check_schema(schema, root: dict | None = None, path: str = "#") -> list[str]:
    """Return problems that would make ``validate`` skip or misread a schema."""
    root = schema if root is None else root
    if not isinstance(schema, dict):
        return [f"{path}: schema node is not an object"]
    problems: list[str] = []
    for key, value in schema.items():
        if key in ANNOTATIONS:
            if key == "$defs":
                if isinstance(value, dict):
                    for name, sub in value.items():
                        problems.extend(check_schema(sub, root, f"{path}/$defs/{name}"))
                else:
                    problems.append(f"{path}: '$defs' must be an object")
            continue
        if key not in SUPPORTED:
            problems.append(f"{path}: unsupported schema keyword {key!r}")
        elif key == "type":
            names = value if isinstance(value, list) else [value]
            if not names or not all(
                isinstance(name, str) and name in _TYPE_CHECKS for name in names
            ):
                problems.append(f"{path}: malformed or unsupported 'type' {value!r}")
        elif key == "properties":
            if isinstance(value, dict):
                for name, sub in value.items():
                    problems.extend(check_schema(sub, root, f"{path}/properties/{name}"))
            else:
                problems.append(f"{path}: 'properties' must be an object")
        elif key in ("items", "not", "if", "then", "else"):
            problems.extend(check_schema(value, root, f"{path}/{key}"))
        elif key == "additionalProperties":
            if isinstance(value, dict):
                problems.extend(check_schema(value, root, f"{path}/{key}"))
            elif not isinstance(value, bool):
                problems.append(f"{path}: 'additionalProperties' must be a schema or boolean")
        elif key in ("allOf", "anyOf"):
            if isinstance(value, list):
                for index, sub in enumerate(value):
                    problems.extend(check_schema(sub, root, f"{path}/{key}/{index}"))
            else:
                problems.append(f"{path}: {key!r} must be an array of schemas")
        elif key == "enum":
            if not isinstance(value, list) or not value:
                problems.append(f"{path}: 'enum' must be a non-empty array")
        elif key == "required":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                problems.append(f"{path}: 'required' must be an array of strings")
        elif key in ("minItems", "minProperties", "minLength"):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                problems.append(f"{path}: {key!r} must be a non-negative integer")
        elif key == "minimum":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                problems.append(f"{path}: 'minimum' must be a number")
        elif key == "pattern":
            if not isinstance(value, str):
                problems.append(f"{path}: 'pattern' must be a string")
            else:
                try:
                    re.compile(value)
                except re.error:
                    problems.append(f"{path}: 'pattern' is not a valid regex {value!r}")
        elif key == "$ref":
            if not (isinstance(value, str) and value.startswith("#/")):
                problems.append(f"{path}: only local '#/...' $ref is supported, got {value!r}")
            else:
                try:
                    _resolve(value, root)
                except (KeyError, TypeError):
                    problems.append(f"{path}: $ref {value!r} does not resolve")
    return problems


def validate(instance, schema: dict, path: str = "$", root: dict | None = None) -> list[str]:
    """Return a list of validation errors (empty = valid).

    ``path`` is a JSONPath-ish locator such as ``$.repositories[3].status``
    so each error points at the offending value. ``root`` is the document
    ``$ref`` pointers resolve against; it defaults to ``schema``.
    """
    root = schema if root is None else root
    errors: list[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: schema node is not an object"]

    if "$ref" in schema:
        try:
            target = _resolve(schema["$ref"], root)
        except (KeyError, TypeError):
            errors.append(f"{path}: cannot resolve $ref {schema['$ref']!r}")
        else:
            errors.extend(validate(instance, target, path, root))

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        unknown = [t for t in types if t not in _TYPE_CHECKS]
        if unknown:
            errors.append(f"{path}: unsupported schema type {unknown[0]!r}")
            return errors
        if not any(_TYPE_CHECKS[t](instance) for t in types):
            errors.append(
                f"{path}: expected type {'/'.join(types)}, got {_type_name(instance)}"
            )
            return errors  # type mismatch — deeper checks would be noise

    if "enum" in schema and not any(_same(instance, option) for option in schema["enum"]):
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")

    if "const" in schema and not _same(instance, schema["const"]):
        errors.append(f"{path}: expected {schema['const']!r}, got {instance!r}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], f"{path}.{key}", root))
            elif additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(validate(value, additional, f"{path}.{key}", root))
        min_props = schema.get("minProperties")
        if min_props is not None and len(instance) < min_props:
            errors.append(f"{path}: has {len(instance)} properties, minimum is {min_props}")

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate(item, item_schema, f"{path}[{index}]", root))
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path}: has {len(instance)} items, minimum is {min_items}")

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            errors.append(f"{path}: string shorter than minLength {min_length}")
        pattern = schema.get("pattern")
        if pattern is not None and not re.search(pattern, instance):
            errors.append(f"{path}: {instance!r} does not match /{pattern}/")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: {instance!r} is below minimum {minimum}")

    for sub in schema.get("allOf", []):
        errors.extend(validate(instance, sub, path, root))

    if "anyOf" in schema:
        if all(validate(instance, sub, path, root) for sub in schema["anyOf"]):
            errors.append(f"{path}: does not match any allowed alternative")

    if "not" in schema and not validate(instance, schema["not"], path, root):
        errors.append(f"{path}: matches a schema it must not match")

    if "if" in schema:
        matched = not validate(instance, schema["if"], path, root)
        branch = schema.get("then") if matched else schema.get("else")
        if branch is not None:
            note = f" [rule: {schema['description']}]" if "description" in schema else ""
            errors.extend(f"{error}{note}" for error in validate(instance, branch, path, root))

    return errors


def journey_errors(registry: dict) -> list[str]:
    """``journeys`` steps must point at existing public entries whose
    ``audiences`` declare the journey's audience key. (Unknown audience
    keys are already rejected by the schema's ``properties`` map.)"""
    errors: list[str] = []
    repositories = registry.get("repositories") if isinstance(registry, dict) else None
    entries = {e.get("name"): e for e in repositories or [] if isinstance(e, dict)}
    journeys = registry.get("journeys")
    if not isinstance(journeys, dict):
        return errors
    for audience, steps in journeys.items():
        for step in steps or []:
            if not isinstance(step, dict):
                continue
            name = step.get("repo")
            entry = entries.get(name)
            if entry is None:
                errors.append(f"$.journeys.{audience}: unknown repo {name!r}")
            elif entry.get("visibility") != "public" or entry.get("public") is False:
                errors.append(f"$.journeys.{audience}: repo {name!r} is not public")
            elif audience not in (entry.get("audiences") or []):
                errors.append(
                    f"$.journeys.{audience}: {name!r} does not declare audience {audience!r}"
                )
    return errors


_MODE_ORDER = {"read": 0, "mixed": 1, "write": 2}
_MAX_PRODUCTS = 7
_READ_ONLY_JOBS = {"understand", "verify"}
_PRODUCT_JOBS = {"understand", "verify", "control", "build"}


def _checkout(entry: dict, root: Path) -> Path | None:
    local_dir = entry.get("local_dir")
    path = (root / (local_dir if local_dir else entry.get("name", ""))).resolve()
    return path if path.is_dir() else None


def _declared_entrypoints(checkout: Path, package: dict | None) -> set[str] | None:
    """console_scripts / bin names declared by the checkout's manifest.

    ``package.path`` selects the manifest inside the checkout (workspace
    monorepos keep each package below the root). None = the manifest
    could not be parsed; the caller must fail rather than skip.
    """
    manifest_dir = checkout
    if isinstance(package, dict) and package.get("path"):
        manifest_dir = (checkout / package["path"]).resolve()
    pyproject = manifest_dir / "pyproject.toml"
    package_json = manifest_dir / "package.json"
    if pyproject.exists():
        try:
            import tomllib
            project = tomllib.loads(pyproject.read_text()).get("project", {})
            return set(project.get("scripts", {}))
        except Exception:
            return None
    if package_json.exists():
        try:
            return set(json.loads(package_json.read_text()).get("bin", {}))
        except Exception:
            return None
    return set()


def product_errors(registry: dict, root: Path | None = None) -> list[str]:
    """Registry v21 product rules (D-2026-10-09), fail-closed.

    ``root`` is the parent of the local checkouts (the directory
    ``local_dir`` is resolved against); when None the checkout-dependent
    checks are skipped so synthetic registries can be validated without a
    filesystem.
    """
    errors: list[str] = []
    repos = registry.get("repositories") if isinstance(registry, dict) else None
    entries = [e for e in repos or [] if isinstance(e, dict)]
    by_name = {e.get("name"): e for e in entries}

    products: dict[str, list[dict]] = {}
    for e in entries:
        pid = e.get("product_id")
        if pid:
            products.setdefault(pid, []).append(e)

    # product cap
    if len(products) > _MAX_PRODUCTS:
        errors.append(
            f"$.repositories: {len(products)} distinct product_id values, maximum is {_MAX_PRODUCTS} ({sorted(products)})"
        )

    for e in entries:
        name = e.get("name")
        own = e.get("ownership")
        pid = e.get("product_id")
        job = e.get("job")
        pkg = e.get("package")
        eps = e.get("entrypoints") or []
        legacy = e.get("legacy")

        # product_id is only for first-party product members
        if pid is not None and own != "first_party":
            errors.append(f"$.repositories[{name}]: product_id {pid!r} on ownership {own!r} (only first_party)")
        # first-party entries must belong to a product — except the control plane
        if own == "first_party" and pid is None and e.get("is_control_plane") is not True:
            errors.append(f"$.repositories[{name}]: ownership 'first_party' without product_id or is_control_plane")
        # job is a product property: set together with product_id, null together
        if (job is None) != (pid is None):
            errors.append(f"$.repositories[{name}]: job {job!r} and product_id {pid!r} must both be set or both be null")
        # entrypoints require a package; a package implies declared entrypoints exist on disk
        if pkg is None and eps:
            errors.append(f"$.repositories[{name}]: entrypoints {eps} declared but package is null")

        # entrypoints must exist in the real manifest
        if root is not None and eps:
            co = _checkout(e, root)
            if co is not None:
                real = _declared_entrypoints(co, pkg)
                if real is None:
                    errors.append(
                        f"$.repositories[{name}]: cannot parse {co.name}'s package manifest"
                    )
                else:
                    missing = sorted(set(eps) - real)
                    if missing:
                        errors.append(
                            f"$.repositories[{name}]: entrypoints {missing} not found in {co.name}'s manifest"
                        )

        # legacy lineage must point at real objects
        if isinstance(legacy, dict):
            old = legacy.get("repo")
            status = legacy.get("status")
            to = legacy.get("to")
            if status == "renamed":
                if old == name:
                    errors.append(f"$.repositories[{name}]: legacy.repo equals the current name")
                if old in by_name:
                    errors.append(f"$.repositories[{name}]: legacy.repo {old!r} still exists as an entry")
            if status in ("archived", "superseded") and to is not None:
                if to not in by_name and to not in products:
                    errors.append(f"$.repositories[{name}]: legacy.to {to!r} is not an entry or product")

    # per-product invariants
    pkg_names: dict[str, str] = {}
    for pid, members in products.items():
        jobs = {m.get("job") for m in members}
        if len(jobs) != 1:
            errors.append(f"product {pid!r}: members declare different jobs {sorted(jobs, key=str)}")
        job = jobs.pop() if jobs else None
        # understand/verify products may only contain read members
        if job in _READ_ONLY_JOBS:
            for m in members:
                mode = m.get("mode")
                if mode is not None and mode != "read":
                    errors.append(
                        f"product {pid!r}: member {m.get('name')!r} has mode {mode!r} but job {job!r} requires read"
                    )
        # every product needs at least one publishable package
        if not any(m.get("package") for m in members):
            errors.append(f"product {pid!r}: no member declares a package")
        for m in members:
            pkg = m.get("package")
            if isinstance(pkg, dict):
                pname = pkg.get("name")
                holder = pkg_names.get(pname)
                # package names are globally unique — a second claimant
                # in the *same* product is just as ambiguous as cross-product
                if holder is not None and holder != m.get("name"):
                    errors.append(
                        f"package {pname!r} claimed by both {holder!r} and {m.get('name')!r}"
                    )
                pkg_names[pname] = m.get("name")

    # deps resolve on package names; cycles are checked per package, and
    # the published-package requirement only applies across products
    pkg_owner: dict[str, dict] = {}
    for e in entries:
        pkg = e.get("package")
        if isinstance(pkg, dict):
            pkg_owner[pkg.get("name")] = e
    dep_edges: dict[str, set[str]] = {}
    for e in entries:
        pkg = e.get("package")
        if not isinstance(pkg, dict):
            continue
        for dep in pkg.get("depends_on") or []:
            owner_entry = pkg_owner.get(dep)
            if owner_entry is None:
                errors.append(
                    f"$.repositories[{e.get('name')}]: depends_on {dep!r} is not a package in the registry"
                )
                continue
            dep_edges.setdefault(pkg.get("name"), set()).add(dep)
            if (
                owner_entry.get("product_id") != e.get("product_id")
                and owner_entry.get("distribution_status") != "published"
            ):
                errors.append(
                    f"$.repositories[{e.get('name')}]: cross-product depends_on {dep!r} but that package is {owner_entry.get('distribution_status')!r} (cross-product deps need a published package)"
                )
    for start in dep_edges:
        seen, stack = set(), [start]
        while stack:
            node = stack.pop()
            for nxt in dep_edges.get(node, ()):
                if nxt == start:
                    errors.append(f"package dependency cycle through {start!r}")
                    stack.clear()
                    break
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)

    # devkit tool commands must be declared entrypoints — for package-managed
    # tools; 'manual' tools carry invocation instructions, not console scripts
    devkit = registry.get("devkit")
    tools = devkit.get("tools") if isinstance(devkit, dict) else None
    for name, tool in (tools or {}).items():
        entry = by_name.get(name)
        if not entry or not isinstance(tool, dict):
            continue
        if tool.get("manager") not in ("uv", "npm"):
            continue
        declared = set(entry.get("entrypoints") or [])
        for cmd in tool.get("commands") or []:
            if cmd not in declared:
                errors.append(
                    f"$.devkit.tools[{name}]: command {cmd!r} not in entrypoints {sorted(declared)}"
                )
    return errors


def semantic_errors(registry: dict, root: Path | None = None) -> list[str]:
    """Cross-entry rules that JSON Schema cannot express."""
    errors: list[str] = []
    repositories = registry.get("repositories") if isinstance(registry, dict) else None
    entries = [item for item in repositories or [] if isinstance(item, dict)]
    names = [entry.get("name") for entry in entries]
    for name in sorted({n for n in names if names.count(n) > 1}, key=str):
        errors.append(f"$.repositories: duplicate name {name!r}")
    planes = [e.get("name") for e in entries if e.get("is_control_plane") is True]
    if len(planes) != 1:
        errors.append(f"$.repositories: exactly one entry must set is_control_plane=true, found {len(planes)} {planes}")
    if not isinstance(registry, dict):
        return errors
    by_name = {e.get("name"): e for e in entries}
    devkit = registry.get("devkit")
    tools = devkit.get("tools") if isinstance(devkit, dict) else None
    status_map = {"published": "published", "source": "source_only", "manual": "source_only"}
    for name, tool in (tools or {}).items():
        entry = by_name.get(name)
        if not entry or not isinstance(tool, dict):
            continue
        expected = status_map.get(tool.get("status"))
        actual = entry.get("distribution_status")
        if expected and actual and actual != expected:
            errors.append(
                f"$.repositories[{name}]: distribution_status {actual!r} disagrees with devkit.tools status {tool.get('status')!r}"
            )
    errors.extend(journey_errors(registry))
    errors.extend(product_errors(registry, root))
    return errors


def registry_errors(registry: dict, schema: dict, root: Path | None = None) -> list[str]:
    """JSON Schema plus cross-entry rules for a whole registry document.

    The cross-entry checks run only on a structurally valid document, so a
    malformed registry produces schema errors instead of crashing them.
    Embedded callers (``new-repo.py``, ``export_devkit_manifest.py``) validate
    through this entry point; the CLI exit-code mapping stays in ``main``.
    ``root`` is the checkout parent for local entrypoint verification;
    None skips filesystem-dependent checks.
    """
    errors = validate(registry, schema)
    return errors if errors else semantic_errors(registry, root)


def _load_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("registry", nargs="?", default=str(HUB / "registry.json"),
                        help="registry JSON to validate (default: this repo's registry.json)")
    parser.add_argument("--schema", default=str(HUB / "registry.schema.json"),
                        help="JSON Schema to validate against")
    args = parser.parse_args(argv)

    try:
        schema = _load_json(Path(args.schema))
        registry = _load_json(Path(args.registry))
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    problems = check_schema(schema)
    if problems:
        print(f"{args.schema}: {len(problems)} schema problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    registry_root = Path(args.registry).resolve().parent.parent
    errors = registry_errors(registry, schema, registry_root)
    if errors:
        print(f"{args.registry}: {len(errors)} validation error(s):", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    repos = registry.get("repositories", [])
    print(f"ok: {args.registry} validates against {args.schema} "
          f"({len(repos)} repositories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

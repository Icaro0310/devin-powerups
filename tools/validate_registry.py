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
express across entries.

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
            if key == "$defs" and isinstance(value, dict):
                for name, sub in value.items():
                    problems.extend(check_schema(sub, root, f"{path}/$defs/{name}"))
            continue
        if key not in SUPPORTED:
            problems.append(f"{path}: unsupported schema keyword {key!r}")
        elif key == "properties":
            for name, sub in value.items():
                problems.extend(check_schema(sub, root, f"{path}/properties/{name}"))
        elif key in ("items", "not", "if", "then", "else"):
            problems.extend(check_schema(value, root, f"{path}/{key}"))
        elif key == "additionalProperties" and isinstance(value, dict):
            problems.extend(check_schema(value, root, f"{path}/{key}"))
        elif key in ("allOf", "anyOf"):
            for index, sub in enumerate(value):
                problems.extend(check_schema(sub, root, f"{path}/{key}/{index}"))
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
        if not any(_TYPE_CHECKS.get(t, lambda v: True)(instance) for t in types):
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


def semantic_errors(registry: dict) -> list[str]:
    """Cross-entry rules that JSON Schema cannot express."""
    errors: list[str] = []
    names = [entry.get("name") for entry in registry.get("repositories", [])]
    for name in sorted({n for n in names if names.count(n) > 1}, key=str):
        errors.append(f"$.repositories: duplicate name {name!r}")
    return errors


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

    errors = validate(registry, schema) + semantic_errors(registry)
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

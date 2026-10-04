#!/usr/bin/env python3
"""validate_registry.py — validate registry.json against registry.schema.json.

Dependency-free (stdlib only): implements the JSON Schema draft 2020-12 subset
used by registry.schema.json — type, required, properties,
additionalProperties, enum, items, minItems, pattern, minLength, minimum,
minProperties. Unknown keywords are ignored (annotation behavior).

Usage:
    python tools/validate_registry.py [registry.json] [--schema registry.schema.json]

Exit codes: 0 = valid, 1 = validation errors, 2 = file/JSON problems.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent

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


def validate(instance, schema: dict, path: str = "$") -> list[str]:
    """Return a list of validation errors (empty = valid).

    ``path`` is a JSONPath-ish locator such as ``$.repositories[3].status``
    so each error points at the offending value.
    """
    errors: list[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: schema node is not an object"]

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_TYPE_CHECKS.get(t, lambda v: True)(instance) for t in types):
            errors.append(
                f"{path}: expected type {'/'.join(types)}, got {_type_name(instance)}"
            )
            return errors  # type mismatch — deeper checks would be noise

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(validate(value, additional, f"{path}.{key}"))
        min_props = schema.get("minProperties")
        if min_props is not None and len(instance) < min_props:
            errors.append(f"{path}: has {len(instance)} properties, minimum is {min_props}")

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))
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

    errors = validate(registry, schema)
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

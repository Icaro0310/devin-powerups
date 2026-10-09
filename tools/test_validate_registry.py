from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import validate_registry as vr  # noqa: E402

HUB = TOOLS.parent
SCHEMA = json.loads((HUB / "registry.schema.json").read_text(encoding="utf-8"))
REGISTRY = json.loads((HUB / "registry.json").read_text(encoding="utf-8"))


def entry(name: str) -> dict:
    return copy.deepcopy(next(e for e in REGISTRY["repositories"] if e["name"] == name))


def doc(*entries: dict) -> dict:
    document = copy.deepcopy(REGISTRY)
    document["repositories"] = list(entries)
    document.pop("journeys", None)  # steps reference repos not in these docs
    return document


def errors_for(*entries: dict) -> list[str]:
    return vr.validate(doc(*entries), SCHEMA)


# --- validator mechanics ----------------------------------------------------


def test_committed_registry_passes_schema_and_semantic_checks():
    assert vr.check_schema(SCHEMA) == []
    assert vr.validate(REGISTRY, SCHEMA) == []
    assert vr.semantic_errors(REGISTRY) == []
    assert vr.main([]) == 0


def test_enum_and_const_keep_booleans_apart_from_integers():
    assert vr.validate(True, {"enum": [1]})
    assert vr.validate(1, {"const": True})
    assert not vr.validate(True, {"const": True})
    assert vr.validate("1", {"enum": [1]})


def test_type_list_accepts_null_and_rejects_other_types():
    schema = {"type": ["string", "null"], "minLength": 1}
    assert vr.validate(None, schema) == []
    assert vr.validate("x", schema) == []
    assert vr.validate("", schema)
    assert vr.validate(3, schema)


def test_all_of_reports_every_failing_branch():
    schema = {"allOf": [{"type": "object", "required": ["a"]}, {"required": ["b"]}]}
    errors = vr.validate({}, schema)
    assert any("'a'" in e for e in errors) and any("'b'" in e for e in errors)


def test_if_then_else_pick_a_branch_and_name_the_rule():
    schema = {
        "description": "kind a needs x, otherwise y",
        "if": {"properties": {"kind": {"const": "a"}}, "required": ["kind"]},
        "then": {"required": ["x"]},
        "else": {"required": ["y"]},
    }
    assert vr.validate({"kind": "a", "x": 1}, schema) == []
    assert vr.validate({"kind": "b", "y": 1}, schema) == []
    then_errors = vr.validate({"kind": "a"}, schema)
    assert then_errors and "'x'" in then_errors[0] and "kind a needs x" in then_errors[0]
    assert "'y'" in vr.validate({"kind": "b"}, schema)[0]


def test_if_without_a_required_antecedent_is_vacuously_true_like_jsonschema():
    schema = {"if": {"properties": {"kind": {"const": "a"}}}, "then": {"required": ["x"]}}
    assert vr.validate({}, schema)  # {} satisfies the antecedent, so x is required


def test_ref_resolves_against_the_root_schema():
    schema = {"$defs": {"flag": {"type": "boolean"}}, "properties": {"on": {"$ref": "#/$defs/flag"}}}
    assert vr.validate({"on": True}, schema) == []
    assert vr.validate({"on": "yes"}, schema)


def test_unresolvable_ref_is_an_error_not_a_pass():
    assert vr.validate(1, {"$ref": "#/$defs/missing"})
    assert vr.check_schema({"$ref": "#/$defs/missing"})
    assert vr.check_schema({"$ref": "https://example.com/other.json"})


def test_any_of_and_not():
    schema = {"anyOf": [{"type": "string"}, {"type": "integer"}], "not": {"const": 7}}
    assert vr.validate("x", schema) == []
    assert vr.validate(3, schema) == []
    assert vr.validate(7, schema)
    assert vr.validate(1.5, schema)


@pytest.mark.parametrize("keyword", ["oneOf", "patternProperties", "format", "dependentRequired", "uniqueItems", "maxItems"])
def test_unsupported_keywords_are_rejected_instead_of_ignored(keyword):
    problems = vr.check_schema({"properties": {"a": {"type": "string", keyword: {}}}})
    assert problems and keyword in problems[0] and "#/properties/a" in problems[0]


def test_annotations_and_property_names_are_not_mistaken_for_keywords():
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "t", "description": "d", "default": 1, "examples": [1],
        "properties": {"format": {"type": "string"}, "oneOf": {"type": "string"}},
    }
    assert vr.check_schema(schema) == []


def test_main_exits_2_when_the_schema_uses_an_unsupported_keyword(tmp_path, capsys):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"type": "object", "oneOf": []}), encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text("{}", encoding="utf-8")
    assert vr.main([str(registry_path), "--schema", str(schema_path)]) == 2
    assert "unsupported schema keyword 'oneOf'" in capsys.readouterr().err


def test_main_exits_1_on_validation_errors_and_2_on_unreadable_input(tmp_path):
    bad = tmp_path / "registry.json"
    bad.write_text(json.dumps({"version": "x"}), encoding="utf-8")
    assert vr.main([str(bad)]) == 1
    assert vr.main([str(tmp_path / "missing.json")]) == 2


def test_duplicate_names_are_a_semantic_error():
    twin = entry("devin-redact")
    assert vr.semantic_errors(doc(entry("devin-powerups"), twin, copy.deepcopy(twin))) == [
        "$.repositories: duplicate name 'devin-redact'"
    ]


def test_exactly_one_control_plane_is_required():
    plane = entry("devin-powerups")
    assert vr.semantic_errors(doc(plane)) == []
    assert any("found 0" in e for e in vr.semantic_errors(doc(entry("devin-redact"))))
    second = {**entry("devin-devkit"), "is_control_plane": True}
    assert any("found 2" in e for e in vr.semantic_errors(doc(plane, second)))


def test_registry_errors_combines_schema_and_cross_entry_checks():
    # structurally invalid document: only schema errors, no crash
    errors = vr.registry_errors({**REGISTRY, "repositories": None}, SCHEMA)
    assert errors and all("is_control_plane" not in e for e in errors)
    # schema-valid document missing the control plane: cross-entry error surfaces
    # (deepcopy: doc() copies the entry list, not the entries — mutating a
    # shared entry here would poison every later test)
    planeless = doc(*[copy.deepcopy(e) for e in REGISTRY["repositories"]])
    next(e for e in planeless["repositories"] if e["name"] == "devin-powerups")[
        "is_control_plane"
    ] = False
    assert any("is_control_plane" in e for e in vr.registry_errors(planeless, SCHEMA))


def test_semantic_checks_tolerate_malformed_documents():
    assert isinstance(vr.semantic_errors({"repositories": None}), list)
    assert isinstance(vr.semantic_errors({"repositories": ["x", {}]}), list)
    assert isinstance(vr.semantic_errors([]), list)


def test_main_reports_malformed_repositories_without_a_traceback(tmp_path):
    bad = tmp_path / "registry.json"
    for bad_value in (None, ["x"], [{"name": 1}]):
        bad.write_text(json.dumps({**REGISTRY, "repositories": bad_value}), encoding="utf-8")
        assert vr.main([str(bad)]) == 1


def test_unknown_type_names_fail_closed():
    assert vr.check_schema({"type": "madeup"})
    assert vr.check_schema({"type": ["string", "madeup"]})
    assert vr.check_schema({"type": []})
    assert vr.validate("anything", {"type": "madeup"}) == [
        "$: unsupported schema type 'madeup'"
    ]


@pytest.mark.parametrize("schema", [
    {"properties": ["a"]},
    {"$defs": []},
    {"allOf": {"type": "object"}},
    {"additionalProperties": 0},
    {"enum": "x"},
    {"enum": []},
    {"required": "name"},
    {"minItems": -1},
    {"minLength": "2"},
    {"minimum": True},
    {"pattern": "["},
    {"pattern": 3},
])
def test_malformed_keyword_operands_are_schema_problems(schema):
    assert vr.check_schema(schema)


# --- rules the old validator silently skipped --------------------------------


def test_corporate_windows_rule_is_now_enforced():
    broken = entry("devin-powerups")
    broken["environments"]["corporate_windows"]["external_dependencies"] = True
    errors = errors_for(broken)
    assert any("corporate_windows" in e and "external_dependencies" in e for e in errors)


def test_public_tools_must_declare_platforms_and_environments():
    broken = entry("devin-redact")
    del broken["platforms"]
    assert any("'platforms'" in e for e in errors_for(broken))


# --- agreement with the reference implementation -----------------------------


def _mutants(base: dict):
    """Single-edit mutants of one registry entry, top level and one level down."""
    for key in list(base):
        yield f"drop {key}", {k: v for k, v in base.items() if k != key}
        for label, value in (("int", 12345), ("str", "__bad__"), ("null", None)):
            yield f"{key}={label}", {**base, key: value}
        if isinstance(base[key], bool):
            yield f"flip {key}", {**base, key: not base[key]}
        if key == "environments":
            for env, support in base["environments"].items():
                for sub in list(support):
                    dropped = {k: v for k, v in support.items() if k != sub}
                    yield f"drop {env}.{sub}", {**base, "environments": {**base["environments"], env: dropped}}
                    if isinstance(support[sub], bool):
                        flipped = {**support, sub: not support[sub]}
                        yield f"flip {env}.{sub}", {**base, "environments": {**base["environments"], env: flipped}}


def test_validator_agrees_with_jsonschema_on_single_edit_mutants():
    jsonschema = pytest.importorskip("jsonschema")
    reference = jsonschema.Draft202012Validator(SCHEMA)
    reference.check_schema(SCHEMA)
    disagreements = []
    checked = 0
    for name in ("devin-powerups", "devin-devkit", "devin-internals-spec", "devin-office",
                 "awesome-devin", "qwenpaw-suite", "personal-agent-system", "devin-learning"):
        for label, mutant in _mutants(entry(name)):
            document = doc(mutant)
            ours = not vr.validate(document, SCHEMA)
            theirs = reference.is_valid(document)
            checked += 1
            if ours != theirs:
                disagreements.append(f"{name}: {label}: ours={ours} jsonschema={theirs}")
    assert checked > 300
    assert disagreements == []


# --- registry v21 product rules -----------------------------------------------


def _member(name: str, pid: str, job: str, mode: str = "read",
            package: dict | None = None, entrypoints=None, ownership="first_party"):
    return {
        "name": name,
        "ownership": ownership,
        "job": job,
        "product_id": pid,
        "mode": mode,
        "package": package if package is not None else {
            "ecosystem": "pypi", "name": name, "path": ".",
        },
        "entrypoints": entrypoints if entrypoints is not None else [name],
        "legacy": None,
        "distribution_status": "published",
    }


def test_product_id_requires_first_party_ownership():
    broken = _member("devin-x", "devin-explore", "understand", ownership="external")
    errors = vr.semantic_errors(doc(entry("devin-powerups"), broken))
    assert any("only first_party" in e for e in errors)


def test_first_party_needs_product_id_or_control_plane():
    orphan = _member("devin-x", "devin-explore", "understand")
    orphan["product_id"] = None
    orphan["job"] = None
    errors = vr.semantic_errors(doc(entry("devin-powerups"), orphan))
    assert any("without product_id" in e for e in errors)
    # the control plane is the only first_party entry allowed without a product
    assert vr.semantic_errors(doc(entry("devin-powerups"))) == []


def test_job_and_product_id_are_set_together():
    broken = _member("devin-x", "devin-explore", "understand")
    broken["product_id"] = None
    errors = vr.semantic_errors(doc(entry("devin-powerups"), broken))
    assert any("must both be set" in e for e in errors)


def test_read_only_jobs_reject_mutating_members():
    ok = _member("devin-x", "devin-explore", "understand", mode="read")
    assert not any("devin-x" in e for e in vr.semantic_errors(doc(entry("devin-powerups"), ok)))
    bad = _member("devin-y", "devin-explore", "understand", mode="mixed")
    errors = vr.semantic_errors(doc(entry("devin-powerups"), bad))
    assert any("requires read" in e for e in errors)
    # control tolerates mixed members
    legal = _member("devin-z", "devin-control", "control", mode="mixed")
    assert not any("requires read" in e for e in vr.semantic_errors(doc(entry("devin-powerups"), legal)))


def test_product_members_share_one_job():
    a = _member("devin-x", "devin-explore", "understand")
    b = _member("devin-y", "devin-explore", "verify")
    errors = vr.semantic_errors(doc(entry("devin-powerups"), a, b))
    assert any("different jobs" in e for e in errors)


def test_every_product_needs_a_package_and_package_names_are_unique():
    a = _member("devin-x", "devin-explore", "understand")
    a["package"] = None
    a["entrypoints"] = []
    errors = vr.semantic_errors(doc(entry("devin-powerups"), a))
    assert any("no member declares a package" in e for e in errors)
    b = _member("devin-y", "devin-assure", "verify")
    b["package"] = {"ecosystem": "pypi", "name": "devin-x", "path": "."}
    errors = vr.semantic_errors(doc(entry("devin-powerups"), _member("devin-x", "devin-explore", "understand"), b))
    assert any("claimed by both" in e for e in errors)


def test_product_cap_is_enforced():
    members = [entry("devin-powerups")]
    for i in range(8):
        members.append(_member(f"devin-p{i}", f"devin-p{i}", "understand"))
    errors = vr.semantic_errors(doc(*members))
    assert any("maximum is 7" in e for e in errors)


def test_entrypoints_require_a_package():
    broken = _member("devin-x", "devin-explore", "understand")
    broken["package"] = None
    errors = vr.semantic_errors(doc(entry("devin-powerups"), broken))
    assert any("package is null" in e for e in errors)


def test_depends_on_must_resolve_to_a_published_package_and_stay_acyclic():
    consumer = _member("devin-x", "devin-explore", "understand")
    consumer["package"]["depends_on"] = ["devin-missing"]
    errors = vr.semantic_errors(doc(entry("devin-powerups"), consumer))
    assert any("not a package" in e for e in errors)

    unpublished = _member("devin-y", "devin-assure", "verify")
    unpublished["distribution_status"] = "source_only"
    consumer["package"]["depends_on"] = ["devin-y"]
    errors = vr.semantic_errors(doc(entry("devin-powerups"), consumer, unpublished))
    assert any("published package" in e for e in errors)

    a = _member("devin-a", "devin-pa", "control")
    b = _member("devin-b", "devin-pb", "control")
    a["package"]["depends_on"] = ["devin-b"]
    b["package"]["depends_on"] = ["devin-a"]
    errors = vr.semantic_errors(doc(entry("devin-powerups"), a, b))
    assert any("cycle" in e for e in errors)


def test_legacy_renamed_must_not_point_at_a_live_entry():
    renamed = _member("devin-brain", "devin-brain", "build")
    renamed["legacy"] = {"repo": "devin-memory", "status": "renamed", "redirect": True}
    assert not any("legacy" in e for e in vr.semantic_errors(
        doc(entry("devin-powerups"), renamed)))
    stale = doc(entry("devin-powerups"), renamed, entry("devin-memory"))
    assert any("still exists" in e for e in vr.semantic_errors(stale))


def test_entrypoints_are_checked_against_the_real_manifest(tmp_path):
    checkout = tmp_path / "devin-x"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text(
        '[project]\nname = "devin-x"\n[project.scripts]\ndevin-x = "devin_x.cli:main"\n'
    )
    e = _member("devin-x", "devin-explore", "understand", entrypoints=["devin-x"])
    assert vr.semantic_errors(doc(entry("devin-powerups"), e), root=tmp_path) == []
    e["entrypoints"] = ["devin-x", "devin-x-ghost"]
    errors = vr.semantic_errors(doc(entry("devin-powerups"), e), root=tmp_path)
    assert any("not found" in e for e in errors)


def test_devkit_commands_must_be_declared_entrypoints():
    document = doc(entry("devin-powerups"), entry("devin-doctor"))
    document["devkit"] = {
        "tools": {"devin-doctor": {"commands": ["devin-doctor", "devin-ghost"]}}
    }
    errors = vr.semantic_errors(document)
    assert any("devin-ghost" in e for e in errors)

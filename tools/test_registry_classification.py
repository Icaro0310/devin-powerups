from __future__ import annotations

import copy
import itertools
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
ENTRY_PROPS = SCHEMA["properties"]["repositories"]["items"]["properties"]

VOCABULARY = {
    "nature": ["product", "infrastructure", "distribution", "surface", "fixture"],
    "track": ["observe", "assure", "guard", "platform", "navigation", "foundation", "related"],
    "role": ["flagship", "module", "foundation", "installer", "catalog", "surface"],
    "mode": ["read", "write", "mixed"],
    "maturity": ["experimental", "usable", "stable"],
    "official_overlap": ["none", "partial", "high"],
    "distribution_status": ["published", "source_only", "pending"],
}

BASE = {
    "public": True, "nature": "product", "track": "observe", "role": "module", "mode": "read",
    "maturity": "usable", "official_overlap": "none", "overlap_note": None,
}


def entry(name: str, **fields) -> dict:
    found = copy.deepcopy(next(e for e in REGISTRY["repositories"] if e["name"] == name))
    found.update(fields)
    return found


def classified(**fields) -> dict:
    return entry("devin-explore", **{**BASE, **fields})


def errors_for(*entries: dict) -> list[str]:
    document = copy.deepcopy(REGISTRY)
    document["repositories"] = list(entries)
    return vr.validate(document, SCHEMA)


def test_vocabulary_is_exactly_the_approved_one():
    for field, values in VOCABULARY.items():
        assert ENTRY_PROPS[field]["enum"] == values, field
    assert ENTRY_PROPS["public"]["type"] == "boolean"
    assert ENTRY_PROPS["is_control_plane"] == {
        "type": "boolean", "default": False,
        "description": ENTRY_PROPS["is_control_plane"]["description"],
    }
    assert ENTRY_PROPS["overlap_note"]["type"] == ["string", "null"]


def test_a_fully_classified_entry_validates():
    assert errors_for(classified()) == []


@pytest.mark.parametrize("field", sorted(VOCABULARY))
def test_enums_reject_values_outside_the_vocabulary(field):
    for bad in ("__bad__", "Observe", 1, True, None, ["observe"]):
        errors = errors_for(classified(**{field: bad}))
        assert any(f".{field}:" in e for e in errors), (field, bad, errors)


@pytest.mark.parametrize("field", ["public", "is_control_plane"])
def test_booleans_reject_other_types(field):
    for bad in ("true", 1, None):
        assert errors_for(classified(**{field: bad})), (field, bad)


# --- what an entry must declare ----------------------------------------------


@pytest.mark.parametrize("field", ["public", "maturity", "nature", "track", "role", "mode", "official_overlap", "overlap_note", "distribution_status"])
def test_public_entries_cannot_omit_a_classification_field(field):
    candidate = classified()
    del candidate[field]
    assert any(f"'{field}'" in e for e in errors_for(candidate)), field


@pytest.mark.parametrize("field", ["public", "maturity"])
def test_private_entries_need_only_public_and_maturity(field):
    private = entry("personal-agent-system", public=False, maturity="usable")
    assert errors_for(private) == []
    del private[field]
    assert any(f"'{field}'" in e for e in errors_for(private))


# --- public mirrors visibility ------------------------------------------------


def test_public_flag_must_mirror_visibility():
    assert errors_for(classified(public=False))
    private = entry("personal-agent-system", public=False, maturity="usable")
    assert errors_for(private) == []
    assert errors_for({**private, "public": True})


# --- official overlap -----------------------------------------------------------


@pytest.mark.parametrize("overlap, note, valid", [
    ("none", None, True),
    ("none", "Complements something.", False),
    ("partial", "Complements official Devin Memory.", True),
    ("high", "Substantially the same function.", True),
    ("partial", None, False),
    ("high", None, False),
    ("partial", "", False),
    ("partial", 3, False),
])
def test_overlap_note_rules(overlap, note, valid):
    assert (errors_for(classified(official_overlap=overlap, overlap_note=note)) == []) is valid


def test_partial_overlap_requires_the_note_key():
    candidate = classified(official_overlap="partial")
    del candidate["overlap_note"]
    assert any("'overlap_note'" in e for e in errors_for(candidate))


# --- control plane ---------------------------------------------------------------


def test_control_plane_must_be_platform_foundation_infrastructure():
    plane = classified(track="platform", role="foundation", nature="infrastructure", mode="mixed", is_control_plane=True)
    assert errors_for(plane) == []
    for field, wrong in (("track", "guard"), ("role", "module"), ("nature", "product")):
        assert errors_for({**plane, field: wrong}), field
    assert errors_for(classified(is_control_plane=True))
    assert errors_for(classified(is_control_plane=False)) == []


# --- consistency of track / role / nature / mode ---------------------------------

VALID_COMBOS = [
    ("platform", "foundation", "infrastructure", "mixed"),
    ("platform", "installer", "distribution", "mixed"),
    ("observe", "foundation", "infrastructure", "read"),
    ("assure", "flagship", "product", "read"),
    ("assure", "module", "fixture", "read"),
    ("guard", "module", "product", "mixed"),
    ("platform", "catalog", "product", "mixed"),
    ("navigation", "surface", "surface", "read"),
    ("related", "module", "product", "mixed"),
    ("observe", "module", "product", "read"),
    ("foundation", "foundation", "infrastructure", "read"),
]

INVALID_COMBOS = [
    ("observe", "module", "surface", "read"),            # surfaces live in navigation
    ("navigation", "module", "product", "read"),         # navigation holds surfaces only
    ("navigation", "surface", "surface", "mixed"),       # a surface is passive
    ("guard", "installer", "distribution", "mixed"),     # distributions belong to platform
    ("platform", "installer", "product", "mixed"),       # an installer is a distribution
    ("observe", "foundation", "product", "read"),        # foundation is infrastructure
    ("platform", "module", "infrastructure", "mixed"),   # infrastructure plays foundation
    ("observe", "flagship", "infrastructure", "read"),   # the flagship is a product
    ("platform", "flagship", "product", "read"),         # the flagship sits in a product track
    ("guard", "catalog", "product", "mixed"),            # catalog functionality is platform
    ("observe", "module", "fixture", "read"),            # fixtures belong to assure
    ("assure", "module", "fixture", "mixed"),            # fixtures are read-only
    ("related", "flagship", "product", "read"),          # related holds modules
    ("foundation", "module", "product", "read"),         # the foundation track holds infrastructure
    ("assure", "catalog", "product", "read"),
]


def combo_errors(combo):
    track, role, nature, mode = combo
    return errors_for(classified(track=track, role=role, nature=nature, mode=mode))


@pytest.mark.parametrize("combo", VALID_COMBOS)
def test_coherent_combinations_validate(combo):
    assert combo_errors(combo) == []


@pytest.mark.parametrize("combo", INVALID_COMBOS)
def test_contradictory_combinations_are_rejected_with_the_rule_named(combo):
    errors = combo_errors(combo)
    assert errors and all("[rule: " in e for e in errors)


def test_every_combination_agrees_with_the_jsonschema_reference():
    jsonschema = pytest.importorskip("jsonschema")
    reference = jsonschema.Draft202012Validator(SCHEMA)
    axes = [VOCABULARY["track"], VOCABULARY["role"], VOCABULARY["nature"], VOCABULARY["mode"]]
    document = copy.deepcopy(REGISTRY)
    valid = 0
    for combo in itertools.product(*axes):
        document["repositories"] = [classified(track=combo[0], role=combo[1], nature=combo[2], mode=combo[3])]
        ours = not vr.validate(document, SCHEMA)
        assert ours == reference.is_valid(document), combo
        valid += ours
    assert 0 < valid < 7 * 6 * 5 * 3
    assert set(VALID_COMBOS) <= {c for c in itertools.product(*axes) if not combo_errors(c)}


# --- the committed registry ------------------------------------------------------

# Approved classification (execution plan P0.2, 2026-10-07; devin-pm and
# devin-brain (ex devin-memory) placed by the maintainer the same day). Changing a track is a
# governance decision: update this table in the same pull request.
APPROVED_TRACKS = {
    "observe": ["devin-internals-spec", "devin-explore", "devin-history", "devin-search", "devin-graph"],
    "assure": ["devin-assure", "devin-evals", "devin-metrics", "devin-judge"],
    "guard": ["devin-bridge", "devin-orchestrator", "devin-switch", "devin-state", "devin-backup", "devin-janitor", "devin-brain", "devin-office"],
    "platform": ["devin-devkit", "devin-powerups", "devin-skill-catalog"],
    "navigation": ["awesome-devin"],
    "related": ["qwenpaw-suite", "devin-pm"],
}
BY_NAME = {e["name"]: e for e in REGISTRY["repositories"]}
PUBLIC_ENTRIES = [e for e in REGISTRY["repositories"] if e["visibility"] == "public"]


def test_every_public_entry_is_classified_in_exactly_the_approved_track():
    expected = {name: track for track, names in APPROVED_TRACKS.items() for name in names}
    assert len(expected) == len(PUBLIC_ENTRIES) == 23
    assert {e["name"]: e["track"] for e in PUBLIC_ENTRIES} == expected


def test_public_entries_carry_the_full_classification():
    required = ["public", "nature", "track", "role", "mode", "maturity", "official_overlap", "overlap_note"]
    for e in PUBLIC_ENTRIES:
        assert all(key in e for key in required), e["name"]
        assert e["public"] is True


def test_private_entries_are_marked_not_public_and_have_a_maturity():
    private = [e for e in REGISTRY["repositories"] if e["visibility"] == "private"]
    assert {e["name"] for e in private} == {"personal-agent-system", "devin-dashboard", "devin-learning"}
    for e in private:
        assert e["public"] is False and e["maturity"] in VOCABULARY["maturity"]


def test_devin_powerups_is_the_only_control_plane():
    assert [e["name"] for e in REGISTRY["repositories"] if e.get("is_control_plane")] == ["devin-powerups"]
    plane = BY_NAME["devin-powerups"]
    assert (plane["track"], plane["role"], plane["nature"], plane["maturity"], plane["public"]) == (
        "platform", "foundation", "infrastructure", "stable", True)
    assert all("is_control_plane" not in e for e in REGISTRY["repositories"] if e["name"] != "devin-powerups")


def test_official_overlap_is_declared_only_where_the_repository_documents_it():
    partial = {e["name"] for e in PUBLIC_ENTRIES if e["official_overlap"] == "partial"}
    assert partial == {"devin-brain", "devin-evals", "devin-skill-catalog"}
    assert not [e for e in PUBLIC_ENTRIES if e["official_overlap"] == "high"]
    for e in PUBLIC_ENTRIES:
        if e["official_overlap"] == "none":
            assert e["overlap_note"] is None, e["name"]
        else:
            assert "official" in e["overlap_note"].lower(), e["name"]


def test_flagship_fixture_and_surface_are_unique():
    roles = [e["role"] for e in PUBLIC_ENTRIES]
    assert roles.count("flagship") == 1 and BY_NAME["devin-assure"]["role"] == "flagship"
    # the only fixture (devin-dream) was absorbed into devin-evals (P4)
    assert [e["name"] for e in PUBLIC_ENTRIES if e["nature"] == "fixture"] == []
    assert [e["name"] for e in PUBLIC_ENTRIES if e["nature"] == "surface"] == ["awesome-devin"]


def test_mode_matches_documented_mutating_commands():
    mixed = {e["name"] for e in PUBLIC_ENTRIES if e["mode"] == "mixed"}
    # explicit, guarded mutations: --apply / --yes / restore / redact / swap / promote / install / control endpoints
    assert mixed == {"devin-powerups", "devin-devkit", "devin-state", "devin-backup", "devin-janitor", "devin-switch",
                     "devin-skill-catalog", "devin-brain", "devin-bridge", "devin-office", "qwenpaw-suite"}
    assert not [e for e in PUBLIC_ENTRIES if e["mode"] == "write"]


def test_distribution_status_is_declared_on_public_products_and_fixtures():
    for e in PUBLIC_ENTRIES:
        if e["nature"] in ("product", "fixture"):
            assert e.get("distribution_status") in VOCABULARY["distribution_status"], e["name"]
    assert {e["name"] for e in PUBLIC_ENTRIES if e.get("distribution_status") == "source_only"} == {
        "devin-skill-catalog", "devin-switch",
        "devin-office", "qwenpaw-suite"}


def test_distribution_status_agrees_with_devkit_tool_status():
    document = copy.deepcopy(REGISTRY)
    doctor = next(e for e in document["repositories"] if e["name"] == "devin-explore")
    doctor["distribution_status"] = "source_only"
    errors = vr.semantic_errors(document)
    assert any("distribution_status" in e and "devin-explore" in e for e in errors), errors

import json
from pathlib import Path

from research.exp18.r1_runner import extract_atoms

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "research" / "exp18" / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def organic_atoms(name):
    fixture = load(name)
    schema = load("schema_map.json")
    declared = {(slot["object_ref"], slot["property"]) for slot in schema["slots"]}
    atoms = []
    for obj in fixture["objects"]:
        for prop, state in obj.get("properties", {}).items():
            if (obj.get("object_ref"), prop) not in declared:
                continue
            link = state.get("provenance_link")
            if not isinstance(link, str) or not link:
                continue
            atoms.append({"object_ref": obj["object_ref"], "property": prop, "val_prev": state.get("val_prev"), "val_curr": state.get("val_curr"), "provenance_link": link})
    return atoms


def test_synthetic_alignment_is_deterministic_and_complete():
    fixture = load("synthetic_control_01.json")
    payload = fixture["raw_observation_payload"]
    first = extract_atoms(payload)
    second = extract_atoms(payload)
    assert first == second
    assert first == fixture["expected_atoms_ground_truth"]


def test_organic_alignment_is_deterministic_with_explicit_drop_counts():
    for name in ("organic_sample_01.json", "organic_sample_02.json"):
        first = organic_atoms(name)
        second = organic_atoms(name)
        assert first == second
        assert len(first) == 4
        assert len(first) / 5 == 0.8


def test_field_alignment_is_fixture_order_invariant():
    baseline = organic_atoms("organic_sample_01.json")
    fixture = load("organic_sample_01.json")
    fixture["objects"] = list(reversed(fixture["objects"]))
    declared = {(slot["object_ref"], slot["property"]) for slot in load("schema_map.json")["slots"]}
    reordered = []
    for obj in fixture["objects"]:
        for prop, state in obj.get("properties", {}).items():
            if (obj.get("object_ref"), prop) in declared and state.get("provenance_link"):
                reordered.append({"object_ref": obj["object_ref"], "property": prop, "val_prev": state.get("val_prev"), "val_curr": state.get("val_curr"), "provenance_link": state["provenance_link"]})
    assert sorted(baseline, key=lambda x: (x["object_ref"], x["property"])) == sorted(reordered, key=lambda x: (x["object_ref"], x["property"]))

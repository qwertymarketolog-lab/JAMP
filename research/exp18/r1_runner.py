import json
from pathlib import Path

FIXTURE = Path("research/exp18/fixtures/synthetic_control_01.json")
OUT = Path("research/exp18/out/r1_synthetic_control_report.json")


def extract_atoms(payload):
    atoms = []
    object_ref = payload["object_ref"]
    provenance_link = payload["provenance_link"]

    for property_name, state in payload["properties"].items():
        atoms.append(
            {
                "object_ref": object_ref,
                "property": property_name,
                "val_prev": state.get("val_prev"),
                "val_curr": state.get("val_curr"),
                "provenance_link": provenance_link,
            }
        )

    return atoms


def main():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    declared_slots = fixture["fixture_meta"]["declared_logical_slots"]
    payload = fixture["raw_observation_payload"]
    ground_truth = fixture["expected_atoms_ground_truth"]

    extracted = extract_atoms(payload)

    if declared_slots <= 0:
        raise ValueError("declared_logical_slots must be positive")

    if len(extracted) > declared_slots:
        raise AssertionError("extracted atoms exceed declared logical slots")

    matched = sum(atom in ground_truth for atom in extracted)

    density = matched / declared_slots

    type_role_discrepancies = []

    if len(extracted) != len(ground_truth):
        type_role_discrepancies.append("ATOM_COUNT_MISMATCH")

    for atom in extracted:
        if atom not in ground_truth:
            type_role_discrepancies.append("GROUND_TRUTH_MISMATCH")

    status = "PASS" if density == 1.0 and not type_role_discrepancies else "FAIL"

    report = {
        "spec": "EXP18-R1",
        "stage": "SYNTHETIC_CONTROL",
        "declared_logical_slots": declared_slots,
        "ground_truth_atoms": len(ground_truth),
        "extracted_atoms": len(extracted),
        "matched_atoms": matched,
        "D_semantic": density,
        "type_role_discrepancies": type_role_discrepancies,
        "status": status,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, sort_keys=True))


def run_organic(fixture_name="organic_sample_01.json", output_name="r1_organic_report.json"):
    schema = json.loads(Path("research/exp18/fixtures/schema_map.json").read_text(encoding="utf-8"))
    fixture = json.loads(
        (Path("research/exp18/fixtures") / fixture_name).read_text(encoding="utf-8")
    )

    declared_slots = schema["declared_logical_slots"]
    declared = {(slot["object_ref"], slot["property"]) for slot in schema["slots"]}

    extracted = []

    for obj in fixture["objects"]:
        object_ref = obj.get("object_ref")
        for property_name, state in obj.get("properties", {}).items():
            key = (object_ref, property_name)

            if key not in declared:
                continue

            provenance_link = state.get("provenance_link")

            if not isinstance(provenance_link, str) or not provenance_link:
                continue

            extracted.append(
                {
                    "object_ref": object_ref,
                    "property": property_name,
                    "val_prev": state.get("val_prev"),
                    "val_curr": state.get("val_curr"),
                    "provenance_link": provenance_link,
                }
            )

    matched = len(extracted)
    density = matched / declared_slots

    report = {
        "spec": "EXP18-R1",
        "stage": "ORGANIC_STRUCTURED",
        "declared_logical_slots": declared_slots,
        "extracted_valid_atoms": matched,
        "dropped_invalid_atoms": declared_slots - matched,
        "D_semantic": density,
        "status": "UNVERIFIED_ORGANIC_PENDING",
    }

    OUT_ORGANIC = Path("research/exp18/out") / output_name
    OUT_ORGANIC.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not args:
        print(
            "[R1-RUNNER] Usage: "
            "python3 research/exp18/r1_runner.py "
            "[synthetic|organic] [--fixture=FILE]"
        )
        raise SystemExit(1)

    mode = args[0].lower()

    fixture_name = "organic_sample_01.json"
    output_name = "r1_organic_report.json"

    for arg in args[1:]:
        if arg.startswith("--fixture="):
            fixture_name = arg.split("=", 1)[1]
        else:
            print("[R1-RUNNER] Unknown argument:", arg)
            raise SystemExit(1)

    if mode == "synthetic":
        if len(args) != 1:
            print("[R1-RUNNER] synthetic accepts no extra arguments")
            raise SystemExit(1)
        main()
    elif mode == "organic":
        if fixture_name != "organic_sample_01.json":
            output_name = "r1_organic_control_report.json"
        run_organic(fixture_name, output_name)
    else:
        print(
            "[R1-RUNNER] Usage: "
            "python3 research/exp18/r1_runner.py "
            "[synthetic|organic] [--fixture=FILE]"
        )
        raise SystemExit(1)

import json
from pathlib import Path

FIXTURE = Path("research/exp18/fixtures/synthetic_control_01.json")
OUT = Path("research/exp18/out/r1_synthetic_control_report.json")


def extract_atoms(payload):
    return [
        {
            "object_ref": payload["object_ref"],
            "property": name,
            "val_prev": state.get("val_prev"),
            "val_curr": state.get("val_curr"),
            "provenance_link": payload["provenance_link"],
        }
        for name, state in payload["properties"].items()
    ]


def main():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    declared_slots = fixture["fixture_meta"]["declared_logical_slots"]
    extracted = extract_atoms(fixture["raw_observation_payload"])
    ground_truth = fixture["expected_atoms_ground_truth"]
    if declared_slots <= 0 or len(extracted) > declared_slots:
        raise AssertionError("invalid declared logical slots")
    matched = sum(atom in ground_truth for atom in extracted)
    complete = len(extracted) == len(ground_truth)
    complete = complete and all(atom in ground_truth for atom in extracted)
    discrepancies = [] if complete else ["GROUND_TRUTH_MISMATCH"]
    density = matched / declared_slots
    status = "PASS" if density == 1.0 and not discrepancies else "FAIL"
    report = {
        "spec": "EXP18-R1",
        "stage": "SYNTHETIC_CONTROL",
        "declared_logical_slots": declared_slots,
        "ground_truth_atoms": len(ground_truth),
        "extracted_atoms": len(extracted),
        "matched_atoms": matched,
        "D_semantic": density,
        "type_role_discrepancies": discrepancies,
        "status": status,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


def run_organic(
    fixture_name="organic_sample_01.json",
    output_name="r1_organic_report.json",
):
    schema = json.loads(Path("research/exp18/fixtures/schema_map.json").read_text(encoding="utf-8"))
    fixture = json.loads((Path("research/exp18/fixtures") / fixture_name).read_text(encoding="utf-8"))
    declared = {
        (slot["object_ref"], slot["property"]) for slot in schema["slots"]
    }
    extracted = []
    for obj in fixture["objects"]:
        for property_name, state in obj.get("properties", {}).items():
            key = (obj.get("object_ref"), property_name)
            link = state.get("provenance_link")
            if key not in declared or not isinstance(link, str) or not link:
                continue
            extracted.append(
                {
                    "object_ref": obj["object_ref"],
                    "property": property_name,
                    "val_prev": state.get("val_prev"),
                    "val_curr": state.get("val_curr"),
                    "provenance_link": link,
                }
            )
    density = len(extracted) / schema["declared_logical_slots"]
    report = {
        "spec": "EXP18-R1",
        "stage": "ORGANIC_STRUCTURED",
        "declared_logical_slots": schema["declared_logical_slots"],
        "extracted_valid_atoms": len(extracted),
        "dropped_invalid_atoms": schema["declared_logical_slots"] - len(extracted),
        "D_semantic": density,
        "status": "UNVERIFIED_ORGANIC_PENDING",
    }
    out = Path("research/exp18/out") / output_name
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not args:
        raise SystemExit(
            "usage: python3 research/exp18/r1_runner.py [synthetic|organic] [--fixture=FILE]"
        )
    mode = args[0].lower()
    fixture_name = "organic_sample_01.json"
    for arg in args[1:]:
        if arg.startswith("--fixture="):
            fixture_name = arg.split("=", 1)[1]
        else:
            raise SystemExit(f"Unknown argument: {arg}")
    if mode == "synthetic":
        if len(args) != 1:
            raise SystemExit("synthetic accepts no extra arguments")
        main()
    elif mode == "organic":
        if fixture_name != "organic_sample_01.json":
            output_name = "r1_organic_control_report.json"
        else:
            output_name = "r1_organic_report.json"
        run_organic(fixture_name, output_name)
    else:
        raise SystemExit(
            "usage: python3 research/exp18/r1_runner.py "
            "[synthetic|organic] [--fixture=FILE]"
        )

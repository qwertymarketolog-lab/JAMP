import json
from pathlib import Path

INPUT_LEDGER = Path("artifacts/s1-r3.ndjson")
OUTPUT_DIR = Path("research/exp18/out")
OUTPUT_REPORT = OUTPUT_DIR / "r0_density_report.json"

# Static denominator: one expected atom slot per S1-R3 vector record.
EXPECTED_SLOTS_PER_VECTOR = {
    "V1": 1,
    "V2": 1,
    "V3": 1,
    "V4": 1,
    "V5": 1,
    "V6": 1,
    "V7": 1,
    "V8": 1,
    "V9": 1,
    "V10": 1,
}


def decompose_record(record: dict) -> list[dict]:
    vec = str(record.get("vector", "GENERAL")).strip()
    seed = record.get("seed", "unknown")
    orig_fp = record.get("original_payload_fingerprint")
    mut_fp = record.get("mutated_payload_fingerprint")

    # No atom is emitted when both source state fingerprints are absent.
    if not orig_fp and not mut_fp:
        return []

    prov_link = f"ledger-s1r3-{vec}-{seed}"

    atom = {
        "object_ref": f"target-{vec.lower()}",
        "property": f"payload_mutation_{vec}",
        "val_prev": orig_fp,
        "val_curr": mut_fp,
        "provenance_link": prov_link,
    }
    return [atom]


def run_r0():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not INPUT_LEDGER.exists():
        raise FileNotFoundError(f"Read-only input missing: {INPUT_LEDGER}")

    total_records = 0
    total_valid_atoms = 0
    total_expected_slots = 0
    vector_stats = {}

    with INPUT_LEDGER.open("r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)
            vector = str(record.get("vector", "GENERAL")).strip()
            _seed = record.get("seed", line_idx)

            exp_slots = EXPECTED_SLOTS_PER_VECTOR.get(vector, 1)
            atoms = decompose_record(record)

            valid_count = len(atoms)
            _density = valid_count / exp_slots if exp_slots > 0 else 0.0

            total_records += 1
            total_valid_atoms += valid_count
            total_expected_slots += exp_slots

            if vector not in vector_stats:
                vector_stats[vector] = {
                    "records": 0,
                    "valid_atoms": 0,
                    "expected_slots": 0,
                }

            vector_stats[vector]["records"] += 1
            vector_stats[vector]["valid_atoms"] += valid_count
            vector_stats[vector]["expected_slots"] += exp_slots

    global_density = (
        total_valid_atoms / total_expected_slots
        if total_expected_slots > 0
        else 0.0
    )

    report = {
        "r0_status": "UNVERIFIED_PENDING_INSPECTION",
        "global_metrics": {
            "total_records": total_records,
            "total_valid_atoms": total_valid_atoms,
            "total_expected_slots": total_expected_slots,
            "global_density": round(global_density, 4),
        },
        "vector_breakdown": {
            vector: {
                **stats,
                "density": round(stats["valid_atoms"] / stats["expected_slots"], 4)
                if stats["expected_slots"] > 0
                else 0.0,
            }
            for vector, stats in vector_stats.items()
        },
    }

    with OUTPUT_REPORT.open("w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True)

    print(
        f"[R0-SHADOW-ALIGNED] Report generated: {OUTPUT_REPORT} | Global D = "
        f"{global_density:.4f}"
    )


if __name__ == "__main__":
    run_r0()

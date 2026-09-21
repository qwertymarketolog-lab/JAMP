import json
from pathlib import Path

INPUT_LEDGER = Path("artifacts/s1-r3.ndjson")
OUTPUT_DIR = Path("research/exp18/out")
OUTPUT_REPORT = OUTPUT_DIR / "r0_density_report.json"
EXPECTED_SLOTS_PER_VECTOR = {f"V{i}": 1 for i in range(1, 11)}


def decompose_record(record: dict) -> list[dict]:
    vec = str(record.get("vector", "GENERAL")).strip()
    seed = record.get("seed", "unknown")
    orig_fp = record.get("original_payload_fingerprint")
    mut_fp = record.get("mutated_payload_fingerprint")
    if not orig_fp and not mut_fp:
        return []
    return [{
        "object_ref": f"target-{vec.lower()}",
        "property": f"payload_mutation_{vec}",
        "val_prev": orig_fp,
        "val_curr": mut_fp,
        "provenance_link": f"ledger-s1r3-{vec}-{seed}",
    }]


def run_r0():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not INPUT_LEDGER.exists():
        raise FileNotFoundError(f"Read-only input missing: {INPUT_LEDGER}")
    total_records = total_valid_atoms = total_expected_slots = 0
    vector_stats = {}
    with INPUT_LEDGER.open("r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f):
            if not line.strip():
                continue
            record = json.loads(line)
            vector = str(record.get("vector", "GENERAL")).strip()
            atoms = decompose_record(record)
            exp_slots = EXPECTED_SLOTS_PER_VECTOR.get(vector, 1)
            total_records += 1
            total_valid_atoms += len(atoms)
            total_expected_slots += exp_slots
            stats = vector_stats.setdefault(vector, {"records": 0, "valid_atoms": 0, "expected_slots": 0})
            stats["records"] += 1
            stats["valid_atoms"] += len(atoms)
            stats["expected_slots"] += exp_slots
    global_density = total_valid_atoms / total_expected_slots if total_expected_slots else 0.0
    report = {"r0_status": "UNVERIFIED_PENDING_INSPECTION", "global_metrics": {"total_records": total_records, "total_valid_atoms": total_valid_atoms, "total_expected_slots": total_expected_slots, "global_density": round(global_density, 4)}, "vector_breakdown": {vector: {**stats, "density": round(stats["valid_atoms"] / stats["expected_slots"], 4) if stats["expected_slots"] else 0.0} for vector, stats in vector_stats.items()}}
    with OUTPUT_REPORT.open("w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True)
    print(f"[R0-SHADOW-ALIGNED] Report generated: {OUTPUT_REPORT}")
    print(f"Global D = {global_density:.4f}")


if __name__ == "__main__":
    run_r0()

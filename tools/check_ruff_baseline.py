import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

BASELINE_FILE = Path(".ruff-baseline.json")

def get_fingerprint(diag: dict) -> str:
    filename = Path(diag["filename"])
    try:
        if filename.is_absolute():
            filename = filename.relative_to(Path.cwd())
    except ValueError:
        pass
    return f"{filename.as_posix()}:{diag['code']}:{diag['message']}"

def get_current_errors_raw() -> list[dict]:
    result = subprocess.run(
        ["ruff", "check", ".", "--output-format=json"],
        capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        print(f"❌ FATAL: Ruff execution failed (code {result.returncode})")
        print(result.stderr)
        sys.exit(2)
    try:
        return json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        print("❌ FATAL: Failed to parse Ruff JSON output.")
        sys.exit(2)

def load_baseline_raw() -> list[dict]:
    if not BASELINE_FILE.exists():
        print(f"❌ FATAL: {BASELINE_FILE} missing. Run 'make lint-update'.")
        sys.exit(2)
    try:
        return json.loads(BASELINE_FILE.read_text())
    except json.JSONDecodeError:
        print(f"❌ FATAL: {BASELINE_FILE} is corrupted.")
        sys.exit(2)

def update_baseline():
    current_raw = get_current_errors_raw()
    current = Counter(get_fingerprint(d) for d in current_raw)
    baseline = Counter(get_fingerprint(d) for d in load_baseline_raw()) if BASELINE_FILE.exists() else Counter()

    new_errors = current - baseline
    fixed_errors = baseline - current

    print("📊 Baseline Delta Report:")
    print(f"  Total errors now: {sum(current.values())}")
    print(f"  Total errors in old baseline: {sum(baseline.values())}")
    
    if new_errors:
        print(f"  ⚠️  {sum(new_errors.values())} errors ADDED:")
        for fp, count in new_errors.items():
            print(f"    +{count} {fp}")
    if fixed_errors:
        print(f"  ✅ {sum(fixed_errors.values())} errors FIXED:")
        for fp, count in fixed_errors.items():
            print(f"    -{count} {fp}")

    BASELINE_FILE.write_text(json.dumps(current_raw, indent=2) + "\n")
    print(f"✅ Baseline updated. Review {BASELINE_FILE} before committing!")

def check_baseline():
    current_raw = get_current_errors_raw()
    current = Counter(get_fingerprint(d) for d in current_raw)
    baseline = Counter(get_fingerprint(d) for d in load_baseline_raw())

    new_errors = current - baseline
    fixed_errors = baseline - current

    if new_errors:
        print(f"❌ Found {sum(new_errors.values())} NEW lint errors:")
        for fp, count in new_errors.items():
            print(f"  +{count} {fp}")
        sys.exit(1)

    print(f"✅ No new lint errors. ({sum(current.values())} debt, {sum(fixed_errors.values())} fixed)")
    sys.exit(0)

if __name__ == "__main__":
    if "--update" in sys.argv:
        update_baseline()
    else:
        check_baseline()

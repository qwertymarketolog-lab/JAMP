import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO = "qwertymarketolog-lab/JAMP"
EXPECTED_FROZEN_SHA = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
CSV_FILENAME = "jamp_audit_master_registry_v3.csv"


class GhApiError(RuntimeError):
    """Ошибка запроса к GitHub CLI/API."""
    pass


def _decode_json_pages(stdout, endpoint):
    """Декодирование вывода `gh api --paginate --slurp`."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GhApiError(
            f"Invalid JSON from endpoint {endpoint}: {exc.msg} at char {exc.pos}"
        ) from exc

    if not isinstance(payload, list):
        raise GhApiError(f"Unexpected paginated response shape from {endpoint}: expected list")
    return payload


def _merge_pages(pages, endpoint):
    """Безопасное слияние страниц с проверкой total_count."""
    if not pages:
        raise GhApiError(f"No page payloads returned for {endpoint}")

    if all(isinstance(page, list) for page in pages):
        return [item for page in pages for item in page]

    if all(isinstance(page, dict) for page in pages):
        if all("workflow_runs" in page for page in pages):
            merged = dict(pages[0])
            all_runs = []
            total_counts = set()
            for page in pages:
                runs = page.get("workflow_runs", [])
                if isinstance(runs, list):
                    all_runs.extend(runs)
                tc = page.get("total_count")
                if tc is not None:
                    total_counts.add(tc)

            if len(total_counts) > 1:
                raise GhApiError(f"Inconsistent total_count values across pages for {endpoint}: {total_counts}")

            expected_tc = total_counts.pop() if total_counts else len(all_runs)
            if len(all_runs) != expected_tc:
                raise GhApiError(
                    f"Workflow runs count mismatch for {endpoint}: got {len(all_runs)}, expected total_count {expected_tc}"
                )
            merged["workflow_runs"] = all_runs
            merged["total_count"] = expected_tc
            return merged

        if len(pages) == 1:
            return pages[0]
        raise GhApiError(f"Cannot safely merge {len(pages)} object-shaped pages from {endpoint}")

    raise GhApiError(f"Inconsistent page response types from {endpoint}")


def run_gh_api(endpoint):
    """Read-only постраничный запрос GitHub API с обработкой системных ошибок."""
    try:
        result = subprocess.run(
            ["gh", "api", "--paginate", "--slurp", endpoint],
            capture_output=True,
            text=True,
            check=True,
        )
        pages = _decode_json_pages(result.stdout, endpoint)
        return _merge_pages(pages, endpoint), None
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, GhApiError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        message = f"GitHub API request failed for {endpoint}: {detail.strip()}"
        print(f"[UNKNOWN / HOLD] {message}")
        return None, message


def run_gh_api_single(endpoint):
    """Read-only одиночный запрос GitHub API с обработкой системных ошибок."""
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=True,
        )
        try:
            return json.loads(result.stdout), None
        except json.JSONDecodeError as exc:
            message = f"Invalid JSON from endpoint {endpoint}: {exc.msg} at char {exc.pos}"
            print(f"[UNKNOWN / HOLD] {message}")
            return None, message
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        message = f"GitHub API request failed for {endpoint}: {detail.strip()}"
        print(f"[UNKNOWN / HOLD] {message}")
        return None, message


def _validate_inventory(baseline_main_sha, branches_raw, prs_raw, ci_raw):
    """Проверка полноты и согласованности инвентаризации."""
    errors = []
    if not isinstance(branches_raw, list) or len(branches_raw) == 0:
        errors.append("Branch inventory is empty or malformed.")
        return False, errors

    main_found = False
    for b in branches_raw:
        if isinstance(b, dict) and b.get("name") == "main":
            main_found = True
            b_sha = b.get("commit", {}).get("sha")
            if b_sha != baseline_main_sha:
                errors.append(f"Main SHA changed between baseline ({baseline_main_sha}) and inventory ({b_sha}).")
    if not main_found:
        errors.append("Main branch not found in branch inventory.")

    if not isinstance(prs_raw, list):
        errors.append("PR inventory is malformed.")

    if not isinstance(ci_raw, dict) or "workflow_runs" not in ci_raw:
        errors.append("CI inventory is malformed.")

    return len(errors) == 0, errors


def _write_csv_atomically(records, output_path, fieldnames):
    """Записать CSV во временный файл и атомарно заменить целевой файл."""
    output_path = Path(output_path)
    with tempfile.NamedTemporaryFile(
        "w", dir=output_path.parent, delete=False, newline="", encoding="utf-8"
    ) as tf:
        temp_name = tf.name
        writer = csv.DictWriter(tf, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(records)
    try:
        os.replace(temp_name, output_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return output_path


def execute_controlled_audit():
    print("=== JAMP Controlled Read-Only Audit v3 Fixed ===")
    errors = []

    print("[1/5] Fetching baseline main HEAD SHA...")
    main_info, err = run_gh_api_single(f"repos/{REPO}/branches/main")
    if err:
        errors.append(err)
    baseline_main_sha = main_info.get("commit", {}).get("sha") if isinstance(main_info, dict) else None
    print(f"      Main HEAD SHA: {baseline_main_sha or 'UNKNOWN / HOLD'}")

    print("[2/5] Checking Frozen Core (src/jamp/run.py)...")
    file_info, err = run_gh_api_single(f"repos/{REPO}/contents/src/jamp/run.py")
    if err:
        errors.append(err)
    actual_blob = file_info.get("sha") if isinstance(file_info, dict) else None

    if actual_blob is None:
        delta_status = "UNKNOWN / HOLD"
        errors.append("Frozen Core blob could not be retrieved")
    elif actual_blob == EXPECTED_FROZEN_SHA:
        delta_status = 0
        print(f"      [VERIFIED] Blob matches: {actual_blob} (Δ = 0)")
    else:
        delta_status = "MISMATCH / HOLD"
        errors.append(f"Frozen core mismatch: expected {EXPECTED_FROZEN_SHA}, got {actual_blob}")
        print(f"      [HOLD] Blob mismatch: {actual_blob}")

    print("[3/5] Fetching branches, PRs, and CI runs...")
    branches_raw, err1 = run_gh_api(f"repos/{REPO}/branches?per_page=100")
    if err1:
        errors.append(err1)

    prs_raw, err2 = run_gh_api(f"repos/{REPO}/pulls?state=all&per_page=100")
    if err2:
        errors.append(err2)

    ci_raw, err3 = run_gh_api(f"repos/{REPO}/actions/runs?per_page=20")
    if err3:
        errors.append(err3)

    inventory_ok, val_errors = _validate_inventory(
        baseline_main_sha, branches_raw, prs_raw, ci_raw
    )
    errors.extend(val_errors)

    inventory_complete = (
        baseline_main_sha is not None and
        delta_status == 0 and
        inventory_ok and
        not errors
    )

    print(f"      Inventory complete status: {inventory_complete}")

    if not inventory_complete:
        print("[HOLD] Inventory validation failed or errors encountered. CSV generation is BLOCKED.")
        print(f"      Encountered errors: {errors}")
        return {
            "inventory_complete": False,
            "main_sha": baseline_main_sha,
            "frozen_core_delta": delta_status,
            "errors": errors
        }

    print("[4/5] Building registry records...")
    branches = [
        {"branch": b.get("name"), "sha": b.get("commit", {}).get("sha")}
        for b in branches_raw if isinstance(b, dict)
    ]

    pr_map = {}
    for pr in prs_raw:
        if not isinstance(pr, dict):
            continue
        head = pr.get("head") or {}
        ref = head.get("ref")
        sha = head.get("sha")
        if ref and sha:
            pr_map.setdefault(ref, []).append({
                "number": pr.get("number"),
                "state": pr.get("state"),
                "merged": pr.get("merged_at") is not None,
                "head_sha": sha
            })

    ci_map = {}
    for run in ci_raw.get("workflow_runs", []):
        if not isinstance(run, dict):
            continue
        sha = run.get("head_sha")
        if sha:
            ci_map.setdefault(sha, []).append({
                "run_id": run.get("id"),
                "workflow": run.get("name") or run.get("path"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion")
            })

    master_records = []
    for b in branches:
        b_name = b["branch"]
        b_sha = b["sha"]
        matched_prs = pr_map.get(b_name, [])
        matched_ci = ci_map.get(b_sha, [])

        pr_summary = ";".join(f"#{pr['number']}@{pr['head_sha']}" for pr in matched_prs) if matched_prs else "N/A"
        pr_state = ";".join(sorted({str(pr.get("state")) for pr in matched_prs})) if matched_prs else "N/A"
        ci_summary = f"{len(matched_ci)} runs" if matched_ci else "No CI runs for exact SHA"

        if b_name == "main":
            rec, reason = "KEEP", "Protected main branch baseline"
        elif matched_prs and any(pr.get("state") == "open" for pr in matched_prs):
            rec, reason = "KEEP", "Active linked PR(s) present"
        elif b_sha == baseline_main_sha:
            rec, reason = "ARCHIVE", "Points directly to current main HEAD baseline"
        elif matched_prs and any(pr.get("merged") for pr in matched_prs):
            rec, reason = "ARCHIVE", "Linked PR is merged"
        else:
            rec, reason = "HOLD", "Unlinked branch or insufficient evidence"

        master_records.append({
            "branch": b_name,
            "sha": b_sha,
            "pr_info": pr_summary,
            "pr_state": pr_state,
            "ci_info": ci_summary,
            "recommendation": rec,
            "reason": reason
        })

    print("[5/5] Writing CSV atomically...")
    fieldnames = ["branch", "sha", "pr_info", "pr_state", "ci_info", "recommendation", "reason"]

    output_path = _write_csv_atomically(master_records, Path(CSV_FILENAME), fieldnames)

    print(f"[SUCCESS] Registry successfully written atomically to {output_path.resolve()} with {len(master_records)} records.")
    return {
        "inventory_complete": True,
        "main_sha": baseline_main_sha,
        "frozen_core_delta": delta_status,
        "csv_path": str(output_path.resolve()),
        "branch_count": len(master_records)
    }


if __name__ == "__main__":
    execute_controlled_audit()

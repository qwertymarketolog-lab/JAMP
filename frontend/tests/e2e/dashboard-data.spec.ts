import { expect, test } from "@playwright/test";

test("overview and history render persisted API contracts without promoting CLEAN to VERIFIED", async ({ page }) => {
  await page.route("**/v1/stats", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ total_checks: 2, hallucinations_caught: 1, inconclusive: 1, status_counts: { CLEAN: 0, SUSPICIOUS: 0, HALLUCINATION_CAUGHT: 1, INCONCLUSIVE: 1, INTEGRITY_VIOLATED: 0 }, time_window: "all_time", denominator: "persisted_verdict_rows (one row per organization/idempotency_key)" }),
  }));
  await page.route("**/v1/verdicts?limit=20&offset=0", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ items: [{ verdict_id: "e2e-verdict-1", status: "CLEAN", package: "fixture-package", created_at: "2026-11-16T00:00:00Z", code_hash: "a".repeat(64) }], limit: 20, offset: 0, total: 1 }),
  }));
  await page.goto("/dashboard/login");
  await page.locator('input[name="api_key"]').fill("e2e-test-key");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Всего сохранённых проверок")).toBeVisible();
  await expect(page.getByText("2", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "История" }).click();
  await expect(page.getByText("CLEAN · не эквивалент VERIFIED")).toBeVisible();
  await expect(page.getByText("fixture-package")).toBeVisible();
});

import { expect, test } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/dashboard/login");
  await page.locator('input[name="api_key"]').fill("e2e-test-key");
  await page.getByRole("button", { name: "Войти" }).click();
}

test("overview and history render persisted API contracts without promoting CLEAN to VERIFIED", async ({ page }) => {
  await page.route("**/v1/stats", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ total_checks: 2, hallucinations_caught: 1, inconclusive: 1, status_counts: { CLEAN: 0, SUSPICIOUS: 0, HALLUCINATION_CAUGHT: 1, INCONCLUSIVE: 1, INTEGRITY_VIOLATED: 0 }, time_window: "all_time", denominator: "persisted_verdict_rows (one row per organization/idempotency_key)" }),
  }));
  await page.route("**/v1/verdicts*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ items: [{ verdict_id: "e2e-verdict-1", status: "CLEAN", package: "fixture-package", created_at: "2026-11-16T00:00:00Z", code_hash: "a".repeat(64) }], limit: 20, offset: 0, total: 1 }),
  }));
  await login(page);
  await expect(page.getByText("Всего сохранённых проверок")).toBeVisible();
  await expect(page.getByText("2", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "История" }).click();
  await expect(page.getByText("CLEAN · не эквивалент VERIFIED")).toBeVisible();
  await expect(page.getByText("fixture-package")).toBeVisible();
  await page.getByRole("button", { name: "Проверка утверждений" }).click();
  await page.getByPlaceholder("Вставьте текст для проверки утверждений…").fill("Цена SBER составляет 5000 рублей.");
  await page.getByRole("button", { name: "Проверить" }).click();
  await expect(page.getByRole("article").getByText("Цена SBER составляет 5000 рублей.")).toBeVisible();
  await expect(page.getByText("CONTRADICTED", { exact: true })).toBeVisible();
});

test("history renders an explicit empty state for an empty persisted result", async ({ page }) => {
  await page.route("**/v1/stats", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ total_checks: 0, hallucinations_caught: 0, inconclusive: 0, status_counts: { CLEAN: 0, SUSPICIOUS: 0, HALLUCINATION_CAUGHT: 0, INCONCLUSIVE: 0, INTEGRITY_VIOLATED: 0 }, time_window: "all_time", denominator: "persisted_verdict_rows (one row per organization/idempotency_key)" }),
  }));
  await page.route("**/v1/verdicts*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ items: [], limit: 20, offset: 0, total: 0 }),
  }));
  await login(page);
  await page.getByRole("button", { name: "История" }).click();
  await expect(page.getByText("Сохранённых вердиктов пока нет. Это пустая история, а не ошибка проверки.")).toBeVisible();
});


test("history searches by package and renders the persisted evidence graph", async ({ page }) => {
  const verdictId = "e2e-verdict-graph";
  const item = { verdict_id: verdictId, status: "INCONCLUSIVE", package: "graph-fixture-package", created_at: "2026-11-17T00:00:00Z", code_hash: "a".repeat(64) };
  await page.route("**/v1/stats", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_checks: 1, hallucinations_caught: 0, inconclusive: 1, status_counts: { CLEAN: 0, SUSPICIOUS: 0, HALLUCINATION_CAUGHT: 0, INCONCLUSIVE: 1, INTEGRITY_VIOLATED: 0 }, time_window: "all_time", denominator: "persisted_verdict_rows" }) }));
  await page.route("**/v1/verdicts*", route => { const q = new URL(route.request().url()).searchParams.get("q") || ""; const match = item.package.includes(q) || item.verdict_id.includes(q); return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: match ? [item] : [], limit: 20, offset: 0, total: match ? 1 : 0 }) }); });
  await page.route("**/v1/verdicts/*/graph", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ nodes: [{ id: "verdict:" + verdictId, type: "verdict", status: "INCONCLUSIVE", package: item.package, code_hash: item.code_hash }, { id: "evidence:e2e-1", type: "evidence", sequence_no: 0, evidence_type: "provenance", payload_hash: "b".repeat(64) }], edges: [{ id: "e2e-edge", source: "evidence:e2e-1", target: "verdict:" + verdictId, relation: "belongs_to" }] }) }));
  await login(page);
  await page.getByRole("button", { name: "История" }).click();
  await page.getByRole("textbox", { name: "Поиск по verdict_id или package" }).fill("graph-fixture-package");
  await page.getByRole("button", { name: "Найти" }).click();
  await expect(page.getByText("graph-fixture-package")).toBeVisible();
  await page.getByRole("button", { name: "Показать граф доказательств" }).click();
  await expect(page.getByRole("img", { name: "Граф сохранённых доказательств" })).toBeVisible();
  await expect(page.getByText("verdict · INCONCLUSIVE")).toBeVisible();
  await expect(page.getByText("evidence · provenance")).toBeVisible();
  await expect(page.getByText("b".repeat(64))).toBeVisible();
});

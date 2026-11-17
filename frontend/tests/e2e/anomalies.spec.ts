import { expect, test } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/dashboard/login");
  await page.locator('input[name="api_key"]').fill("e2e-test-key");
  await page.getByRole("button", { name: "Войти" }).click();
}

const stats = (inconclusive: number) => ({
  total_checks: 0,
  hallucinations_caught: 0,
  inconclusive,
  status_counts: { CLEAN: 0, SUSPICIOUS: 0, HALLUCINATION_CAUGHT: 0, INCONCLUSIVE: inconclusive, INTEGRITY_VIOLATED: 0 },
  time_window: "all_time",
  denominator: "persisted_verdict_rows",
});

const list = (items: unknown[], total: number) => ({
  items, limit: 100, offset: 0, total,
});

test("Anomalies shows only persisted INCONCLUSIVE and SUSPICIOUS verdicts", async ({ page }) => {
  await page.route("**/v1/stats", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(stats(1)),
  }));
  await page.route("**/v1/verdicts?status=INCONCLUSIVE*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify(list([{
      verdict_id: "persisted-inconclusive-1", status: "INCONCLUSIVE",
      package: "real-inconclusive-package", created_at: "2026-11-17T10:00:00Z", code_hash: "a".repeat(64),
    }], 1)),
  }));
  await page.route("**/v1/verdicts?status=SUSPICIOUS*", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify(list([{
      verdict_id: "persisted-suspicious-1", status: "SUSPICIOUS",
      package: "real-suspicious-package", created_at: "2026-11-17T11:00:00Z", code_hash: "b".repeat(64),
    }], 1)),
  }));

  await login(page);
  await page.getByRole("button", { name: "Аномалии" }).click();
  await expect(page.getByRole("heading", { name: "Аномалии", level: 2 })).toBeVisible();
  await expect(page.getByText("Total INCONCLUSIVE · /v1/stats")).toBeVisible();
  const anomalySection = page.locator('section[aria-label="Аномалии"]');
  await expect(anomalySection.getByText("1", { exact: true })).toHaveCount(2);
  await expect(page.getByText("Total SUSPICIOUS · /v1/verdicts")).toBeVisible();
  await expect(page.getByText("persisted-inconclusive-1")).toBeVisible();
  await expect(page.getByText("persisted-suspicious-1")).toBeVisible();
  await expect(page.getByText("AMBIGUOUS", { exact: true })).toHaveCount(0);
});

test("Anomalies shows the empty state only when both persisted totals are zero", async ({ page }) => {
  await page.route("**/v1/stats", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(stats(0)),
  }));
  await page.route("**/v1/verdicts?status=INCONCLUSIVE*", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(list([], 0)),
  }));
  await page.route("**/v1/verdicts?status=SUSPICIOUS*", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(list([], 0)),
  }));

  await login(page);
  await page.getByRole("button", { name: "Аномалии" }).click();
  await expect(page.getByText("Аномалий не обнаружено.")).toBeVisible();
});

test("Settings displays verified session metadata, honest key status and shared integration states", async ({ page }) => {
  const session = {
    authenticated: true,
    org_id: "6f6d6a4e-83bb-4c61-9b6c-0c4a8f6d7c11",
    session_expires_at: "2026-11-19T00:00:00Z",
  };
  await page.route("**/session", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(session),
  }));

  await login(page);
  await page.getByRole("button", { name: "Настройки" }).click();
  await expect(page.getByTestId("organization-id")).toHaveText(session.org_id);
  await expect(page.getByText("NOT_IMPLEMENTED")).toBeVisible();
  await expect(page.getByText("Управление ключами — в разработке.")).toBeVisible();
  await expect(page.getByText("NOT_VERIFIED_IN_UI")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "Beget" }).getByText("NOT_CONNECTED")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "MOEX" }).getByText("ONLINE")).toBeVisible();
});

test("Settings redirects to login when the session endpoint returns 401", async ({ page }) => {
  await page.route("**/session", route => route.fulfill({
    status: 401, contentType: "application/json", body: JSON.stringify({ authenticated: false }),
  }));

  await login(page);
  await page.getByRole("button", { name: "Настройки" }).click();
  await expect(page).toHaveURL(/\/dashboard\/login$/);
});

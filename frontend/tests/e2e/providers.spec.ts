import { expect, test } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/dashboard/login");
  await page.locator('input[name="api_key"]').fill("e2e-test-key");
  await page.getByRole("button", { name: "Войти" }).click();
}

test("Models & Providers shows evidence-backed snapshot statuses without fake health checks", async ({ page }) => {
  let healthRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/v1/providers/health")) healthRequests += 1;
  });

  await login(page);
  await page.getByRole("button", { name: "Модели и провайдеры" }).click();

  await expect(page.getByRole("heading", { name: "Модели и провайдеры", level: 2 })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();

  const row = (name: string) => page.getByRole("row").filter({ hasText: name });
  await expect(row("MOEX").getByText("ONLINE", { exact: true })).toBeVisible();
  await expect(row("AnyModel").getByText("UNKNOWN", { exact: true })).toBeVisible();
  await expect(row("CoinGecko").getByText("UNKNOWN", { exact: true })).toBeVisible();
  await expect(row("Beget").getByText("NOT_CONNECTED", { exact: true })).toBeVisible();
  await expect(row("OpenRouter").getByText("UNKNOWN", { exact: true })).toBeVisible();
  await expect(row("Telegram").getByText("NOT_CONNECTED", { exact: true })).toBeVisible();

  await expect(page.getByText(/offline_mock_only/)).toBeVisible();
  await expect(page.getByText(/старше 24 часов/)).toBeVisible();
  await expect(page.getByText(/не выполняет health-check/)).toBeVisible();
  expect(healthRequests).toBe(0);
});

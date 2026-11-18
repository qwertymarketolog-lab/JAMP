import { expect, test } from "@playwright/test";

const apiKey = process.env.DASHBOARD_E2E_API_KEY;

test("Docker dashboard: root, real organization login, session, navigation and BFF", async ({ page }) => {
  expect(apiKey, "DASHBOARD_E2E_API_KEY must be supplied by the ephemeral Docker test setup").toBeTruthy();

  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  const rootResponse = await page.goto("/");
  expect(rootResponse?.status()).toBe(200);
  await expect(page).toHaveURL(/\/dashboard\/login$/);
  await expect(page.getByRole("heading", { name: "Вход в Станцию доверия" })).toBeVisible();

  await page.locator("#api_key").fill(apiKey!);
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByText("Всего сохранённых проверок")).toBeVisible();

  await page.getByRole("button", { name: "История" }).click();
  await expect(page.getByText("Сохранённых вердиктов пока нет. Это пустая история, а не ошибка проверки.")).toBeVisible();
  await page.getByRole("textbox", { name: "Поиск по verdict_id или package" }).fill("missing-dashboard-e2e-record");
  await page.getByRole("button", { name: "Найти" }).click();
  await expect(page.getByText("По запросу ничего не найдено.")).toBeVisible();
  await page.getByRole("button", { name: "Сбросить" }).click();
  await expect(page.getByText("Сохранённых вердиктов пока нет. Это пустая история, а не ошибка проверки.")).toBeVisible();

  await page.getByRole("button", { name: "Аномалии" }).click();
  await expect(page.getByRole("heading", { name: "Аномалии" })).toBeVisible();
  await expect(page.getByText("Аномалий не обнаружено.")).toBeVisible();

  await page.getByRole("button", { name: "Модели и провайдеры" }).click();
  await expect(page.getByText("MOEX", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Настройки" }).click();
  await expect(page.getByTestId("organization-id")).toHaveText("ci-dashboard-e2e");

  await page.getByRole("button", { name: "Проверка утверждений" }).click();
  await page.getByPlaceholder("Вставьте текст для проверки утверждений…").fill("Обычный текст без проверяемых фактов.");
  const verifyResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/ui_verify") && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Проверить" }).click();
  const verifyResponse = await verifyResponsePromise;
  expect(verifyResponse.status()).toBe(200);
  const payload = await verifyResponse.json();
  expect(payload.status).toBe("NO_CLAIMS");
  await expect(page.getByText("Утверждения не обнаружены")).toBeVisible();

  await expect(page.getByRole("button", { name: /Маркетплейс/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: /^Telegram/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Evidence Vault/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: /^RU/ })).toHaveCount(0);
  expect(pageErrors).toEqual([]);
});

test("invalid API key keeps the browser on an HTML login form", async ({ page }) => {
  await page.goto("/dashboard/login");
  await page.locator("#api_key").fill("invalid-dashboard-e2e-key");
  const loginResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/dashboard/login") && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Войти" }).click();
  const loginResponse = await loginResponsePromise;

  expect(loginResponse.status()).toBe(401);
  expect(loginResponse.headers()["content-type"]).toContain("text/html");
  await expect(page).toHaveURL(/\/dashboard\/login$/);
  await expect(page.getByRole("alert")).toContainText("Не удалось войти");
  await expect(page.locator("form")).toBeVisible();
});

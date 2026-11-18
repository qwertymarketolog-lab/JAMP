import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
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
  await expect(page.getByRole("heading", { name: "Аномалии", level: 2 })).toBeVisible();
  await expect(page.getByText("Аномалий не обнаружено.")).toBeVisible();

  await page.getByRole("button", { name: "Модели и провайдеры" }).click();
  await expect(page.getByText("MOEX", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Настройки" }).click();
  await expect(page.getByTestId("organization-id")).toHaveText("ci-dashboard-e2e");

  await page.getByRole("button", { name: "Проверка утверждений" }).click();
  await page.getByPlaceholder("Вставьте текст для проверки утверждений…").fill("Цена SBER составляет 5000 рублей.");
  const verifyResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/ui_verify") && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Проверить" }).click();
  const verifyResponse = await verifyResponsePromise;
  expect(verifyResponse.status()).toBe(200);
  const payload = await verifyResponse.json();
  expect(payload.status).toBe("COMPLETE_VERIFICATION");
  const claims = payload.claims as Array<{
    raw_text?: string;
    verdict?: string;
    evidence?: Array<{
      source?: string;
      raw_sha256?: string;
      raw_body_base64?: string;
      status_code?: number;
      body_complete?: boolean;
      url?: string;
    }>;
  }>;
  expect(Array.isArray(claims) && claims.length > 0).toBe(true);

  const contradicted = claims.filter((claim) =>
    claim.verdict === "CONTRADICTED" && (claim.raw_text ?? "").toUpperCase().includes("SBER")
  );
  expect(contradicted.length).toBeGreaterThan(0);

  const moexEvidence = contradicted.flatMap((claim) =>
    (claim.evidence ?? []).filter((evidence) => evidence.source === "MOEX")
  );
  expect(moexEvidence.length).toBeGreaterThan(0);
  for (const evidence of moexEvidence) {
    expect(evidence.status_code).toBe(200);
    expect(evidence.body_complete).toBe(true);
    expect(evidence.raw_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(evidence.raw_body_base64).toBeTruthy();
    const recomputed = createHash("sha256")
      .update(Buffer.from(evidence.raw_body_base64!, "base64"))
      .digest("hex");
    expect(recomputed).toBe(evidence.raw_sha256);
    expect(evidence.url).toMatch(/^https:\/\/iss\.moex\.com\/iss\//);
  }

  await expect(page.getByText("CONTRADICTED", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: /Evidence/ }).first().click();
  await expect(page.getByText("MOEX", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(moexEvidence[0].raw_sha256!, { exact: true })).toBeVisible();

  const evidenceDir = resolve(process.cwd(), process.env.MOEX_EVIDENCE_DIR ?? "../artifacts/e2e-moex");
  mkdirSync(evidenceDir, { recursive: true });
  writeFileSync(resolve(evidenceDir, "response.json"), JSON.stringify(payload, null, 2));
  writeFileSync(resolve(evidenceDir, "http-status.txt"), `${verifyResponse.status()}\\n`);
  writeFileSync(resolve(evidenceDir, "result.txt"), "MOEX_E2E=PASS\\n");
  writeFileSync(resolve(evidenceDir, "summary.json"), JSON.stringify({
    status: payload.status,
    trace_id: payload.trace_id,
    contradicted_sber_claims: contradicted.length,
    moex_evidence_items: moexEvidence.length,
    raw_hashes_recomputed: moexEvidence.length,
  }, null, 2));

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

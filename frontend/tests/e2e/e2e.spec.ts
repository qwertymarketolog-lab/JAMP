import { expect, test } from "@playwright/test";

test("requires login and renders CONTRADICTED claim with expandable raw evidence", async ({ page }) => {
  await page.goto("/dashboard/login");
  await page.getByRole("textbox").fill("e2e-test-key");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page).toHaveURL("/");

  await page.getByRole("textbox").fill("Цена SBER составляет 5000 рублей.");
  await page.getByRole("button", { name: "Проверить" }).click();

  const claimCard = page.locator("article").filter({
    hasText: "Цена SBER составляет 5000 рублей.",
  });
  await expect(claimCard).toBeVisible();
  await expect(claimCard.getByText("CONTRADICTED", { exact: true })).toBeVisible();

  await claimCard.getByRole("button", { name: /Evidence/ }).click();
  await expect(claimCard.getByText("source", { exact: true })).toBeVisible();
  await expect(
    claimCard.getByText("MOEX ISS — deterministic E2E fixture (not live data)", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(claimCard.getByText("raw_sha256", { exact: true })).toBeVisible();
  await expect(
    claimCard.getByText(
      "98fca5e0a61077522129f476961c31cef8d8f8f18803fb63d7d67576ab409301",
      { exact: true },
    ),
  ).toBeVisible();
});

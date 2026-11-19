import { expect, test } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/dashboard/login");
  await page.locator('input[name="api_key"]').fill("e2e-test-key");
  await page.getByRole("button", { name: "Войти" }).click();
}

test("unknown persisted verdict statuses use neutral styling, never success green", async ({ page }) => {
  await page.route("**/v1/stats", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      total_checks: 1,
      hallucinations_caught: 0,
      inconclusive: 0,
      status_counts: {
        CLEAN: 0,
        SUSPICIOUS: 0,
        HALLUCINATION_CAUGHT: 0,
        INCONCLUSIVE: 0,
        INTEGRITY_VIOLATED: 0,
      },
      time_window: "all_time",
      denominator: "persisted_verdict_rows",
    }),
  }));
  await page.route("**/v1/verdicts*", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      items: [{
        verdict_id: "e2e-unknown-status",
        status: "FOO",
        package: "unknown-status-fixture",
        created_at: "2026-11-19T00:00:00Z",
        code_hash: "a".repeat(64),
      }],
      limit: 20,
      offset: 0,
      total: 1,
    }),
  }));

  await login(page);
  await page.getByRole("button", { name: "История" }).click();

  const status = page.getByText("FOO", { exact: true });
  await expect(status).toBeVisible();
  await expect(status).toHaveClass(/border-slate-500\/50/);
  await expect(status).toHaveClass(/text-slate-400/);
  await expect(status).not.toHaveClass(/emerald|green/);
});


test("UNKNOWN claim verdict uses neutral styling", async ({ page }) => {
  await login(page);
  await page.route("**/api/ui_verify", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      status: "PARTIAL_VERIFICATION",
      system_warnings: [],
      provider_errors: [],
      trace_id: "e2e_unknown_claim",
      claims: [{
        claim_id: "e2e-unknown-claim",
        raw_text: "Claim with an unknown verdict",
        type: "unknown",
        extracted_value: null,
        unit: "",
        verdict: "UNKNOWN",
        reason: null,
        evidence: [],
        trace_id: "e2e_unknown_claim",
      }],
    }),
  }));
  await page.getByPlaceholder("Вставьте текст для проверки утверждений…").fill("Claim with an unknown verdict");
  await page.getByRole("button", { name: "Проверить" }).click();

  const claim = page.getByRole("article").filter({ hasText: "Claim with an unknown verdict" });
  await expect(claim).toBeVisible();
  await expect(claim).toHaveClass(/border-slate-400/);
  await expect(claim).not.toHaveClass(/emerald|green/);
});

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e-docker",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: "playwright-report-docker", open: "never" }]],
  outputDir: "test-results-docker",
  use: {
    baseURL: "http://127.0.0.1:8002",
    trace: "off",
    ...devices["Desktop Chrome"],
  },
});

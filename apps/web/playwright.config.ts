import { defineConfig, devices } from "@playwright/test";

// localhost, not 127.0.0.1: it must match the redirect URI registered in Keycloak.
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

/*
 * Functional and accessibility tests run anywhere. Screenshot comparisons run only in the pinned Linux
 * Playwright image (`make visual`) because font rendering differs between operating systems (DECISIONS D-007).
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/support/global-setup.ts",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFileName}/{arg}{ext}",
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.002, animations: "disabled" } },
  // The app follows Accept-Language when no language was chosen; the specs are written in Azerbaijani.
  use: { baseURL, locale: "az-AZ", trace: "retain-on-failure" },
  projects: [
    {
      name: "functional",
      testIgnore: /\.visual\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"] },
    },
    // The service worker and the offline store behave differently per engine; only that spec runs here (D-124).
    { name: "pwa-webkit", testMatch: /pwa\.spec\.ts$/, use: { ...devices["Desktop Safari"] } },
    { name: "pwa-firefox", testMatch: /pwa\.spec\.ts$/, use: { ...devices["Desktop Firefox"] } },
    {
      name: "visual",
      testMatch: /\.visual\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "pnpm dev",
        url: `${baseURL}/healthz`,
        reuseExistingServer: true,
        env: { DESIGN_SYSTEM_ENABLED: "true" },
        timeout: 120_000,
      },
});

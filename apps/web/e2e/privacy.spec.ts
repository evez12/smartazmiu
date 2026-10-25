import { readFile } from "node:fs/promises";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { password, signIn } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

test("a user reads the privacy notice and downloads their data", async ({ page }) => {
  await signIn(page, "leyla.hasanova", "/privacy");
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { level: 1, name: "Məxfilik bildirişi" })).toBeVisible();
  await expect(main.getByRole("heading", { name: "Hüquqlarınız" })).toBeVisible();
  await expect(main).toContainText("“Fərdi məlumatlar haqqında” Qanununa");
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  // Acknowledging is recorded once; on reruns the notice is already acknowledged.
  const acknowledge = main.getByRole("button", { name: "Tanış oldum" });
  if (await acknowledge.isVisible()) await acknowledge.click();
  await expect(main.getByText(/Siz bu bildirişlə .* tanış olmusunuz\./)).toBeVisible();

  await page.goto("/");
  await expect(page.getByRole("main").getByText("Məxfilik bildirişi ilə tanış olun")).toHaveCount(
    0,
  );

  await page.goto("/profile");
  await expect(
    page.getByRole("main").getByText(/Versiya 2026-10, .* tanış olmusunuz\./),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("main").getByRole("link", { name: "Məlumatlarımı yükləyin" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^smartazmiu-melumatlarim-\d{4}-\d{2}-\d{2}\.json$/);
  const document = JSON.parse(await readFile((await file.path())!, "utf8"));
  expect(document.account.email).toBe("leyla.hasanova@smartazmiu.test");
  expect(document.roles).toContain("teacher");
  expect(document.consents.map((c: { purpose: string }) => c.purpose)).toContain("privacy_notice");
});

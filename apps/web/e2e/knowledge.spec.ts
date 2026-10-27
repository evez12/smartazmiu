import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { openPage, password, signIn, test } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

// Read-only smoke over the Sprint 7–9 screens with a seeded student of 765a2 (D-083, D-084): nothing is created.
const AYSEL = "aysel.mammadova";

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

test("guides, subject cards, saved messages and topics render for a student", async ({ page }) => {
  await signIn(page, AYSEL, "/guides");
  await expect(page.getByRole("heading", { level: 1, name: "Bələdçilər" })).toBeVisible();
  await expect(page.getByText("Tələbə məsləhətidir, rəsmi məlumat deyil").first()).toBeVisible();
  await expectNoSeriousViolations(page);

  const directory = await page
    .getByRole("link", { name: /Mikroiqtisadiyyat\s*IQT-2101/ })
    .first()
    .getAttribute("href");
  await openPage(page, directory!);
  await expect(page.getByRole("heading", { level: 1, name: "Mikroiqtisadiyyat" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Bütün bələdçilərdən soruşun" })).toBeVisible();
  await expectNoSeriousViolations(page);

  await openPage(page, `${directory}/tips`);
  await expect(
    page.getByRole("heading", { level: 1, name: "Fənn kartları: Mikroiqtisadiyyat" }),
  ).toBeVisible();
  await expectNoSeriousViolations(page);

  await openPage(page, "/saved");
  await expect(page.getByRole("heading", { level: 1, name: "Saxlanılanlar" })).toBeVisible();
  await expectNoSeriousViolations(page);

  await openPage(page, "/chat");
  await page
    .getByRole("navigation", { name: "Kanallar" })
    .getByRole("link", { name: /Mikroiqtisadiyyat/ })
    .first()
    .click();
  const topics = page.getByRole("navigation", { name: "Mövzular" });
  await expect(topics.getByRole("button", { name: "#suallar" })).toBeVisible();
  await topics.getByRole("button", { name: "#suallar" }).click();
  await expect(page.getByRole("checkbox", { name: /Anonim soruşun/ })).toBeVisible();
  await topics.getByRole("button", { name: "#materiallar" }).click();
  await expect(page.getByRole("link", { name: "Fənnin materiallarına baxın" })).toBeVisible();
  await page.getByRole("button", { name: /Faydalı/ }).click();
  await expect(page.getByRole("dialog", { name: "Faydalı mesajlar" })).toBeVisible();
});

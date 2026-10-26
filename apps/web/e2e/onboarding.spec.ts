import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";

import { openPage, password, signIn, test } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

/*
 * Sprint 6 onboarding: a new account sees the tour on the dashboard, can step through it, and once closed it
 * stays closed on the next visit; the profile page brings it back (D-072). A throwaway account, so the seeded
 * users keep their state.
 */
test("a new student steps through the tour, closes it and brings it back", async ({
  page,
  accounts,
}) => {
  await signIn(
    page,
    await accounts.create("student", { givenName: "Səbinə", familyName: "Rzayeva" }),
  );
  const tour = page.getByRole("region", { name: "SmartAzMİU ilə tanışlıq" });
  await expect(tour).toContainText("Addım 1 / 5");
  await expect(tour.getByRole("heading", { name: "Dərs cədvəli" })).toBeVisible();
  // Without imported data the dashboard explains instead of failing (§13.1).
  await expect(
    page.getByText("Qrupunuz, fənləriniz və dərs cədvəliniz hələ idxal olunmayıb."),
  ).toBeVisible();
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  await tour.getByRole("button", { name: "Növbəti" }).click();
  await expect(tour.getByRole("heading", { name: "Fənn və qrup kanalları" })).toBeVisible();
  await tour.getByRole("button", { name: "Tanışlığı bağlayın" }).click();
  await expect(tour).toHaveCount(0);
  await openPage(page, "/");
  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();
  await expect(tour).toHaveCount(0);

  await openPage(page, "/profile");
  await page.getByRole("button", { name: "Tanışlıq turunu yenidən göstərin" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(tour).toContainText("Addım 1 / 5");
});

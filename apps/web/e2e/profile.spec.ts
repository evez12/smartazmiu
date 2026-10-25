import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { password, signIn } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

// A valid 1×1 PNG; the API crops and re-encodes it to a 512 px WebP.
const PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

test("student sets a photo, bio and privacy settings", async ({ page }) => {
  await signIn(page, "ramin.aliyev", "/profile");
  await expect(page.getByRole("heading", { level: 1, name: "Profil" })).toBeVisible();
  // Whether the group is shown depends on the sample import (staff.spec.ts), which may not have run yet.
  await expect(page.getByRole("heading", { name: "Qrup və ixtisas" })).toBeVisible();

  const picker = page.getByRole("main").locator("input[type=file]");
  await picker.setInputFiles({ name: "ramin.png", mimeType: "image/png", buffer: PIXEL });
  await expect(page.getByText("Şəkil yeniləndi").first()).toBeVisible();
  await expect(page.getByLabel("Şəkli dəyişin")).toBeAttached();
  const photo = await page.request.get(
    (await page.locator("main img").first().getAttribute("src"))!,
  );
  expect(photo.headers()["content-type"]).toBe("image/webp");

  const bio = `Statistika üzrə qeydlərimi paylaşa bilərəm. ${Date.now()}`;
  await page.getByRole("textbox", { name: "Haqqınızda" }).fill(bio);
  await page.getByRole("radio", { name: "Yalnız bələdçilər və müəllimlər" }).check();
  await page.getByRole("radio", { name: "Bütün istifadəçilər" }).check();
  await page.getByRole("button", { name: "Yadda saxlayın" }).click();
  await expect(page.getByText("Profil yadda saxlanıldı").first()).toBeVisible();

  await page.reload();
  await expect(page.getByRole("textbox", { name: "Haqqınızda" })).toHaveValue(bio);
  await expect(page.getByRole("radio", { name: "Bütün istifadəçilər" })).toBeChecked();
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  // Back to the most private settings, so reruns start from the defaults.
  await page.getByRole("radio", { name: "Heç kim" }).last().check();
  await page.getByRole("button", { name: "Yadda saxlayın" }).click();
  await expect(page.getByText("Profil yadda saxlanıldı").first()).toBeVisible();
});

test("the photo controls work from the keyboard", async ({ page }) => {
  await signIn(page, "ramin.aliyev", "/profile");
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { level: 1, name: "Profil" })).toBeVisible();
  const picker = main.locator("input[type=file]");
  await picker.focus();
  await expect(picker).toBeFocused();
  // The visually hidden input draws its focus ring on the visible button.
  const outline = await picker
    .locator("xpath=..")
    .evaluate((label) => getComputedStyle(label).outlineStyle);
  expect(outline).toBe("solid");
});

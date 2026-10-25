import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { password, signIn } from "./support/auth";

/*
 * Sign-in, sign-out and the shell, through Keycloak with the seeded test users.
 * Needs the running stack and the shared test-user password from .env (`make e2e` exports it).
 */
test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

test("student signs in, reaches the dashboard and signs out", async ({ page }) => {
  await signIn(page, "aysel.mammadova");
  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();
  const profile = page.getByRole("button", { name: /Profil menyusu/ });
  await expect(profile).toContainText("Aysel Məmmədova");
  await expect(profile).toContainText("Tələbə");

  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  await profile.click();
  await page.getByRole("menuitem", { name: "Çıxış edin" }).click();
  await expect(page).toHaveURL(/\/login\?status=signed_out/);
  await expect(page.getByText("Hesabdan çıxdınız")).toBeVisible();

  // The Keycloak session is gone too: signing in again asks for credentials.
  await page.getByRole("link", { name: "Universitet hesabı ilə daxil olun" }).click();
  await expect(page.getByRole("heading", { name: "Hesabınıza daxil olun" })).toBeVisible();
});

test("roles from the identity provider are shown in the profile menu", async ({ page }) => {
  await signIn(page, "nigar.ismayilova");
  await expect(page.getByRole("button", { name: /Profil menyusu/ })).toContainText(
    "Tələbə · Moderator",
  );
});

test("a crafted returnTo cannot leave the site", async ({ page }) => {
  await page.goto("/login?returnTo=//evil.example/steal");
  const href = await page
    .getByRole("link", { name: "Universitet hesabı ilə daxil olun" })
    .getAttribute("href");
  expect(href).toBe("/auth/signin?returnTo=%2F");
});

test.describe("mobile shell", () => {
  test.use({ viewport: { width: 320, height: 720 } });

  test("uses the bottom tab bar and navigation sheet without sideways scroll", async ({ page }) => {
    await signIn(page, "ramin.aliyev");
    await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBe(0);

    await page.getByRole("button", { name: "Menyunu açın" }).click();
    const sheet = page.getByRole("dialog", { name: "Menyu" });
    await expect(sheet.getByRole("link", { name: "Ana səhifə" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
  });
});

test("keyboard users reach the content through the skip link", async ({ page }) => {
  await signIn(page, "leyla.hasanova");
  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Əsas məzmuna keçin" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
});

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/*
 * Sprint 1 acceptance: sign in through Keycloak as a test student and see the empty dashboard.
 * Needs the running stack and the shared test-user password from .env (`make e2e` exports it).
 */
const password = process.env.KEYCLOAK_TEST_USER_PASSWORD;

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

async function signIn(page: Page, username: string) {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?returnTo=%2F/);
  await page.getByRole("link", { name: "Universitet hesabı ilə daxil olun" }).click();

  await expect(page.getByRole("heading", { name: "Hesabınıza daxil olun" })).toBeVisible();
  await page.getByLabel("İstifadəçi adı və ya e-poçt").fill(username);
  await page.getByLabel("Şifrə", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Daxil olun" }).click();
}

test("student signs in, sees the empty dashboard and signs out", async ({ page }) => {
  await signIn(page, "aysel.mammadova");

  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();
  await expect(
    page.getByText("Qrupunuz, fənləriniz və dərs cədvəliniz hələ idxal olunmayıb."),
  ).toBeVisible();
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

test("staff are asked to set up two-factor sign-in", async ({ page }) => {
  await signIn(page, "elvin.quliyev");
  await expect(page.getByRole("heading", { name: "İki mərhələli girişi qurun" })).toBeVisible();
  await expect(page.locator("#kc-totp-secret-qr-code")).toBeVisible();
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

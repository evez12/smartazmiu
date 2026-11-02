import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { hydrated, openPage, password, signIn, test } from "./support/auth";
import { undersizedTargets } from "./support/touch-targets";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

/*
 * Sprint 15, Group A: English and Russian next to Azerbaijani (D-113). The language is chosen on the sign-in page
 * (cookie only) or in the profile menu (saved on the account, so another device follows it).
 */
const LANGUAGES = [
  { locale: "az", radio: "Azərbaycanca", signIn: "SmartAzMİU-ya daxil olun", home: "Ana səhifə" },
  { locale: "en", radio: "English", signIn: "Sign in to SmartAzMİU", home: "Home" },
  { locale: "ru", radio: "Русский", signIn: "Вход в SmartAzMİU", home: "Главная" },
] as const;

async function expectNoSeriousViolations(page: Page, where: string) {
  await expect(page).toHaveTitle(/\S/);
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(
    violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => `${v.id}: ${v.nodes.length}`),
    where,
  ).toEqual([]);
}

async function chooseLanguageInMenu(page: Page, language: (typeof LANGUAGES)[number]) {
  await page.getByRole("button", { name: /^.*(Profil menyusu|Profile menu|Меню профиля)/ }).click();
  await page.getByRole("menuitemradio", { name: language.radio }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", language.locale);
}

test("the sign-in page switches between the three languages and remembers the choice", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(page.locator("html[data-hydrated]")).toBeAttached();
  await expect(page.locator("html")).toHaveAttribute("lang", "az");

  for (const language of [LANGUAGES[1], LANGUAGES[2], LANGUAGES[0]]) {
    await page.getByRole("radio", { name: language.radio }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", language.locale);
    await expect(page.getByRole("heading", { level: 1, name: language.signIn })).toBeVisible();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", language.locale);
    await expect(page.getByRole("heading", { level: 1, name: language.signIn })).toBeVisible();
    await expectNoSeriousViolations(page, `/login in ${language.locale}`);
  }
});

test("a browser that asks for Russian gets Russian until a language is chosen", async ({
  browser,
}) => {
  const context = await browser.newContext({ locale: "ru-RU" });
  const page = await context.newPage();
  await page.goto("/login");
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("heading", { level: 1, name: "Вход в SmartAzMİU" })).toBeVisible();
  await context.close();
});

test("the language of an account follows it to another device", async ({
  page,
  browser,
  accounts,
}) => {
  const account = await accounts.create("student", { givenName: "Səbinə", familyName: "Rzayeva" });
  await signIn(page, account);
  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();

  await chooseLanguageInMenu(page, LANGUAGES[2]);
  await expect(page.getByRole("heading", { level: 1, name: "Главная" })).toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  const me = await page.request.get("/api/v1/me");
  expect((await me.json()).locale).toBe("ru");

  // A second browser without any cookie: it asks for Azerbaijani, and the account's language wins once it is known.
  const other = await browser.newContext({ locale: "az-AZ" });
  const second = await other.newPage();
  // The sign-in callback itself writes the account's language, so the first page already comes in it (D-123).
  const callback = second.waitForResponse(
    (response) => new URL(response.url()).pathname === "/auth/callback",
  );
  await signIn(second, account);
  expect((await (await callback).headerValues("set-cookie")).join(" ")).toContain("NEXT_LOCALE=ru");
  await expect(second.locator("html")).toHaveAttribute("lang", "ru");
  await expect(second.getByRole("heading", { level: 1, name: "Главная" })).toBeVisible();

  // A change on the second device reaches the first one on its next page load.
  await openPage(second, "/profile");
  await chooseLanguageInMenu(second, LANGUAGES[1]);
  await expect(second.getByRole("heading", { level: 1, name: "Profile" })).toBeVisible();
  await page.reload();
  await hydrated(page);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await other.close();
});

for (const language of LANGUAGES) {
  test(`the main screens have no serious accessibility violations in ${language.locale}`, async ({
    page,
    accounts,
  }) => {
    await signIn(
      page,
      await accounts.create("student", { givenName: "Səbinə", familyName: "Rzayeva" }),
    );
    await chooseLanguageInMenu(page, language);
    for (const url of ["/", "/schedule", "/notifications/settings", "/forum", "/exams", "/gpa"]) {
      await openPage(page, url);
      await expect(page.locator("html")).toHaveAttribute("lang", language.locale);
      await expectNoSeriousViolations(page, `${url} in ${language.locale}`);
    }
  });
}

test.describe("Russian at 320 px, the longest strings", () => {
  test.use({ viewport: { width: 320, height: 640 }, hasTouch: true, isMobile: true });

  test("no screen scrolls sideways or has a touch target under 44 px", async ({
    page,
    accounts,
  }) => {
    await signIn(
      page,
      await accounts.create("student", { givenName: "Səbinə", familyName: "Rzayeva" }),
    );
    await chooseLanguageInMenu(page, LANGUAGES[2]);
    const screens = [
      "/",
      "/schedule",
      "/chat",
      "/materials",
      "/notifications",
      "/notifications/settings",
      "/profile",
      "/assignments",
      "/quizzes",
      "/exams",
      "/exams/papers",
      "/gpa",
      "/attendance",
      "/guides",
      "/announcements",
      "/events",
      "/forum",
      "/feed",
      "/map",
      "/saved",
      "/support",
      "/privacy",
    ];
    for (const url of screens) {
      await openPage(page, url);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow, `${url}: sideways scroll`).toBeLessThanOrEqual(0);
      expect(await undersizedTargets(page), `${url}: touch targets`).toEqual([]);
    }
    await page.getByRole("button", { name: /Меню профиля/ }).click();
    expect(await undersizedTargets(page), "profile menu").toEqual([]);
  });
});

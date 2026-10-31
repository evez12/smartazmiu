import { randomBytes } from "node:crypto";

import { expect, type Page } from "@playwright/test";

import { openPage, password, signIn, signInWithSecondFactor, test } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

/*
 * Touch targets on a phone (§12.6, CLAUDE.md: ≥ 44 px). A control passes when its own box or the tap area it adds
 * (`touchTarget`, an ::after box that exists only for coarse pointers) is at least 44 px in both directions. Exempt:
 * the skip link (off screen until focused), the hidden inputs behind Radix checkboxes, and links inside a sentence
 * (WCAG 2.5.8), which are recognised by the text around them.
 */
test.use({ viewport: { width: 320, height: 640 }, hasTouch: true, isMobile: true });

const MIN = 44;

async function undersizedTargets(page: Page): Promise<string[]> {
  return page.evaluate((min) => {
    const selector =
      "a[href],button,input:not([type=hidden]),select,textarea,summary,[role=tab],[role=menuitem],[role=switch]";
    return Array.from(document.querySelectorAll<HTMLElement>(selector)).flatMap((el) => {
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      if (box.width < 2 || box.height < 2 || style.visibility === "hidden") return [];
      if (
        el.matches('a[href="#main"],[aria-hidden="true"],[tabindex="-1"]:not(button,a,summary)')
      ) {
        return [];
      }
      const sentence =
        el.tagName === "A" &&
        style.display === "inline" &&
        (el.parentElement?.textContent ?? "").trim().length >
          (el.textContent ?? "").trim().length + 10;
      if (sentence) return [];
      let width = box.width;
      let height = box.height;
      const after = getComputedStyle(el, "::after");
      if (after.content !== "none" && after.display !== "none" && after.position === "absolute") {
        width = Math.max(width, parseFloat(after.width) || 0);
        height = Math.max(height, parseFloat(after.height) || 0);
      }
      if (width >= min - 0.5 && height >= min - 0.5) return [];
      const name = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40);
      return [`${el.tagName.toLowerCase()} "${name}" ${Math.round(width)}×${Math.round(height)}`];
    });
  }, MIN);
}

async function expectTargets(page: Page, url: string) {
  await openPage(page, url);
  expect(await undersizedTargets(page), url).toEqual([]);
}

test("a new student's dashboard, tour, profile and feedback dialog", async ({ page, accounts }) => {
  await signIn(
    page,
    await accounts.create("student", { givenName: "Səbinə", familyName: "Rzayeva" }),
  );
  expect(await undersizedTargets(page), "/").toEqual([]);
  await expectTargets(page, "/profile");
  await expectTargets(page, "/notifications");
  await page.getByRole("button", { name: /Profil menyusu/ }).click();
  expect(await undersizedTargets(page), "profile menu").toEqual([]);
  await page.getByRole("menuitem", { name: "Rəy bildirin" }).click();
  await expect(page.getByRole("dialog", { name: "Rəy bildirin" })).toBeVisible();
  expect(await undersizedTargets(page), "feedback dialog").toEqual([]);
});

test("the feed, the forum and a question with an answer", async ({ page, accounts, records }) => {
  const marker = records.community(randomBytes(6).toString("hex"));
  await signIn(
    page,
    await accounts.create("student", { givenName: "Səbinə", familyName: "Rəsulova" }),
    "/feed",
  );
  await page
    .getByRole("textbox", { name: /Yeni paylaşım/ })
    .fill(`Kitabxana yeni saatlarla işləyir. ${marker}`);
  await page.getByRole("button", { name: "Paylaşın" }).click();
  await page.getByRole("button", { name: /Şərh yazın/ }).click();
  await expect(page.getByRole("textbox", { name: "Şərhiniz" })).toBeVisible();
  expect(await undersizedTargets(page), "/feed").toEqual([]);

  await openPage(page, "/forum");
  await page.getByRole("button", { name: "Sual verin" }).click();
  await page
    .getByRole("textbox", { name: /Sualın başlığı/ })
    .fill(`İmtahan cədvəli haradadır? ${marker}`);
  await page
    .getByRole("textbox", { name: /Sualın mətni/ })
    .fill(`Cədvəl hələ dərc olunmayıb. ${marker}`);
  expect(await undersizedTargets(page), "/forum").toEqual([]);
  await page.getByRole("button", { name: "Sualı dərc edin" }).click();
  await expect(page).toHaveURL(/\/forum\/questions\//);
  await page.getByRole("textbox", { name: "Cavabınız" }).fill(`Elanlar bölməsinə baxın. ${marker}`);
  await page.getByRole("button", { name: "Cavabı göndərin" }).click();
  await expect(page.getByText(`Elanlar bölməsinə baxın. ${marker}`)).toBeVisible();
  expect(await undersizedTargets(page), "question").toEqual([]);
});

test("the assignment and quiz screens of a student", async ({ page, accounts }) => {
  await signIn(
    page,
    await accounts.create("student", { givenName: "Səbinə", familyName: "Rzayeva" }),
    "/assignments",
  );
  await expect(page.getByText("Hələ sizin üçün tapşırıq yoxdur.")).toBeVisible();
  expect(await undersizedTargets(page), "/assignments").toEqual([]);
  await expectTargets(page, "/quizzes");
});

test("the assignment and quiz builders of a staff member", async ({ page, accounts }) => {
  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/assignments/new",
  );
  await expect(page.getByLabel(/Fənn və qrup/)).toBeVisible();
  expect(await undersizedTargets(page), "/assignments/new").toEqual([]);
  await expectTargets(page, "/quizzes/new");
});

test("the attendance screens of a student", async ({ page }) => {
  await signIn(page, "aysel.mammadova", "/attendance");
  await expect(page.getByRole("link", { name: "İştirakı qeyd et" })).toBeVisible();
  expect(await undersizedTargets(page), "/attendance").toEqual([]);
  await expectTargets(page, "/attendance/scan");
});

test("the attendance screen of a staff member", async ({ page, accounts }) => {
  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/attendance",
  );
  await expect(
    page.getByRole("heading", { level: 2, name: "Dərslərin idarə edilməsi" }),
  ).toBeVisible();
  expect(await undersizedTargets(page), "/attendance (staff)").toEqual([]);
});

test("a student's schedule, chat, events and materials", async ({ page }) => {
  await signIn(page, "aysel.mammadova", "/schedule");
  expect(await undersizedTargets(page), "/schedule").toEqual([]);
  await expectTargets(page, "/events");
  await expectTargets(page, "/chat");
  const channel = page.getByRole("navigation", { name: "Kanallar" }).getByRole("link").first();
  await openPage(page, (await channel.getAttribute("href"))!);
  expect(await undersizedTargets(page), "a channel").toEqual([]);
  await openPage(page, "/materials");
  const subject = await page
    .getByRole("link", { name: /Statistika\s*IQT-2102/ })
    .first()
    .getAttribute("href");
  await expectTargets(page, subject!);
});

test("a teacher's upload form", async ({ page }) => {
  await signIn(page, "leyla.hasanova", "/materials");
  const subject = await page
    .getByRole("link", { name: /Statistika\s*IQT-2102/ })
    .first()
    .getAttribute("href");
  await openPage(page, subject!);
  const upload = await page
    .getByRole("link", { name: "Material yükləyin" })
    .first()
    .getAttribute("href");
  await expectTargets(page, upload!);
});

test("staff feedback and report lists", async ({ page, accounts }) => {
  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Elvin", familyName: "Quliyev" }),
    "/admin/feedback",
  );
  expect(await undersizedTargets(page), "/admin/feedback").toEqual([]);
  await expectTargets(page, "/admin/reports");
  await expectTargets(page, "/admin/reports?tab=materials");
});

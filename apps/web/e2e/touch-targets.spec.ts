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

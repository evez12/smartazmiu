import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { openPage, password, signIn, signInWithSecondFactor, test } from "./support/auth";
import { SMALL_PDF } from "./support/files";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
test.describe.configure({ mode: "serial" });

// Seeded accounts (D-020): Leyla Həsənova teaches Statistika (IQT-2102), Aysel Məmmədova of 765a2 takes it.
const LEYLA = { username: "leyla.hasanova", email: "leyla.hasanova@smartazmiu.test" };
const AYSEL = { username: "aysel.mammadova", email: "aysel.mammadova@smartazmiu.test" };

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

/** Follows a link as a full navigation, so the next step waits for the new page to hydrate (D-044). */
async function follow(page: Page, name: string | RegExp) {
  const href = await page.getByRole("link", { name }).first().getAttribute("href");
  await openPage(page, href!);
}

async function openStatistika(page: Page) {
  await follow(page, /Statistika\s*IQT-2102/);
  await expect(page.getByRole("heading", { level: 1, name: "Statistika" })).toBeVisible();
}

/*
 * Sprint 6 Materials v1: a teacher uploads a lecture with copyright consent; once scanned, a student of the
 * course previews it and reports it, and staff see the report (§6.1, D-071).
 */
test("a teacher's upload is scanned, then previewed and reported by a student", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(240_000);
  const marker = records.materials(randomBytes(6).toString("hex"));
  records.rateLimit("material_upload", [LEYLA.email]);
  records.rateLimit("material_report", [AYSEL.email]);
  const title = `Təsviri statistika ${marker}`;

  const teacherContext = await browser.newContext();
  const teacher = await teacherContext.newPage();
  await signIn(teacher, LEYLA.username, "/materials");
  await openStatistika(teacher);
  await follow(teacher, "Material yükləyin");
  await teacher.getByRole("button", { name: "Yükləyin" }).click();
  await expect(teacher.getByText("Faylı paylaşmaq hüququnuzu təsdiq edin.")).toBeVisible();
  await teacher.getByLabel(/^Semestr/).selectOption({ label: "2026 Payız" });
  await teacher.getByLabel(/^Növ/).selectOption("lecture");
  await teacher.getByLabel(/^Ad/).fill(title);
  await teacher.locator('input[type="file"]').setInputFiles({
    name: "Mühazirə 1.pdf",
    mimeType: "application/pdf",
    buffer: SMALL_PDF,
  });
  await teacher.getByRole("checkbox").check();
  await expectNoSeriousViolations(teacher);
  await teacher.getByRole("button", { name: "Yükləyin" }).click();
  await expect(teacher.getByRole("heading", { level: 1, name: title })).toBeVisible({
    timeout: 30_000,
  });
  // The scan runs in the worker; the page shows the result on reload.
  await expect(async () => {
    await teacher.reload();
    await expect(teacher.getByText("Yoxlanılıb")).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 120_000 });
  await teacherContext.close();

  const studentContext = await browser.newContext();
  const student = await studentContext.newPage();
  await signIn(student, AYSEL.username, "/materials");
  await openStatistika(student);
  await expect(student.getByRole("link", { name: "Material yükləyin" })).toHaveCount(0);
  await follow(student, title);
  await student.getByRole("button", { name: "Baxın" }).first().click();
  await expect(student.getByTitle("Mühazirə 1.pdf faylının önizləməsi")).toBeVisible();
  await student.keyboard.press("Escape");
  await student.getByRole("button", { name: "Şikayət edin" }).click();
  const dialog = student.getByRole("dialog", { name: "Materialdan şikayət" });
  await dialog.getByRole("radio", { name: "Səhv və ya köhnəlmiş məzmun" }).click();
  await dialog.getByRole("button", { name: "Şikayət göndərin" }).click();
  await expect(student.getByText("Şikayətiniz qeydə alındı.").first()).toBeVisible();
  await expectNoSeriousViolations(student);
  await studentContext.close();

  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/admin/reports?kind=materials",
  );
  const row = page.getByRole("row").filter({ hasText: marker });
  await expect(row).toContainText("Səhv və ya köhnəlmiş məzmun");
  await expect(row).toContainText("Aysel Məmmədova");
  await expectNoSeriousViolations(page);
});

test.describe("materials on a phone in dark mode", () => {
  test.use({ viewport: { width: 320, height: 640 }, colorScheme: "dark" });

  test("the catalogue fits a 320 px screen and passes the accessibility check", async ({
    page,
  }) => {
    await signIn(page, AYSEL.username, "/materials");
    await openStatistika(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    await expectNoSeriousViolations(page);
  });
});

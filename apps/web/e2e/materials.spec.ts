import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Locator, type Page } from "@playwright/test";

import { hydrated, openPage, password, signIn, signInWithSecondFactor, test } from "./support/auth";
import { EICAR, SMALL_PDF, storedZip } from "./support/files";

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

async function uploadFile(page: Page, file: { name: string; mimeType: string; buffer: Buffer }) {
  await page.locator('input[type="file"]').setInputFiles(file);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Yükləyin" }).click();
}

async function waitForStatus(page: Page, row: Locator, status: string) {
  await expect(async () => {
    await page.reload();
    await hydrated(page);
    await expect(row.getByText(status)).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 120_000 });
}

/*
 * M1 acceptance (§6.1, D-071): an infected new version is blocked and never replaces the clean one; a clean second
 * version becomes current and a student of the course downloads it; a student outside the subject gets "not found".
 */
test("a second version becomes current, an infected one is blocked, outsiders see nothing", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(420_000);
  const marker = records.materials(randomBytes(6).toString("hex"));
  records.rateLimit("material_upload", [LEYLA.email]);
  const title = `Seminar tapşırıqları ${marker}`;
  const versionRow = (p: Page, version: number) =>
    p.getByRole("row").filter({ hasText: `Versiya ${version}` });

  const teacherContext = await browser.newContext();
  const teacher = await teacherContext.newPage();
  await signIn(teacher, LEYLA.username, "/materials");
  await openStatistika(teacher);
  await follow(teacher, "Material yükləyin");
  await teacher.getByLabel(/^Semestr/).selectOption({ label: "2026 Payız" });
  await teacher.getByLabel(/^Növ/).selectOption("seminar");
  await teacher.getByLabel(/^Ad/).fill(title);
  await uploadFile(teacher, {
    name: "Seminar 1.pdf",
    mimeType: "application/pdf",
    buffer: SMALL_PDF,
  });
  await expect(teacher.getByRole("heading", { level: 1, name: title })).toBeVisible({
    timeout: 30_000,
  });
  const materialUrl = new URL(teacher.url()).pathname;
  await waitForStatus(teacher, versionRow(teacher, 1), "Yoxlanılıb");

  await follow(teacher, "Yeni versiya yükləyin");
  await uploadFile(teacher, {
    name: "Seminar 2.zip",
    mimeType: "application/zip",
    buffer: storedZip("eicar.com", EICAR),
  });
  await expect(teacher.getByRole("heading", { level: 1, name: title })).toBeVisible({
    timeout: 30_000,
  });
  await waitForStatus(teacher, versionRow(teacher, 2), "Virus aşkarlandı");
  await expect(versionRow(teacher, 2).getByRole("button", { name: /faylını endirin/ })).toHaveCount(
    0,
  );

  await follow(teacher, "Yeni versiya yükləyin");
  await uploadFile(teacher, {
    name: "Seminar 1 - düzəliş.pdf",
    mimeType: "application/pdf",
    buffer: SMALL_PDF,
  });
  await expect(teacher.getByRole("heading", { level: 1, name: title })).toBeVisible({
    timeout: 30_000,
  });
  await waitForStatus(teacher, versionRow(teacher, 3), "Yoxlanılıb");
  await teacherContext.close();

  const studentContext = await browser.newContext();
  const student = await studentContext.newPage();
  await signIn(student, AYSEL.username, materialUrl);
  await expect(student.getByRole("heading", { level: 1, name: title })).toBeVisible();
  // The rejected version is not listed for students; the clean third one is current.
  await expect(versionRow(student, 2)).toHaveCount(0);
  await expect(versionRow(student, 1)).toBeVisible();
  const download = student.waitForEvent("download");
  await versionRow(student, 3)
    .getByRole("button", { name: "Seminar 1 - düzəliş.pdf faylını endirin" })
    .click();
  expect((await download).suggestedFilename()).toBe("Seminar 1 - düzəliş.pdf");
  await studentContext.close();

  // A student without an enrollment in Statistika learns nothing about the material or the subject.
  await signIn(
    page,
    await accounts.create("student", { givenName: "Səbinə", familyName: "Rəsulova" }),
    materialUrl,
  );
  await expect(page.getByRole("heading", { name: title })).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1, name: "Səhifə tapılmadı" })).toBeVisible();
  await openPage(page, "/materials");
  await expect(page.getByRole("link", { name: /Statistika\s*IQT-2102/ })).toHaveCount(0);
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

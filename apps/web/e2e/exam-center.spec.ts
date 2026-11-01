import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Locator, type Page } from "@playwright/test";

import {
  hydrated,
  openPage,
  password,
  signIn,
  signInWithSecondFactor,
  test,
  type TestAccount,
} from "./support/auth";
import type { TestRecords } from "./support/database";
import { SMALL_PDF } from "./support/files";
import { importFile } from "./support/imports";
import { bakuInput } from "./support/structure";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
test.describe.configure({ mode: "serial" });

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

const OFFERING_LABEL = "Xətti cəbr və riyazi analiz · 765a2 · 2026 Payız";
const SUBJECT = "Xətti cəbr və riyazi analiz";
const HEADER =
  "subject_code,year,term,offering_code,group_codes,date,starts_at,ends_at,room_code\n";

/** A throwaway teacher and student in an offering of their own, imported as the dean's office would. */
async function importOffering(
  page: Page,
  records: TestRecords,
  teacher: TestAccount,
  student: TestAccount,
): Promise<string> {
  const code = records.offering(`E2E-${randomBytes(4).toString("hex")}`);
  records.person(teacher.email);
  records.person(student.email);
  const rows = {
    teachers:
      "university_id,family_name,given_name,email,status\n" +
      `${code}-T,${teacher.familyName},${teacher.givenName},${teacher.email},active\n`,
    students:
      "university_id,family_name,given_name,email,group_code\n" +
      `${code}-S,${student.familyName},${student.givenName},${student.email},765a2\n`,
    offerings:
      "subject_code,year,term,code,group_codes,teacher_ids\n" +
      `RIY-1101,2026,Payız,${code},765a2,${code}-T\n`,
    enrollments:
      "student_id,subject_code,year,term,offering_code,status\n" +
      `${code}-S,RIY-1101,2026,Payız,${code},active\n`,
  };
  for (const [kind, content] of Object.entries(rows)) {
    await importFile(page, { value: kind }, { name: `${kind}-${code}.csv`, content });
  }
  return code;
}

/** The preview of an exam timetable, with its warnings, before it is applied. */
async function previewExams(page: Page, name: string, content: string): Promise<void> {
  await openPage(page, "/admin/imports/new");
  await page.getByRole("combobox", { name: /Məlumat növü/ }).selectOption({ value: "exam_slots" });
  await page
    .getByLabel(/^Fayl/, { exact: false })
    .and(page.locator("input[type=file]"))
    .setInputFiles({ name, mimeType: "text/csv", buffer: Buffer.from(content) });
  await page.getByRole("button", { name: "Faylı yoxlayın" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await expect(page.getByText("Fayl yoxlanıldı, xəta tapılmadı")).toBeVisible();
}

function courseLink(page: Page): Locator {
  return page
    .getByRole("navigation", { name: "Kanallar" })
    .getByRole("region", { name: "Fənlər" })
    .locator("> ul")
    .getByRole("link")
    .first();
}

async function reloadUntil(page: Page, locator: () => Locator, timeout = 120_000) {
  await expect(async () => {
    await page.reload();
    await hydrated(page);
    await expect(locator()).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout });
}

/*
 * Sprint 14 acceptance, group B (D-097): the dean's office imports the exam timetable and is warned about a
 * collision; the student sees the exams with a countdown, the room and a calendar file; and exam mode follows
 * the real slots in the course channel, on screens that are already open, when a slot is added, moved or removed.
 */
test("an exam timetable is imported with warnings, shown to students, and drives exam mode live", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(420_000);
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Quliyeva" });
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const staff = await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" });
  await signInWithSecondFactor(page, staff, "/admin/imports");
  const code = await importOffering(page, records, teacher, student);

  // Two exams of one offering that overlap, in the same room: both are accepted, both are flagged.
  const timetable =
    HEADER +
    `RIY-1101,2026,Payız,${code},,2030-03-12,10:00,11:30,1-301\n` +
    `RIY-1101,2026,Payız,${code},,2030-03-12,11:00,12:30,1-301\n`;
  await previewExams(page, `exam_slots-${code}.csv`, timetable);
  await expect(page.getByRole("heading", { name: "Xəbərdarlıqlar" })).toBeVisible();
  await expect(page.getByText(/Bu fənnin başqa imtahanı ilə üst-üstə düşür/).first()).toBeVisible();
  await expect(page.getByText(/Eyni otaqda başqa imtahanla üst-üstə düşür/).first()).toBeVisible();
  await expectNoSeriousViolations(page);
  await page.getByRole("button", { name: "Tətbiq edin" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Tətbiq edin" }).click();
  await expect(page.getByText("İdxal tətbiq olunub")).toBeVisible();

  // The student sees both exams, the room on the map and the calendar file.
  const studentContext = await browser.newContext();
  const studentPage = await studentContext.newPage();
  await signIn(studentPage, student, "/exams");
  await expect(studentPage.getByRole("heading", { name: SUBJECT })).toHaveCount(2);
  await expect(studentPage.getByText(/gün .* saat qalıb/).first()).toBeVisible();
  await expect(studentPage.getByRole("link", { name: "Otaq 1-301" }).first()).toHaveAttribute(
    "href",
    "/map?room=1-301",
  );
  await expectNoSeriousViolations(studentPage);
  const calendar = await studentPage.request.get("/api/v1/exams/mine.ics");
  expect(calendar.status()).toBe(200);
  expect(await calendar.text()).toContain("BEGIN:VEVENT");

  // The student has the course channel open while the dean's office adds an exam that starts in ten minutes.
  const chatContext = await browser.newContext();
  const chat = await chatContext.newPage();
  await signIn(chat, student, "/chat");
  await expect(courseLink(chat)).toBeVisible({ timeout: 120_000 });
  await courseLink(chat).click();
  await expect(chat.getByRole("combobox", { name: "Mesaj" })).toBeEnabled();
  await expect(chat.getByText(/İmtahan gedir\. Kanal/)).toHaveCount(0);

  await openPage(page, "/exams/slots");
  await expect(page.getByRole("row").filter({ hasText: "2030" })).toHaveCount(2);
  await expect(page.getByText("2 toqquşma").or(page.getByText("1 toqquşma")).first()).toBeVisible();
  await expectNoSeriousViolations(page);
  await page.getByLabel(/Fənn və qrup/).selectOption({ label: OFFERING_LABEL });
  await page.getByLabel(/^Başlama vaxtı/).fill(bakuInput(0.15));
  await page.getByLabel(/^Bitmə vaxtı/).fill(bakuInput(2));
  await page.getByRole("button", { name: "İmtahanı əlavə et" }).click();
  await expect(page.getByText("İmtahan saxlanıldı.").first()).toBeVisible();
  await expect(chat.getByText(/İmtahan gedir\. Kanal/)).toBeVisible({ timeout: 30_000 });
  await expect(chat.getByRole("combobox", { name: "Mesaj" })).toBeDisabled();

  // Moved to a later date the channel opens again, without anyone reloading.
  const near = () =>
    page.getByRole("row").filter({ hasText: SUBJECT }).filter({ hasNotText: "2030" });
  await near().getByRole("button", { name: "Dəyiş" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/^Başlama vaxtı/).fill(bakuInput(24 * 40));
  await dialog.getByLabel(/^Bitmə vaxtı/).fill(bakuInput(24 * 40 + 2));
  await dialog.getByRole("button", { name: "Yadda saxla" }).click();
  await expect(dialog).toBeHidden();
  await expect(chat.getByText(/İmtahan gedir\. Kanal/)).toHaveCount(0, { timeout: 30_000 });
  await expect(chat.getByRole("combobox", { name: "Mesaj" })).toBeEnabled();

  // Removing an exam asks first.
  await near().getByRole("button", { name: "Sil" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Sil" }).click();
  await expect(page.getByRole("row").filter({ hasText: SUBJECT })).toHaveCount(2);
  await chatContext.close();
  await studentContext.close();
});

/*
 * The archive: a student's paper waits for a teacher of the subject, is scanned, approved, and then the whole
 * subject can download it; the form refuses to go on without consent (D-097).
 */
test("a past paper is uploaded with consent, approved by the teacher and downloaded by the student", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(420_000);
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Quliyeva" });
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const outsider = await accounts.create("student", { givenName: "Orxan", familyName: "Rzayev" });
  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/admin/imports",
  );
  await importOffering(page, records, teacher, student);
  const title = records.pastPapers(`Yekun imtahan ${randomBytes(4).toString("hex")}`);

  const studentContext = await browser.newContext();
  const studentPage = await studentContext.newPage();
  await signIn(studentPage, student, "/exams/papers");
  await expect(
    studentPage.getByText(/Cari semestrin imtahan sualları paylaşıla bilməz/),
  ).toBeVisible();
  await expectNoSeriousViolations(studentPage);
  await studentPage.getByRole("button", { name: "Kağızı göndər" }).click();
  await expect(studentPage.getByText("Fayl seçin.")).toBeVisible();
  await expect(studentPage.getByText("Davam etmək üçün təsdiq qutusunu işarələyin.")).toBeVisible();
  // The running semester is not among the choices.
  const semesters = studentPage.getByLabel(/^Semestr/);
  await expect(semesters.locator("option", { hasText: "2026 Payız" })).toHaveCount(0);
  await studentPage.locator('input[type="file"]').setInputFiles({
    name: "Yekun.pdf",
    mimeType: "application/pdf",
    buffer: SMALL_PDF,
  });
  await semesters.selectOption({ label: "2025 Payız" });
  await studentPage.getByLabel(/^Ad/).fill(title);
  await studentPage.getByRole("checkbox", { name: /bitmiş semestrə aid olduğunu/ }).click();
  await studentPage.getByRole("button", { name: "Kağızı göndər" }).click();
  await expect(studentPage.getByText("Kağız göndərildi. Təsdiq gözləyir.").first()).toBeVisible({
    timeout: 30_000,
  });

  // Another student of nothing sees no subject at all.
  const outsiderContext = await browser.newContext();
  const outsiderPage = await outsiderContext.newPage();
  await signIn(outsiderPage, outsider, "/exams/papers");
  await expect(outsiderPage.getByText("Hələ fənniniz yoxdur.")).toBeVisible();
  await outsiderContext.close();

  // The teacher approves once the scan is clean.
  const teacherContext = await browser.newContext();
  const teacherPage = await teacherContext.newPage();
  await signIn(teacherPage, teacher, "/exams/papers");
  const card = () => teacherPage.getByRole("article").filter({ hasText: title });
  await reloadUntil(teacherPage, () => card().getByRole("button", { name: "Qərar ver" }));
  await expect(async () => {
    await teacherPage.reload();
    await hydrated(teacherPage);
    await expect(card()).toBeVisible({ timeout: 2_000 });
    await expect(card().getByText("Yoxlanılır")).toHaveCount(0, { timeout: 2_000 });
  }).toPass({ timeout: 120_000 });
  await card().getByRole("button", { name: "Qərar ver" }).click();
  await teacherPage.getByRole("dialog").getByRole("button", { name: "Təsdiq et" }).click();
  await expect(card().getByText("Təsdiqlənib")).toBeVisible();

  // The student's paper is approved and downloadable.
  await studentPage.reload();
  await hydrated(studentPage);
  const mine = studentPage.getByRole("article").filter({ hasText: title });
  await expect(mine.getByText("Təsdiqlənib")).toBeVisible();
  await expect(mine.getByRole("button", { name: "Yüklə" })).toBeVisible();
  await teacherContext.close();
  await studentContext.close();
});

test("the exam screens fit a 320 px phone", async ({ browser, page, accounts }) => {
  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/exams/slots",
  );
  const context = await browser.newContext({
    viewport: { width: 320, height: 640 },
    hasTouch: true,
  });
  const phone = await context.newPage();
  await signIn(
    phone,
    await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" }),
    "/exams",
  );
  for (const url of ["/exams", "/exams/papers"]) {
    await openPage(phone, url);
    expect(
      await phone.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    ).toBe(false);
    await expectNoSeriousViolations(phone);
  }
  await expectNoSeriousViolations(page);
  await context.close();
});

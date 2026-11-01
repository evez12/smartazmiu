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
import { EICAR, SMALL_PDF, storedZip } from "./support/files";
import { importFile } from "./support/imports";
import { bakuInput } from "./support/structure";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
test.describe.configure({ mode: "serial" });

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

const OFFERING_LABEL = "Xətti cəbr və riyazi analiz · 765a2 · 2026 Payız";

/** A throwaway teacher and student in an offering of their own, imported as the dean's office would. */
async function importOffering(
  page: Page,
  records: TestRecords,
  teacher: TestAccount,
  student: TestAccount,
): Promise<void> {
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
}

async function waitForText(page: Page, locator: () => Locator, timeout = 120_000) {
  await expect(async () => {
    await page.reload();
    await hydrated(page);
    await expect(locator()).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout });
}

/*
 * Sprint 13 acceptance (D-092): a teacher creates an assignment, a student submits a file that is scanned, the
 * teacher grades it and the student sees the points and the feedback; then the same pair run a quiz with a
 * closed and an open question, with the open one scored by hand.
 */
test("an assignment goes from creation to a grade, and a quiz from building to a final score", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(480_000);
  const marker = records.coursework(randomBytes(6).toString("hex"));
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Quliyeva" });
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const outsider = await accounts.create("student", { givenName: "Orxan", familyName: "Rzayev" });

  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/admin/imports",
  );
  await importOffering(page, records, teacher, student);

  const teacherContext = await browser.newContext();
  const teacherPage = await teacherContext.newPage();
  await signIn(teacherPage, teacher, "/assignments/new");
  const title = `Təsviri statistika ${marker}`;
  await teacherPage.getByLabel(/Fənn və qrup/).selectOption({ label: OFFERING_LABEL });
  await teacherPage.getByLabel(/^Başlıq/).fill(title);
  await teacherPage.getByLabel(/^Təlimat/).fill("Verilənləri təhlil edib hesabat yazın.");
  await teacherPage.getByLabel(/^Son tarix/).fill(bakuInput(72));
  await teacherPage.getByLabel(/^Maksimum bal/).fill("50");
  await expectNoSeriousViolations(teacherPage);
  await teacherPage.getByRole("button", { name: "Tapşırığı yaradın" }).click();
  await expect(teacherPage.getByRole("heading", { level: 2, name: title })).toBeVisible();
  const assignmentUrl = teacherPage.url();
  await expect(teacherPage.getByText("0 / 1 tələbə göndərib, 0 qiymətləndirilib")).toBeVisible();

  // The student submits; a classmate outside the offering sees nothing of it.
  const studentContext = await browser.newContext();
  const studentPage = await studentContext.newPage();
  await signIn(studentPage, student, "/assignments");
  await studentPage.getByRole("link", { name: title }).click();
  await hydrated(studentPage);
  await expect(studentPage.getByText("Verilənləri təhlil edib hesabat yazın.")).toBeVisible();
  await studentPage.getByRole("button", { name: "Göndərin" }).click();
  await expect(studentPage.getByText("Fayl seçin.")).toBeVisible();
  await studentPage.locator('input[type="file"]').setInputFiles({
    name: "Hesabat.pdf",
    mimeType: "application/pdf",
    buffer: SMALL_PDF,
  });
  await expectNoSeriousViolations(studentPage);
  await studentPage.getByRole("button", { name: "Göndərin" }).click();
  await expect(studentPage.getByText("Hesabat.pdf")).toBeVisible({ timeout: 30_000 });
  await expect(studentPage.getByText("Göndərilib").first()).toBeVisible();
  await waitForText(studentPage, () => studentPage.getByText("Yoxlanılıb"));

  const strangerContext = await browser.newContext();
  const strangerPage = await strangerContext.newPage();
  await signIn(strangerPage, outsider, "/assignments");
  await expect(strangerPage.getByText("Hələ sizin üçün tapşırıq yoxdur.")).toBeVisible();
  await openPage(strangerPage, new URL(assignmentUrl).pathname);
  await expect(strangerPage.getByText("Verilənləri təhlil edib hesabat yazın.")).toHaveCount(0);
  await strangerContext.close();

  // The teacher sees the work, grades it and gives feedback.
  await openPage(teacherPage, new URL(assignmentUrl).pathname);
  const row = teacherPage.getByRole("row").filter({ hasText: "Nərmin Şükürova" });
  await expect(row).toContainText("Göndərilib");
  await row.getByRole("link", { name: "Qiymətləndirin" }).click();
  await hydrated(teacherPage);
  await expect(teacherPage.getByText("Hesabat.pdf")).toBeVisible();
  await teacherPage.getByLabel(/^Bal \(ən çox 50\)/).fill("60");
  await teacherPage.getByRole("button", { name: "Qiyməti yadda saxlayın" }).click();
  await expect(teacherPage.getByText("0 ilə 50 arasında bal yazın.")).toBeVisible();
  await teacherPage.getByLabel(/^Bal \(ən çox 50\)/).fill("42,5");
  await teacherPage.getByLabel("Rəy").fill("Yaxşı iş, nəticələri daha dəqiq şərh edin.");
  await teacherPage.getByRole("button", { name: "Qiyməti yadda saxlayın" }).click();
  await expect(teacherPage.getByText("Qiymət yadda saxlandı.").first()).toBeVisible();
  await expectNoSeriousViolations(teacherPage);

  await studentPage.reload();
  await hydrated(studentPage);
  await expect(studentPage.getByText("42,5 / 50 bal")).toBeVisible();
  await expect(studentPage.getByText("Yaxşı iş, nəticələri daha dəqiq şərh edin.")).toBeVisible();
  await expect(
    studentPage.getByText("İşiniz qiymətləndirilib, dəyişiklik etmək mümkün deyil."),
  ).toBeVisible();
  await expect(studentPage.getByRole("button", { name: /Göndərin/ })).toHaveCount(0);

  // The quiz: one closed and one open question.
  const quizTitle = `Aralıq test ${marker}`;
  await openPage(teacherPage, "/quizzes/new");
  await teacherPage.getByLabel(/Fənn və qrup/).selectOption({ label: OFFERING_LABEL });
  await teacherPage.getByLabel(/^Başlıq/).fill(quizTitle);
  await teacherPage.getByLabel(/^Vaxt limiti/).fill("20");
  await teacherPage.getByRole("button", { name: "Testi yaradın" }).click();
  await expect(teacherPage.getByRole("heading", { level: 2, name: quizTitle })).toBeVisible();
  await expect(teacherPage.getByText("Qaralama")).toBeVisible();

  await teacherPage.getByLabel(/^Sualın mətni/).fill("Medianın tərifi hansıdır?");
  await teacherPage.getByLabel(/^Bal/).fill("2");
  await teacherPage.getByLabel("Variant 1").fill("Orta qiymət");
  await teacherPage.getByLabel("Variant 2").fill("Ortadakı qiymət");
  await teacherPage.getByRole("checkbox", { name: "2-ci variant düzgündür" }).check();
  await teacherPage.getByRole("button", { name: "Sualı əlavə edin" }).click();
  await expect(teacherPage.getByText("Medianın tərifi hansıdır?")).toBeVisible();
  // The form empties itself once the question is stored.
  await expect(teacherPage.getByLabel(/^Sualın mətni/)).toHaveValue("");

  await teacherPage.getByRole("radio", { name: "Qısa cavab (açıq sual)" }).click();
  await teacherPage.getByLabel(/^Sualın mətni/).fill("Normal paylanmanı izah edin.");
  await teacherPage.getByLabel(/^Bal/).fill("5");
  await teacherPage.getByRole("button", { name: "Sualı əlavə edin" }).click();
  await expect(teacherPage.getByText("Normal paylanmanı izah edin.").first()).toBeVisible();
  await expectNoSeriousViolations(teacherPage);

  await teacherPage.getByRole("button", { name: "Testi dərc edin" }).click();
  await teacherPage
    .getByRole("alertdialog")
    .getByRole("button", { name: "Testi dərc edin" })
    .click();
  await expect(teacherPage.getByText("Dərc olunub")).toBeVisible();
  const quizUrl = new URL(teacherPage.url()).pathname;

  // The student answers; the closed question is graded at once, the open one waits.
  await openPage(studentPage, quizUrl);
  await expect(studentPage.getByText("Kalkulyator")).toHaveCount(0);
  await studentPage.getByRole("button", { name: "Testə başlayın" }).click();
  await expect(studentPage.getByText("Medianın tərifi hansıdır?")).toBeVisible();
  await hydrated(studentPage);
  await expect(studentPage.getByRole("timer")).toContainText("Qalan vaxt: ");
  await studentPage.getByRole("radio", { name: "Ortadakı qiymət" }).click();
  await studentPage
    .getByRole("textbox", { name: "Cavabınız" })
    .fill("Zəng əyrisi şəklində paylanma.");
  await expect(studentPage.getByText("Cavablar yadda saxlanıb.")).toBeVisible({ timeout: 10_000 });
  await expectNoSeriousViolations(studentPage);
  await studentPage.getByRole("button", { name: "Testi bitirin" }).click();
  await studentPage.getByRole("alertdialog").getByRole("button", { name: "Testi bitirin" }).click();
  await expect(studentPage.getByText("2 / 7 bal · 29%")).toBeVisible();
  await expect(
    studentPage.getByText("Açıq suallar hələ qiymətləndirilməyib. Bal dəyişə bilər."),
  ).toBeVisible();

  // The teacher scores the open question; the final result follows.
  await openPage(teacherPage, `${quizUrl}/results`);
  await expect(teacherPage.getByText("Açıq suallar gözləyir")).toBeVisible();
  await teacherPage.getByRole("link", { name: "Baxın" }).click();
  await hydrated(teacherPage);
  await expect(teacherPage.getByText("Zəng əyrisi şəklində paylanma.")).toBeVisible();
  await teacherPage.getByLabel("Bal (0–5)").fill("4");
  await teacherPage.getByRole("button", { name: "Balları yadda saxlayın" }).click();
  await expect(teacherPage.getByText("Ballar yadda saxlandı.").first()).toBeVisible();

  await openPage(studentPage, quizUrl);
  await expect(studentPage.getByText("6 / 7 bal")).toBeVisible();
  await expect(studentPage.getByText("Cəhd sayınız bitib.")).toBeVisible();
  await expect(studentPage.getByRole("button", { name: "Testə başlayın" })).toHaveCount(0);

  await Promise.all([teacherContext.close(), studentContext.close()]);
});

/*
 * D-093: a file the scanner reports as infected never reaches a teacher. The student sees why, nobody can open the
 * file, and a clean replacement becomes the current version. The EICAR test file is built in memory.
 */
test("an infected assignment file is rejected, cannot be opened, and a clean one replaces it", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(360_000);
  const marker = records.coursework(randomBytes(6).toString("hex"));
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Quliyeva" });
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });

  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/admin/imports",
  );
  await importOffering(page, records, teacher, student);

  const teacherContext = await browser.newContext();
  const teacherPage = await teacherContext.newPage();
  await signIn(teacherPage, teacher, "/assignments/new");
  const title = `Virus yoxlaması ${marker}`;
  await teacherPage.getByLabel(/Fənn və qrup/).selectOption({ label: OFFERING_LABEL });
  await teacherPage.getByLabel(/^Başlıq/).fill(title);
  await teacherPage.getByLabel(/^Təlimat/).fill("Hesabatı bir fayl kimi göndərin.");
  await teacherPage.getByLabel(/^Son tarix/).fill(bakuInput(72));
  await teacherPage.getByLabel(/^Maksimum bal/).fill("20");
  await teacherPage.getByRole("button", { name: "Tapşırığı yaradın" }).click();
  await expect(teacherPage.getByRole("heading", { level: 2, name: title })).toBeVisible();
  const assignmentPath = new URL(teacherPage.url()).pathname;

  const studentContext = await browser.newContext();
  const studentPage = await studentContext.newPage();
  await signIn(studentPage, student, "/assignments");
  await studentPage.getByRole("link", { name: title }).click();
  await hydrated(studentPage);
  await studentPage.locator('input[type="file"]').setInputFiles({
    name: "Hesabat.zip",
    mimeType: "application/zip",
    buffer: storedZip("eicar.com", EICAR),
  });
  await studentPage.getByRole("button", { name: "Göndərin" }).click();
  // The file name is on the picker from the moment it is chosen: only the status shows the work was submitted,
  // and reloading before that would abort the upload.
  await expect(studentPage.getByText("Göndərilib").first()).toBeVisible({ timeout: 30_000 });
  await waitForText(studentPage, () => studentPage.getByText("Virus aşkarlandı"));
  await expect(studentPage.getByText("Bu fayl qəbul olunmadı. Başqa fayl göndərin.")).toBeVisible();
  await expect(studentPage.getByRole("button", { name: /faylını endirin/ })).toHaveCount(0);
  await expectNoSeriousViolations(studentPage);

  // The teacher is told the file was rejected and has nothing to open.
  await openPage(teacherPage, assignmentPath);
  const row = teacherPage.getByRole("row").filter({ hasText: "Nərmin Şükürova" });
  await row.getByRole("link", { name: "Qiymətləndirin" }).click();
  await hydrated(teacherPage);
  await expect(teacherPage.getByText("Virus aşkarlandı")).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: /faylını endirin/ })).toHaveCount(0);

  // A clean file replaces it as version 2; the rejected one stays in the history, still not downloadable.
  await studentPage.reload();
  await hydrated(studentPage);
  await studentPage.locator('input[type="file"]').setInputFiles({
    name: "Hesabat.pdf",
    mimeType: "application/pdf",
    buffer: SMALL_PDF,
  });
  await studentPage.getByRole("button", { name: "Yenidən göndərin" }).click();
  await expect(studentPage.getByText("Versiya 2")).toBeVisible({ timeout: 30_000 });
  await waitForText(studentPage, () => studentPage.getByText("Yoxlanılıb"));
  await expect(
    studentPage.getByRole("button", { name: "Hesabat.pdf faylını endirin" }),
  ).toBeVisible();
  await expect(
    studentPage.getByRole("button", { name: "Hesabat.zip faylını endirin" }),
  ).toHaveCount(0);

  await Promise.all([teacherContext.close(), studentContext.close()]);
});

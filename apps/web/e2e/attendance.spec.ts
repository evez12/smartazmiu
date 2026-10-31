import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

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
import { importFile } from "./support/imports";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
test.describe.configure({ mode: "serial" });

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

const OFFERING_LABEL = "Xətti cəbr və riyazi analiz · 765a2 · 2026 Payız";

/** A throwaway teacher and two students in an offering of their own, imported as the dean's office would. */
async function importOffering(
  page: Page,
  records: TestRecords,
  teacher: TestAccount,
  students: TestAccount[],
): Promise<void> {
  const code = records.offering(`E2E-${randomBytes(4).toString("hex")}`);
  records.person(teacher.email);
  for (const student of students) records.person(student.email);
  const rows = {
    teachers:
      "university_id,family_name,given_name,email,status\n" +
      `${code}-T,${teacher.familyName},${teacher.givenName},${teacher.email},active\n`,
    students:
      "university_id,family_name,given_name,email,group_code\n" +
      students
        .map((s, i) => `${code}-S${i},${s.familyName},${s.givenName},${s.email},765a2`)
        .join("\n") +
      "\n",
    offerings:
      "subject_code,year,term,code,group_codes,teacher_ids\n" +
      `RIY-1101,2026,Payız,${code},765a2,${code}-T\n`,
    enrollments:
      "student_id,subject_code,year,term,offering_code,status\n" +
      students.map((_, i) => `${code}-S${i},RIY-1101,2026,Payız,${code},active`).join("\n") +
      "\n",
  };
  for (const [kind, content] of Object.entries(rows)) {
    await importFile(page, { value: kind }, { name: `${kind}-${code}.csv`, content });
  }
}

/** The teacher's screen shows the digits as "042 917"; a student types them with or without the space. */
async function shownDigits(teacherPage: Page): Promise<string> {
  const text = await teacherPage.getByLabel("Altı rəqəmli kod").innerText();
  return text.replace(/\D/g, "");
}

/*
 * Sprint 14 acceptance, group A (D-094): a teacher opens a meeting, a student checks in with the code on the
 * teacher's screen, the teacher marks and unmarks students by hand with a reason, closes the meeting, and each
 * student sees only their own rate while the teacher reads the report. The camera path is covered by unit tests
 * and the API tests: a headless browser has nothing to point at.
 */
test("a meeting is opened, students check in, marks are corrected by hand and the report follows", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(240_000);
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Quliyeva" });
  const first = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const second = await accounts.create("student", { givenName: "Tural", familyName: "Əliyev" });
  const outsider = await accounts.create("student", { givenName: "Orxan", familyName: "Rzayev" });

  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/admin/imports",
  );
  await importOffering(page, records, teacher, [first, second]);

  const teacherContext = await browser.newContext();
  const teacherPage = await teacherContext.newPage();
  await signIn(teacherPage, teacher, "/attendance");
  await expect(
    teacherPage.getByRole("heading", { level: 2, name: "Dərslərin idarə edilməsi" }),
  ).toBeVisible();
  await expect(teacherPage.getByLabel("Fənn")).toContainText(OFFERING_LABEL);
  await expectNoSeriousViolations(teacherPage);
  await teacherPage.getByLabel("Dərsin adı").fill("Mühazirə 5");
  await teacherPage.getByRole("button", { name: "Dərsi aç" }).click();
  await hydrated(teacherPage);
  await expect(
    teacherPage.getByRole("img", { name: "İştirakı qeyd etmək üçün QR kod" }),
  ).toBeVisible();
  await expect(teacherPage.getByText("0 / 2 tələbə")).toBeVisible();
  await expect(teacherPage.getByText(/Yeni kod \d+ saniyə sonra/)).toBeVisible();
  await expectNoSeriousViolations(teacherPage);
  const sessionPath = new URL(teacherPage.url()).pathname;

  // The first student checks in with the digits; the teacher's count follows without a reload.
  const firstContext = await browser.newContext();
  const firstPage = await firstContext.newPage();
  await signIn(firstPage, first, "/attendance/scan");
  await firstPage.getByLabel("Altı rəqəmli kod").fill("000000");
  await firstPage.getByRole("button", { name: "Kodu göndər" }).click();
  await expect(firstPage.getByText("İştirak qeyd olunmadı")).toBeVisible();
  await expect(firstPage.getByText(/Kod düzgün deyil/)).toBeVisible();
  await firstPage.getByLabel("Altı rəqəmli kod").fill(await shownDigits(teacherPage));
  await expectNoSeriousViolations(firstPage);
  await firstPage.getByRole("button", { name: "Kodu göndər" }).click();
  await expect(firstPage.getByText("İştirakınız qeyd olundu")).toBeVisible();
  await expect(teacherPage.getByText("1 / 2 tələbə")).toBeVisible({ timeout: 15_000 });
  const firstRow = teacherPage.getByRole("row").filter({ hasText: "Nərmin Şükürova" });
  await expect(firstRow).toContainText("İştirak edir");
  await expect(firstRow).toContainText("Rəqəmli kod");

  // A second submission is not an error: the student is told they are already recorded.
  await firstPage.getByLabel("Altı rəqəmli kod").fill(await shownDigits(teacherPage));
  await firstPage.getByRole("button", { name: "Kodu göndər" }).click();
  await expect(firstPage.getByText("İştirakınız artıq qeyd olunub")).toBeVisible();

  // Someone outside the course cannot use the code, and cannot see the meeting.
  const outsiderContext = await browser.newContext();
  const outsiderPage = await outsiderContext.newPage();
  await signIn(outsiderPage, outsider, "/attendance/scan");
  await outsiderPage.getByLabel("Altı rəqəmli kod").fill(await shownDigits(teacherPage));
  await outsiderPage.getByRole("button", { name: "Kodu göndər" }).click();
  await expect(outsiderPage.getByText("İştirak qeyd olunmadı")).toBeVisible();
  await openPage(outsiderPage, sessionPath);
  await expect(
    outsiderPage.getByText("Dərs yüklənmədi. Bir az sonra yenidən cəhd edin."),
  ).toBeVisible({ timeout: 15_000 });
  await outsiderContext.close();

  // Manual marks need a reason; the teacher marks the absent student and unmarks the first one.
  const secondRow = teacherPage.getByRole("row").filter({ hasText: "Tural Əliyev" });
  await secondRow.getByRole("button", { name: "İştirak qeyd et" }).click();
  const dialog = teacherPage.getByRole("dialog");
  await dialog.getByRole("button", { name: "İştirak qeyd et" }).click();
  await expect(dialog.getByText("Səbəbi yazın (ən azı 3 simvol).")).toBeVisible();
  await dialog.getByLabel(/^Səbəb/).fill("Telefonu işləmirdi");
  await dialog.getByRole("button", { name: "İştirak qeyd et" }).click();
  await expect(dialog).toBeHidden();
  await expect(secondRow).toContainText("Əl ilə");
  await firstRow.getByRole("button", { name: "İştirakı ləğv et" }).click();
  await dialog.getByLabel(/^Səbəb/).fill("Auditoriyada yox idi");
  await dialog.getByRole("button", { name: "İştirakı ləğv et" }).click();
  await expect(dialog).toBeHidden();
  await expect(firstRow).toContainText("Yoxdur");

  // Closing ends check-in; a late code is refused.
  await teacherPage.getByRole("button", { name: "Qeydi bağla" }).click();
  await expect(teacherPage.getByText("Bu dərsin iştirak qeydi bağlanıb.")).toBeVisible();
  await expect(
    teacherPage.getByRole("img", { name: "İştirakı qeyd etmək üçün QR kod" }),
  ).toHaveCount(0);
  await firstPage.getByLabel("Altı rəqəmli kod").fill("123456");
  await firstPage.getByRole("button", { name: "Kodu göndər" }).click();
  await expect(firstPage.getByText("İştirak qeyd olunmadı")).toBeVisible();

  // Each student sees only their own rate.
  await openPage(firstPage, "/attendance");
  const firstCourse = firstPage.getByRole("listitem").filter({ hasText: OFFERING_LABEL });
  await expect(firstCourse).toContainText("0 / 1 dərs");
  await expect(firstCourse).toContainText("0 %");
  await expectNoSeriousViolations(firstPage);
  const secondContext = await browser.newContext();
  const secondPage = await secondContext.newPage();
  await signIn(secondPage, second, "/attendance");
  const secondCourse = secondPage.getByRole("listitem").filter({ hasText: OFFERING_LABEL });
  await expect(secondCourse).toContainText("1 / 1 dərs");
  await expect(secondCourse).toContainText("100 %");
  await secondCourse.getByRole("link").click();
  await hydrated(secondPage);
  await expect(secondPage.getByText("Mühazirə 5")).toBeVisible();
  await expect(secondPage.getByText("İştirak etdiniz")).toBeVisible();
  await expect(secondPage.getByText("Nərmin Şükürova")).toHaveCount(0);

  // The teacher reads the report and downloads it; a student cannot.
  await openPage(teacherPage, "/attendance");
  await teacherPage.getByRole("link", { name: "Hesabat" }).click();
  await hydrated(teacherPage);
  const reportRow = teacherPage.getByRole("row").filter({ hasText: "Tural Əliyev" });
  await expect(reportRow).toContainText("100 %");
  await expect(teacherPage.getByRole("row").filter({ hasText: "Nərmin Şükürova" })).toContainText(
    "0 %",
  );
  await expectNoSeriousViolations(teacherPage);
  const csvPath = (await teacherPage
    .getByRole("link", { name: "CSV yüklə" })
    .getAttribute("href"))!;
  const csv = await teacherPage.request.get(csvPath);
  expect(csv.status()).toBe(200);
  expect(await csv.text()).toContain("Tural Əliyev");
  expect((await secondPage.request.get(csvPath)).status()).toBe(404);
  await secondContext.close();
  await firstContext.close();
  await teacherContext.close();
});

test("the teacher screen and the scanner fit a 320 px phone", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(180_000);
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Quliyeva" });
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/admin/imports",
  );
  await importOffering(page, records, teacher, [student]);

  const context = await browser.newContext({
    viewport: { width: 320, height: 640 },
    hasTouch: true,
  });
  const phone = await context.newPage();
  await signIn(phone, teacher, "/attendance");
  await phone.getByRole("button", { name: "Dərsi aç" }).click();
  await hydrated(phone);
  await expect(phone.getByRole("img", { name: "İştirakı qeyd etmək üçün QR kod" })).toBeVisible();
  const overflow = () =>
    phone.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(await overflow()).toBe(false);
  await expectNoSeriousViolations(phone);

  const studentContext = await browser.newContext({
    viewport: { width: 320, height: 640 },
    hasTouch: true,
  });
  const studentPhone = await studentContext.newPage();
  await signIn(studentPhone, student, "/attendance/scan");
  await expect(studentPhone.getByRole("button", { name: "Kameranı aç" })).toBeVisible();
  expect(
    await studentPhone.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);
  await expectNoSeriousViolations(studentPhone);
  await studentContext.close();
  await context.close();
});

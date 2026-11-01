import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { password, signIn, signInWithSecondFactor, test } from "./support/auth";
import { importFile } from "./support/imports";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
test.describe.configure({ mode: "serial" });

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

/*
 * Sprint 14 acceptance, group C: a student sees the ÜOMG of the results the dean's office imported, a retake
 * replaces the failed first attempt by default, the rules can be changed, and a simulated course shows its effect.
 */
test("a student calculates the ÜOMG from imported results and simulates a new course", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(300_000);
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Quliyeva" });
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const staff = await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" });
  const code = records.offering(`E2E-${randomBytes(4).toString("hex")}`);
  records.person(teacher.email);
  records.person(student.email);
  await signInWithSecondFactor(page, staff, "/admin/imports");

  // Linear algebra (8 credits) failed in 2024 and was retaken in 2025 Yaz; statistics (10 credits) passed.
  const rows = {
    teachers:
      "university_id,family_name,given_name,email,status\n" +
      `${code}-T,${teacher.familyName},${teacher.givenName},${teacher.email},active\n`,
    students:
      "university_id,family_name,given_name,email,group_code\n" +
      `${code}-S,${student.familyName},${student.givenName},${student.email},765a2\n`,
    offerings:
      "subject_code,year,term,code,group_codes,teacher_ids\n" +
      `RIY-1101,2024,Payız,${code},765a2,${code}-T\n` +
      `RIY-1101,2025,Yaz,${code},765a2,${code}-T\n` +
      `IQT-2102,2025,Payız,${code},765a2,${code}-T\n`,
    enrollments:
      "student_id,subject_code,year,term,offering_code,status,passed,grade\n" +
      `${code}-S,RIY-1101,2024,Payız,${code},completed,false,40\n` +
      `${code}-S,RIY-1101,2025,Yaz,${code},completed,true,80\n` +
      `${code}-S,IQT-2102,2025,Payız,${code},completed,true,90\n`,
  };
  for (const [kind, content] of Object.entries(rows)) {
    await importFile(page, { value: kind }, { name: `${kind}-${code}.csv`, content });
  }

  const context = await browser.newContext();
  const own = await context.newPage();
  await signIn(own, student, "/gpa");
  // (8 * 80 + 10 * 90) / 18 = 85.56: the retake replaced the failed attempt, and the first row says so.
  await expect(own.getByTestId("gpa-total")).toHaveText("85.56");
  await expect(
    own.getByText("71 və yuxarı: tələbə kreditində faiz tətbiq olunmur").first(),
  ).toBeVisible();
  await expect(own.getByText("Təkrarla əvəz olunub")).toBeVisible();
  await expectNoSeriousViolations(own);

  await own.getByRole("radio", { name: /Bütün cəhdlər sayılır/ }).click();
  await expect(own.getByTestId("gpa-total")).toHaveText("71.54");
  await own.getByRole("radio", { name: /Son cəhd əvəz edir/ }).click();
  await expect(own.getByTestId("gpa-total")).toHaveText("85.56");

  await own.getByRole("button", { name: "Fənn əlavə et" }).click();
  await own.getByLabel("1-ci fənn: kredit").fill("6");
  await own.getByLabel("1-ci fənn: semestr balı (0–50)").fill("30");
  await own.getByLabel("1-ci fənn: imtahan balı (0–50)").fill("10");
  // The exam is below 17, so only the 30 semester points count: (1540 + 6 * 30) / 24 = 71.67.
  await expect(own.getByTestId("gpa-simulated")).toHaveText("71.67");
  await expect(own.getByTestId("gpa-delta")).toHaveText("Dəyişiklik: −13.89");
  await expectNoSeriousViolations(own);
  await context.close();
});

test("the calculator fits a 320 px phone", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 320, height: 640 },
    hasTouch: true,
  });
  const phone = await context.newPage();
  await signIn(phone, "aysel.mammadova", "/gpa");
  await expect(phone.getByRole("heading", { level: 2, name: "Hesablama qaydaları" })).toBeVisible();
  await phone.getByRole("button", { name: "Fənn əlavə et" }).click();
  expect(await phone.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(
    false,
  );
  await expectNoSeriousViolations(phone);
  await context.close();
});

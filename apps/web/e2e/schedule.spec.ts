import { randomBytes } from "node:crypto";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { password, signIn, signInWithSecondFactor, test } from "./support/auth";
import { importFile, SEED_DIR } from "./support/imports";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

/** The sample semesters (semesters.csv) that may contain the day the suite runs. */
const SEMESTERS = [
  { year: 2026, term: "Payız", starts: "2026-09-15", ends: "2027-01-31" },
  { year: 2027, term: "Yaz", starts: "2027-02-22", ends: "2027-06-30" },
];
const STAFF_NAME = { givenName: "Günel", familyName: "Səfərova" };
// Registry and campus data the class refers to; each applies as a no-op when already imported.
const REGISTRY = ["faculties", "specialties", "subjects", "semesters", "teachers", "groups"];
const CAMPUS = ["buildings", "floors", "rooms"];

function bakuToday(): { date: string; weekday: number } {
  const date = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Baku" }).format(new Date());
  return { date, weekday: ((new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7) + 1 };
}

async function importSeed(page: Page, kinds: string[]) {
  for (const kind of kinds) {
    await importFile(page, { value: kind }, path.join(SEED_DIR, `${kind}.csv`));
  }
}

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

/*
 * Sprint 3 acceptance: a student opens the homepage, sees today's classes, taps the room and the map highlights
 * it. The day the suite runs may have no classes in the sample timetable, so the test imports its own: a
 * throwaway student in 765a2 with one offering that meets today in room 1-305. The subject has no other offering
 * for 765a2 in these semesters, so the sample enrollment file (which picks offerings by group) stays unambiguous.
 */
test("student goes from today's classes to the room on the map", async ({
  page,
  browser,
  accounts,
}) => {
  test.setTimeout(240_000);
  const today = bakuToday();
  const semester = SEMESTERS.find((s) => s.starts <= today.date && today.date <= s.ends);
  test.skip(!semester, `No sample semester contains ${today.date}`);
  const { year, term } = semester!;

  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const code = `E2E-${randomBytes(4).toString("hex")}`;
  await signInWithSecondFactor(page, await accounts.create("staff", STAFF_NAME), "/admin/imports");
  await importSeed(page, [...REGISTRY, ...CAMPUS]);
  const rows = {
    students: `university_id,family_name,given_name,email,group_code\n${code},Şükürova,Nərmin,${student.email},765a2\n`,
    offerings: `subject_code,year,term,code,group_codes,teacher_ids\nRIY-1101,${year},${term},${code},765a2,\n`,
    enrollments: `student_id,subject_code,year,term,offering_code,status\n${code},RIY-1101,${year},${term},${code},active\n`,
    schedule:
      "subject_code,year,term,offering_code,weekday,starts_at,ends_at,class_type,room_code\n" +
      `RIY-1101,${year},${term},${code},${today.weekday},10:05,11:25,mühazirə,1-305\n`,
  };
  for (const [kind, content] of Object.entries(rows)) {
    await importFile(page, { value: kind }, { name: `${kind}-${code}.csv`, content });
  }

  const context = await browser.newContext();
  const home = await context.newPage();
  await signIn(home, student);
  const main = home.getByRole("main");
  const todayPanel = main.getByRole("region", { name: "Bugünkü dərslər" });
  await expect(todayPanel).toContainText("Xətti cəbr və riyazi analiz");
  await expect(todayPanel).toContainText("10:05–11:25");
  await expectNoSeriousViolations(home);

  await todayPanel.getByRole("link", { name: "1-305 otağını xəritədə göstərin" }).click();
  await expect(home).toHaveURL(/\/map\?room=1-305$/);
  const room = main.locator('[data-room="1-305"]');
  await expect(room).toHaveAttribute("aria-current", "location");
  await expect(main.locator('[aria-current="location"]')).toHaveCount(1);
  await expect(main.getByRole("link", { name: "Tədris korpusu 1" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(main.getByRole("link", { name: "3-cü mərtəbə" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  const facts = main.getByRole("region", { name: "Seçilmiş otaq" });
  await expect(facts).toContainText("1-305");
  await expect(facts).toContainText("Auditoriya");
  await expectNoSeriousViolations(home);

  // The weekly timetable lists the same class and offers the calendar file.
  await home.goto("/schedule");
  await expect(main.getByRole("heading", { level: 1, name: "Dərs cədvəli" })).toBeVisible();
  await expect(main.locator('[aria-current="date"]')).toContainText("Xətti cəbr və riyazi analiz");
  const download = home.waitForEvent("download");
  await main.getByRole("link", { name: "Təqvim faylını yükləyin" }).click();
  expect((await download).suggestedFilename()).toBe("ders-cedveli.ics");
  await expectNoSeriousViolations(home);
  await context.close();
});

test("rooms can be found by code or name, typed without Azerbaijani letters", async ({
  page,
  browser,
  accounts,
}) => {
  test.setTimeout(120_000);
  const staff = await browser.newContext();
  const wizard = await staff.newPage();
  await signInWithSecondFactor(
    wizard,
    await accounts.create("staff", STAFF_NAME),
    "/admin/imports",
  );
  await importSeed(wizard, CAMPUS);
  await staff.close();

  await signIn(page, "aysel.mammadova", "/map");
  await expect(page.getByRole("heading", { level: 1, name: "Kampus xəritəsi" })).toBeVisible();
  const main = page.getByRole("main");

  await main.getByRole("searchbox", { name: "Otaq axtarışı" }).fill("komputer");
  await main.getByRole("button", { name: "Axtarın" }).click();
  const results = main.getByRole("region", { name: "Axtarışın nəticələri" });
  await expect(results.getByRole("link", { name: /^2-310/ })).toBeVisible();
  await results.getByRole("link", { name: /^2-310/ }).click();
  await expect(main.locator('[data-room="2-310"]')).toHaveAttribute("aria-current", "location");

  // On a phone the plan scrolls inside its frame so that the selected room is on screen.
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto("/map?room=1-305");
  const room = await main.locator('[data-room="1-305"] rect').boundingBox();
  expect(room!.x).toBeGreaterThanOrEqual(0);
  expect(room!.x + room!.width).toBeLessThanOrEqual(320);

  await page.goto("/map?room=9-999");
  await expect(main.getByText("9-999 kodlu otaq tapılmadı.", { exact: false })).toBeVisible();
});

test.describe("mobile schedule and map", () => {
  test.use({ viewport: { width: 320, height: 640 } });

  test("fit a 320 px screen without sideways scrolling", async ({ page }) => {
    await signIn(page, "aysel.mammadova", "/schedule");
    await expect(page.getByRole("heading", { level: 1, name: "Dərs cədvəli" })).toBeVisible();
    for (const url of ["/schedule", "/schedule?view=day", "/map?room=1-305"]) {
      await page.goto(url);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, url).toBe(0);
    }
  });
});

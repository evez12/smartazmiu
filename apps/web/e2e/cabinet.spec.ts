import { randomInt } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { hydrated, openPage, password, signIn, signInWithSecondFactor, test } from "./support/auth";
import { importFile } from "./support/imports";
import { undersizedTargets } from "./support/touch-targets";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
test.describe.configure({ mode: "serial" });

async function expectNoSeriousViolations(page: Page, where: string) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(
    violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => `${v.id}: ${v.nodes.length}`),
    where,
  ).toEqual([]);
}

/*
 * Sprint 15, Group C (D-126): the nightly mirror of the personal cabinet. The worker syncs against the fake provider,
 * which has a record for every eight-digit student ID, so a throwaway student gets a transcript without any fixture.
 * The state "source unavailable" is a stored failed run in the unit and API tests; here the response is replaced,
 * because a test must not switch the real worker's source off.
 */
test("a student reads their mirrored transcript after staff start a sync; an outsider sees nothing", async ({
  browser,
  page,
  records,
  accounts,
}) => {
  test.setTimeout(420_000);
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const outsider = await accounts.create("student", { givenName: "Orxan", familyName: "Rzayev" });
  const staff = await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" });
  records.person(student.email);
  const universityId = `9${String(randomInt(0, 10_000_000)).padStart(7, "0")}`;

  await signInWithSecondFactor(page, staff, "/admin/imports");
  await importFile(
    page,
    { value: "students" },
    {
      name: `students-${universityId}.csv`,
      content:
        "university_id,family_name,given_name,email,group_code\n" +
        `${universityId},${student.familyName},${student.givenName},${student.email},765a2\n`,
    },
  );

  await openPage(page, "/admin/cabinet");
  await expect(
    page.getByRole("heading", { level: 1, name: "Kabinet sinxronizasiyası" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "İndi sinxronlaşdır" }).click();
  await expect(page.getByText(/növbəyə qoyuldu/).first()).toBeVisible();

  const own = await browser.newContext();
  const studentPage = await own.newPage();
  await signIn(studentPage, student, "/transcript");
  // The worker picks the job up within seconds; the page reads the mirror, so poll it rather than sleep.
  await expect(async () => {
    const [response] = await Promise.all([
      studentPage.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/me/transcript"),
      studentPage.reload(),
    ]);
    expect(response.headers()["cache-control"]).toBe("no-store");
    await expect(studentPage.getByTestId("cabinet-average")).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 180_000, intervals: [3_000] });

  await expect(studentPage.getByRole("heading", { level: 2, name: "2025 Payız" })).toBeVisible();
  await expect(studentPage.getByRole("heading", { level: 2, name: "2026 Yaz" })).toBeVisible();
  for (const code of ["SOS-1101", "KAR-1101", "SOS-1202", "KAR-1202"]) {
    // A course with an appeal shows its code twice: in the semester table and in the appeals.
    await expect(studentPage.getByText(code, { exact: true }).first()).toBeVisible();
  }
  await expect(studentPage.getByText("Fərq var")).toHaveCount(0);
  await expectNoSeriousViolations(studentPage, "transcript");

  // The calculator shows the cabinet figure beside its own result and links to the transcript.
  await openPage(studentPage, "/gpa");
  await expect(studentPage.getByTestId("cabinet-card-average")).toBeVisible();
  await expectNoSeriousViolations(studentPage, "gpa with the cabinet card");

  // Staff see a successful run with counts and no grade anywhere on the page.
  await openPage(page, "/admin/cabinet");
  await expect(page.getByText("Əl ilə").first()).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Fərq", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: /^Bal$/ })).toHaveCount(0);
  await expectNoSeriousViolations(page, "cabinet sync page");

  const other = await browser.newContext();
  const outsiderPage = await other.newPage();
  await signIn(outsiderPage, outsider, "/transcript");
  await expect(outsiderPage.getByTestId("cabinet-empty")).toBeVisible();
  await expect(outsiderPage.getByTestId("cabinet-average")).toHaveCount(0);
  const forbidden = await outsiderPage.request.get("/api/v1/cabinet/sync-runs");
  expect(forbidden.status()).toBe(403);
  await openPage(outsiderPage, "/admin/cabinet");
  await expect(outsiderPage.getByRole("button", { name: "İndi sinxronlaşdır" })).toHaveCount(0);

  await own.close();
  await other.close();
});

test("a student is told the source is unavailable, with the time of the last good copy", async ({
  page,
}) => {
  await signIn(page, "aysel.mammadova", "/transcript");
  await page.route("**/api/v1/me/transcript", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "cache-control": "no-store" },
      body: JSON.stringify({
        source: { state: "unavailable", last_synced_at: "2026-11-03T22:40:00Z" },
        student: {
          specialty_name: "İqtisadiyyat",
          credits_earned: 24,
          cumulative_average: 78.4,
          synced_at: "2026-11-03T22:40:00Z",
        },
        semesters: [],
      }),
    }),
  );
  await page.reload();
  await hydrated(page);

  const notice = page.getByTestId("cabinet-source-unavailable");
  await expect(notice).toContainText("Mənbə əlçatan deyil");
  await expect(notice).toContainText("4 Noyabr 2026, 02:40");
  await expectNoSeriousViolations(page, "source unavailable");
});

async function expectFits(page: Page, url: string) {
  await openPage(page, url);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow, `${url}: sideways scroll`).toBeLessThanOrEqual(0);
  expect(await undersizedTargets(page), `${url}: touch targets`).toEqual([]);
  await expectNoSeriousViolations(page, url);
}

for (const [locale, heading] of [
  ["az", "Transkript"],
  ["ru", "Академическая справка"],
] as const) {
  test(`the transcript and the calculator fit a 320 px phone in ${locale}`, async ({
    browser,
    baseURL,
  }) => {
    const context = await browser.newContext({
      viewport: { width: 320, height: 640 },
      hasTouch: true,
    });
    const phone = await context.newPage();
    // The sign-in helper reads Azerbaijani labels, so the language is chosen after signing in.
    await signIn(phone, "aysel.mammadova", "/transcript");
    await context.addCookies([{ name: "NEXT_LOCALE", value: locale, url: baseURL! }]);
    await phone.reload();
    await expect(phone.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expectFits(phone, "/transcript");
    await expectFits(phone, "/gpa");
    await context.close();
  });
}

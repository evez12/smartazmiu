import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { password, signIn, signInWithSecondFactor } from "./support/auth";

/*
 * Staff and admin flows. They re-enrol the authenticator of the same Keycloak users, so they run in order
 * in one file instead of in parallel.
 */
test.describe.configure({ mode: "serial" });
test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

const SEED_DIR = path.resolve(__dirname, "../../../infra/seed/academics");
const KINDS = [
  ["faculties", "1. Fakültələr"],
  ["specialties", "2. İxtisaslar"],
  ["subjects", "3. Fənlər"],
  ["semesters", "4. Semestrlər"],
  ["teachers", "5. Müəllimlər"],
  ["groups", "6. Qruplar"],
  ["students", "7. Tələbələr"],
  ["offerings", "8. Fənn təyinatları"],
  ["enrollments", "9. Fənn qeydiyyatları"],
] as const;

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

test("staff must set up two-factor sign-in", async ({ page }) => {
  await signInWithSecondFactor(page, "elvin.quliyev");
  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();
});

/*
 * Sprint 2 acceptance: the dean's office imports the 765a2 roster with its subjects through the wizard;
 * the student then sees their own group and subjects.
 */
test("staff imports the 765a2 roster and the student sees group and subjects", async ({
  page,
  browser,
}) => {
  // Nine files, each validated and applied, plus two sign-ins.
  test.setTimeout(180_000);
  await signInWithSecondFactor(page, "elvin.quliyev", "/admin/imports");
  await expect(page.getByRole("heading", { level: 1, name: "Məlumat idxalı" })).toBeVisible();

  for (const [kind, label] of KINDS) {
    await page.goto("/admin/imports/new");
    await page.getByRole("combobox", { name: /Məlumat növü/ }).selectOption({ label });
    await page
      .getByLabel(/^Fayl/, { exact: false })
      .and(page.locator("input[type=file]"))
      .setInputFiles(path.join(SEED_DIR, `${kind}.csv`));
    await page.getByRole("button", { name: "Faylı yoxlayın" }).click();

    await expect(page.getByRole("heading", { level: 1, name: `${kind}.csv` })).toBeVisible();
    await expect(
      page
        .getByText("Fayl yoxlanıldı, xəta tapılmadı")
        .or(page.getByText("Bu fayl artıq tətbiq olunub")),
    ).toBeVisible();
    await page.getByRole("button", { name: "Tətbiq edin" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Tətbiq edin" }).click();
    await expect(page.getByText("İdxal tətbiq olunub")).toBeVisible();
  }
  await expectNoSeriousViolations(page);

  const context = await browser.newContext();
  const student = await context.newPage();
  await signIn(student, "aysel.mammadova");
  // Scoped to the main landmark: while a streamed segment is being swapped in, a hidden copy exists.
  const main = student.getByRole("main");
  await expect(main.getByRole("heading", { name: "Qrupunuz" })).toBeVisible();
  await expect(main.getByText("765a2", { exact: true }).first()).toBeVisible();
  await expect(main.getByText("İqtisadiyyat · 6004004")).toBeVisible();
  const subjects = main.getByRole("table", { name: "Fənləriniz" });
  await expect(subjects.getByRole("row")).toHaveCount(6);
  await expect(subjects).toContainText("Mikroiqtisadiyyat");
  await expect(subjects).toContainText("Şəhla Ağayeva");
  await expectNoSeriousViolations(student);

  // Students have no import permission: no navigation entry and a forbidden state on direct access.
  await expect(student.getByRole("link", { name: "Məlumat idxalı" })).toHaveCount(0);
  await student.goto("/admin/imports");
  await expect(
    student.getByRole("heading", { name: "Bu səhifəyə baxmaq üçün icazəniz yoxdur" }),
  ).toBeVisible();
  await context.close();
});

test("an invalid file is explained row by row and cannot be applied", async ({ page }) => {
  await signInWithSecondFactor(page, "elvin.quliyev", "/admin/imports/new?kind=students");
  await page.locator("input[type=file]").setInputFiles({
    name: "telebeler.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "university_id,family_name,given_name,email,group_code\n" +
        "25765299,Məmmədova,Aysel,aysel.mammadova@smartazmiu.test,765a2\n" +
        "25765298,Orucov,Elçin,elchin.orujov@smartazmiu.test,765a9\n",
    ),
  });
  await page.getByRole("button", { name: "Faylı yoxlayın" }).click();

  await expect(page.getByText("Faylda 2 xəta tapıldı")).toBeVisible();
  const errors = page.getByRole("table", { name: "Xətalar" });
  await expect(errors).toContainText("Bu e-poçt başqa şəxsə məxsusdur.");
  await expect(errors).toContainText("İstinad edilən qeyd tapılmadı.");
  await expect(page.getByRole("button", { name: "Tətbiq edin" })).toHaveCount(0);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Xəta hesabatını yükləyin" }).click();
  expect((await download).suggestedFilename()).toBe("telebeler-xetalar.csv");
});

test("admin gives a student the moderator role and the change is audited", async ({
  page,
  browser,
}) => {
  test.setTimeout(120_000);
  await signInWithSecondFactor(page, "tural.babayev", "/admin/users");
  await expect(page.getByRole("heading", { level: 1, name: "İstifadəçilər" })).toBeVisible();

  // Searching without Azerbaijani letters still finds "Əliyev".
  await page.getByRole("searchbox", { name: "Axtarış" }).fill("ramin eliyev");
  await page.getByRole("button", { name: "Axtarın" }).click();
  await page.getByRole("link", { name: "Ramin Əliyev" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Ramin Əliyev" })).toBeVisible();

  const moderator = page.getByRole("checkbox", { name: "Moderator" });
  await moderator.check();
  await page.getByRole("button", { name: "Rolları yadda saxlayın" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Rollar dəyişdirilsin?" });
  await expect(dialog).toContainText("Əlavə ediləcək: Moderator.");
  await dialog.getByRole("button", { name: "Rolları yadda saxlayın" }).click();
  await expect(page.getByText("Rollar yadda saxlanıldı").first()).toBeVisible();
  const activity = page.getByRole("table", { name: "Son fəaliyyət" });
  await expect(activity.getByRole("row").nth(1)).toContainText("Rollar dəyişdirildi");
  await expect(activity.getByRole("row").nth(1)).toContainText("Əlavə: Moderator");

  const context = await browser.newContext();
  const student = await context.newPage();
  await signIn(student, "ramin.aliyev");
  await expect(student.getByRole("button", { name: /Profil menyusu/ })).toContainText(
    "Tələbə · Moderator",
  );
  await context.close();

  // Restore the seeded roles, so reruns and other tests start from the realm file's state.
  await page.getByRole("checkbox", { name: "Moderator" }).uncheck();
  await page.getByRole("button", { name: "Rolları yadda saxlayın" }).click();
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Rolları yadda saxlayın" })
    .click();
  await expect(page.getByRole("checkbox", { name: "Moderator" })).not.toBeChecked();

  await page.getByRole("link", { name: "Audit jurnalı" }).first().click();
  await page
    .getByRole("combobox", { name: "Hərəkət" })
    .selectOption({ label: "Rollar dəyişdirildi" });
  await page.getByRole("button", { name: "Göstərin" }).click();
  const log = page.getByRole("table", { name: "Audit qeydləri" });
  await expect(log.getByRole("row").nth(1)).toContainText("Silinən: Moderator");
  await expect(log.getByRole("row").nth(1)).toContainText("Tural Babayev");
  await expectNoSeriousViolations(page);
});

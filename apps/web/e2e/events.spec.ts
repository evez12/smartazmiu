import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { openPage, password, signIn, signInWithSecondFactor, test } from "./support/auth";
import { mailFor, mailText } from "./support/database";
import { bakuInput, importStructure } from "./support/structure";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

const STAFF_NAME = { givenName: "Günel", familyName: "Səfərova" };
const STUDENT_NAME = { givenName: "Nərmin", familyName: "Şükürova" };

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

/** The id at the end of the current URL (`/events/<id>`). */
function idFrom(page: Page): string {
  return new URL(page.url()).pathname.split("/").pop()!;
}

/*
 * Sprint 4 acceptance: staff publish an event for faculty X; the students of X are notified in the app (and by
 * push on devices that enabled it); RSVP produces a QR ticket, which staff then scan at the door. The faculty
 * is the test's own, with one throwaway student, so nobody else is notified.
 */
test("an event for a faculty reaches its student, whose RSVP gives a ticket staff can scan", async ({
  page,
  browser,
  accounts,
  records,
}) => {
  test.setTimeout(240_000);
  const student = await accounts.create("student", STUDENT_NAME);
  await signInWithSecondFactor(page, await accounts.create("staff", STAFF_NAME), "/admin/imports");
  const structure = await importStructure(page, records, student);
  const title = `Dizayn həftəsi: açılış ${structure.code}`;

  await openPage(page, "/events/new");
  await page.getByRole("textbox", { name: /^Ad/ }).fill(title);
  await page
    .getByRole("textbox", { name: /^Təsvir/ })
    .fill("Tələbə işlərinin sərgisi və müəllimlərlə görüş.");
  await page.getByLabel(/^Başlama vaxtı/).fill(bakuInput(1));
  await page.getByLabel(/^Bitmə vaxtı/).fill(bakuInput(3));
  await page.getByRole("textbox", { name: /^Otaq kodu/ }).fill("1-305");
  await page.getByRole("spinbutton", { name: /^Yer sayı/ }).fill("40");
  await page.getByLabel(/^Kimə/).selectOption("faculty");
  await page.getByRole("searchbox", { name: "Axtarış" }).fill(structure.code);
  await page.getByRole("radio", { name: structure.faculty }).check();
  await expectNoSeriousViolations(page);
  await page.getByRole("button", { name: "Dərc edin" }).click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  const eventId = idFrom(page);
  records.event(eventId);

  // The student sees the notification in the bell and opens the event from it.
  const context = await browser.newContext();
  const home = await context.newPage();
  await signIn(home, student);
  const bell = home.getByRole("button", { name: "Bildirişlər, 1 oxunmamış" });
  await expect(bell).toBeVisible();
  await bell.click();
  const panel = home.getByRole("dialog", { name: "Bildirişlər" });
  await expect(panel).toContainText("Yeni tədbir");
  await panel.getByRole("link", { name: new RegExp(title) }).click();
  await expect(home.getByRole("heading", { level: 1, name: title })).toBeVisible();
  await expect(home.getByRole("button", { name: "Bildirişlər" })).toBeVisible();
  const main = home.getByRole("main");
  await expect(main.getByText("(Bakı vaxtı)")).toBeVisible();
  await expect(main.getByRole("link", { name: /^Otaq 1-305.*xəritədə göstərin$/ })).toBeVisible();

  await main.getByRole("button", { name: "Qeydiyyatdan keçin" }).click();
  await expect(main.getByRole("img", { name: `${title} tədbirinin bilet QR kodu` })).toBeVisible();
  await expect(main.getByText("Qeydiyyatdan keçmisiniz")).toBeVisible();
  const code = (await main.locator("p.font-mono").innerText()).trim();
  expect(code).toMatch(/^SA1\.[0-9a-f]{32}\.[A-Za-z0-9_-]{22}$/);
  await expectNoSeriousViolations(home);

  await home.goto("/events/tickets");
  await expect(home.getByRole("main").getByRole("link", { name: title })).toBeVisible();

  // At the door: the scanned code admits her once.
  await openPage(page, `/events/${eventId}/check-in`);
  const field = page.getByRole("textbox", { name: /^Bilet kodu/ });
  await field.fill(code);
  await field.press("Enter");
  await expect(
    page.getByText(
      `${STUDENT_NAME.givenName} ${STUDENT_NAME.familyName} (${structure.group}) qeydiyyata alındı`,
    ),
  ).toBeVisible();
  await expect(page.getByText("1 / 1 nəfər girişdə qeyd olunub")).toBeVisible();
  await field.fill(code);
  await field.press("Enter");
  await expect(page.getByText("Giriş qeydə alınmadı")).toBeVisible();
  await expectNoSeriousViolations(page);
  await context.close();
});

test("an announcement for a group reaches its student on the dashboard and by e-mail", async ({
  page,
  browser,
  accounts,
  records,
}) => {
  test.setTimeout(240_000);
  const student = await accounts.create("student", STUDENT_NAME);
  await signInWithSecondFactor(page, await accounts.create("staff", STAFF_NAME), "/admin/imports");
  const structure = await importStructure(page, records, student);
  const title = `Qış imtahan sessiyasının cədvəli ${structure.code}`;

  await openPage(page, "/announcements/new");
  await page.getByRole("textbox", { name: /^Başlıq/ }).fill(title);
  await page
    .getByRole("textbox", { name: /^Mətn/ })
    .fill("Cədvəl dekanlığın lövhəsində asılıb.\nSualınız varsa, kuratora yazın.");
  await page.getByLabel(/^Kimə/).selectOption("group");
  await page.getByRole("searchbox", { name: "Axtarış" }).fill(structure.code.toLowerCase());
  await page.getByRole("radio", { name: structure.group }).check();
  await page.getByRole("button", { name: "Dərc edin" }).click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  records.announcement(idFrom(page));

  const context = await browser.newContext();
  const home = await context.newPage();
  await signIn(home, student);
  const widget = home.getByRole("main");
  await expect(widget.getByRole("link", { name: title })).toBeVisible();
  await expect(home.getByRole("button", { name: "Bildirişlər, 1 oxunmamış" })).toBeVisible();

  // Announcements are e-mailed by default; the worker sends it through SMTP (Mailpit locally).
  await expect
    .poll(async () => (await mailFor(student.email)).map((m) => m.Subject), { timeout: 30_000 })
    .toContain(`Yeni elan: ${title}`);
  const [message] = await mailFor(student.email);
  const text = await mailText(message!.ID);
  expect(text).toContain(`Hörmətli ${STUDENT_NAME.givenName} ${STUDENT_NAME.familyName},`);
  expect(text).toMatch(/\/announcements\/[0-9a-f-]{36}/);

  await widget.getByRole("link", { name: title }).click();
  await expect(home.getByRole("main")).toContainText("Sualınız varsa, kuratora yazın.");
  await expectNoSeriousViolations(home);

  // The student turns announcement e-mails off; the choice persists.
  await openPage(home, "/notifications/settings");
  const announcements = home.getByRole("group", { name: "Elanlar" });
  await announcements.getByRole("checkbox", { name: "E-poçt" }).click();
  await home.getByRole("button", { name: "Yadda saxlayın" }).click();
  await expect(home.getByText("Bildiriş ayarları yadda saxlanıldı").first()).toBeVisible();
  await home.reload();
  await expect(
    home.getByRole("group", { name: "Elanlar" }).getByRole("checkbox", { name: "E-poçt" }),
  ).not.toBeChecked();
  await expectNoSeriousViolations(home);
  await context.close();
});

test.describe("mobile notifications and events", () => {
  test.use({ viewport: { width: 320, height: 640 } });

  test("fit a 320 px screen and the tab bar reaches the notifications", async ({ page }) => {
    await signIn(page, "aysel.mammadova");
    const tabs = page.getByRole("navigation", { name: "Əsas naviqasiya" }).last();
    await tabs.getByRole("link", { name: "Bildirişlər" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Bildirişlər" })).toBeVisible();
    for (const url of ["/notifications", "/notifications/settings", "/events", "/announcements"]) {
      await page.goto(url);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, url).toBe(0);
    }
  });
});

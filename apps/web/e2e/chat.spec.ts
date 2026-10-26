import { randomBytes } from "node:crypto";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Browser, type Locator, type Page } from "@playwright/test";

import { password, signIn, signInWithSecondFactor, test } from "./support/auth";
import { EICAR, SMALL_PDF, storedZip } from "./support/files";
import { importFile, SEED_DIR } from "./support/imports";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
// The tests sign in as the same seeded students; in parallel their tabs would read each other's messages.
test.describe.configure({ mode: "serial" });

// Two seeded students of 765a2 (D-020); they only sign in and write messages, which the test removes.
const AYSEL = { username: "aysel.mammadova", email: "aysel.mammadova@smartazmiu.test" };
const RAMIN = { username: "ramin.aliyev", email: "ramin.aliyev@smartazmiu.test" };
const STAFF_NAME = { givenName: "Günel", familyName: "Səfərova" };
const REGISTRY = ["faculties", "specialties", "subjects", "semesters", "teachers", "groups"];

async function openChat(browser: Browser, username: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await signIn(page, username, "/chat");
  return page;
}

function sidebar(page: Page): Locator {
  return page.getByRole("navigation", { name: "Kanallar" });
}

/** The open course channels of a sidebar (section "Fənlər"), so the test needs no semester-specific names. */
function courses(page: Page): Locator {
  return sidebar(page).getByRole("region", { name: "Fənlər" }).locator("> ul").getByRole("link");
}

async function online(page: Page) {
  // The connection line disappears once the socket is subscribed.
  await expect(sidebar(page).getByRole("status")).toHaveCount(0, { timeout: 15_000 });
}

async function send(page: Page, text: string) {
  const field = page.getByRole("combobox", { name: "Mesaj" });
  await field.fill(text);
  await field.press("Enter");
}

function messageLog(page: Page): Locator {
  return page.getByRole("log", { name: /kanalının mesajları$/ });
}

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

/*
 * Sprint 5 acceptance: two students of 765a2 in two browsers exchange messages in real time in a course channel
 * and in a direct message; a network drop loses and duplicates nothing.
 */
test("two students talk in a course channel and a DM, and a network drop loses nothing", async ({
  browser,
  records,
}) => {
  test.setTimeout(180_000);
  const marker = records.chatMessages(randomBytes(6).toString("hex"), [AYSEL.email, RAMIN.email]);
  const aysel = await openChat(browser, AYSEL.username);
  const ramin = await openChat(browser, RAMIN.username);
  await online(aysel);
  await online(ramin);

  const course = courses(aysel).first();
  const courseName = (await course.locator("span.truncate").first().innerText()).trim();
  await course.click();
  await courses(ramin).filter({ hasText: courseName }).first().click();
  await expect(ramin.getByRole("heading", { level: 2, name: courseName })).toBeVisible();

  await send(aysel, `Seminara hazırlıq: 3-cü mövzunu kim oxuyub? ${marker}-1`);
  await expect(messageLog(ramin).getByText(`${marker}-1`)).toBeVisible({ timeout: 5000 });
  await send(ramin, `Mən oxumuşam, sabah danışarıq. ${marker}-2`);
  await expect(messageLog(aysel).getByText(`${marker}-2`)).toBeVisible({ timeout: 5000 });
  await expectNoSeriousViolations(aysel);

  // A network drop: Aysel keeps writing, Ramin writes offline; after reconnecting both see everything once.
  await ramin.context().setOffline(true);
  for (const n of [3, 4, 5])
    await send(aysel, `Qeyd ${n}: tapşırıq cümə günü təhvil verilir. ${marker}-${n}`);
  await send(ramin, `Bağlantı kəsilmişdi, bunu sonra göndərin. ${marker}-6`);
  await expect(messageLog(ramin).getByText("Bağlantı bərpa olunanda göndəriləcək")).toBeVisible();
  await ramin.context().setOffline(false);
  for (const n of [3, 4, 5, 6]) {
    await expect(messageLog(ramin).getByText(`${marker}-${n}`)).toHaveCount(1, { timeout: 30_000 });
  }
  await expect(messageLog(aysel).getByText(`${marker}-6`)).toHaveCount(1, { timeout: 15_000 });
  await expect(messageLog(ramin).getByText("Bağlantı bərpa olunanda göndəriləcək")).toHaveCount(0);

  // A direct message, started from the channel's member list.
  await aysel.getByRole("button", { name: "Üzvlər" }).click();
  await aysel
    .getByRole("dialog", { name: "Kanalın üzvləri" })
    .getByRole("button", { name: /Ramin Əliyev/ })
    .click();
  await aysel
    .getByRole("dialog", { name: "Ramin Əliyev" })
    .getByRole("button", { name: "Mesaj yazın" })
    .click();
  await expect(aysel.getByRole("heading", { level: 2, name: "Ramin Əliyev" })).toBeVisible();
  await send(aysel, `Şəxsi sual: konspekti göndərə bilərsiniz? ${marker}-7`);
  const dm = sidebar(ramin)
    .getByRole("region", { name: "Şəxsi" })
    .getByRole("link", { name: /Aysel Məmmədova/ });
  await expect(dm).toBeVisible({ timeout: 10_000 });
  await expect(dm).toContainText("1 oxunmamış mesaj");
  await dm.click();
  await expect(messageLog(ramin).getByText(`${marker}-7`)).toBeVisible();
  await send(ramin, `Bəli, axşam göndərərəm. ${marker}-8`);
  await expect(messageLog(aysel).getByText(`${marker}-8`)).toBeVisible({ timeout: 5000 });
  await expectNoSeriousViolations(ramin);

  await aysel.context().close();
  await ramin.context().close();
});

/*
 * Sprint 6: a mention picked from the suggestions, a reply in the thread panel, a reaction, an edit within the
 * window and a soft delete that keeps the thread (§5.3, §13.2).
 */
test("students mention, reply in a thread, react, edit and delete", async ({
  browser,
  records,
}) => {
  test.setTimeout(180_000);
  const marker = records.chatMessages(randomBytes(6).toString("hex"), [AYSEL.email, RAMIN.email]);
  const aysel = await openChat(browser, AYSEL.username);
  const ramin = await openChat(browser, RAMIN.username);
  await online(aysel);
  await online(ramin);
  const course = courses(aysel).first();
  const courseName = (await course.locator("span.truncate").first().innerText()).trim();
  await course.click();
  await courses(ramin).filter({ hasText: courseName }).first().click();
  await expect(ramin.getByRole("heading", { level: 2, name: courseName })).toBeVisible();

  const field = aysel.getByRole("combobox", { name: "Mesaj" });
  await field.fill("Kollokvium cümə günüdür, ");
  await field.pressSequentially("@Rami");
  await aysel.getByRole("option", { name: /Ramin Əliyev/ }).click();
  await field.pressSequentially(`hazırsınız? ${marker}-root`);
  await field.press("Enter");
  const rootOnRamin = messageLog(ramin)
    .getByRole("article")
    .filter({ hasText: `${marker}-root` });
  await expect(rootOnRamin).toContainText("@Ramin Əliyev", { timeout: 5000 });

  await rootOnRamin.hover();
  await rootOnRamin.getByRole("button", { name: "Cavab yazın" }).click();
  const thread = ramin.getByRole("region", { name: "Cavablar" });
  await expect(thread.getByText(`${marker}-root`)).toBeVisible();
  await thread
    .getByRole("combobox", { name: "Cavab yazın" })
    .fill(`Bəli, hazıram. ${marker}-reply`);
  await thread.getByRole("combobox", { name: "Cavab yazın" }).press("Enter");
  await expect(thread.getByText(`${marker}-reply`)).toBeVisible();
  const rootOnAysel = messageLog(aysel)
    .getByRole("article")
    .filter({ hasText: `${marker}-root` });
  await expect(rootOnAysel.getByRole("button", { name: "1 cavab" })).toBeVisible({ timeout: 5000 });
  // Replies stay in the thread, not in the channel.
  await expect(messageLog(aysel).getByText(`${marker}-reply`)).toHaveCount(0);

  await rootOnRamin.hover();
  await rootOnRamin.getByRole("button", { name: "Reaksiya bildirin" }).click();
  await ramin
    .getByRole("button", { name: /reaksiyası$/ })
    .first()
    .click();
  await expect(rootOnAysel.getByRole("button", { name: /1 nəfər/ })).toBeVisible({ timeout: 5000 });
  await expectNoSeriousViolations(ramin);

  await rootOnAysel.hover();
  await rootOnAysel.getByRole("button", { name: "Digər əməliyyatlar" }).click();
  await aysel.getByRole("menuitem", { name: "Redaktə edin" }).click();
  const editor = rootOnAysel.getByRole("combobox", { name: "Mesajın mətni" });
  await expect(editor).toHaveValue(/@Ramin Əliyev/);
  await editor.fill(`Kollokvium şənbə günüdür. ${marker}-root`);
  await editor.press("Enter");
  await expect(rootOnRamin).toContainText("şənbə günüdür", { timeout: 5000 });
  await expect(rootOnRamin).toContainText("redaktə olunub");

  await rootOnAysel.hover();
  await rootOnAysel.getByRole("button", { name: "Digər əməliyyatlar" }).click();
  await aysel.getByRole("menuitem", { name: "Silin" }).click();
  await aysel.getByRole("alertdialog").getByRole("button", { name: "Silin" }).click();
  await expect(messageLog(ramin).getByText("Bu mesaj silinib.")).toBeVisible({ timeout: 5000 });
  await expect(thread.getByText(`${marker}-reply`)).toBeVisible();
  await expect(thread.getByText("silinmiş mesaja cavab")).toBeVisible();

  await aysel.context().close();
  await ramin.context().close();
});

/*
 * Sprint 6 attachments: a clean PDF reaches the other student only after the scan; a file ClamAV flags stays
 * hidden from others and its uploader is told (§13.2, D-068).
 */
test("attachments are scanned before others see them", async ({ browser, records }) => {
  test.setTimeout(240_000);
  const marker = records.chatMessages(randomBytes(6).toString("hex"), [AYSEL.email, RAMIN.email]);
  const aysel = await openChat(browser, AYSEL.username);
  const ramin = await openChat(browser, RAMIN.username);
  await online(aysel);
  await online(ramin);
  const course = courses(aysel).first();
  const courseName = (await course.locator("span.truncate").first().innerText()).trim();
  await course.click();
  await courses(ramin).filter({ hasText: courseName }).first().click();
  await expect(ramin.getByRole("heading", { level: 2, name: courseName })).toBeVisible();

  const picker = aysel.locator('input[type="file"]').first();
  await picker.setInputFiles({
    name: "Kurs işi.pdf",
    mimeType: "application/pdf",
    buffer: SMALL_PDF,
  });
  await expect(aysel.getByText("yükləndi")).toBeVisible({ timeout: 15_000 });
  await send(aysel, `Kurs işinin planı əlavədədir. ${marker}-pdf`);
  const onRamin = messageLog(ramin)
    .getByRole("article")
    .filter({ hasText: `${marker}-pdf` });
  await expect(onRamin.getByRole("button", { name: "Baxın" })).toBeVisible({ timeout: 120_000 });
  await onRamin.getByRole("button", { name: "Baxın" }).click();
  await expect(ramin.getByTitle("Kurs işi.pdf sənədinə baxış")).toBeVisible();
  await ramin.keyboard.press("Escape");

  await picker.setInputFiles({
    name: "test.zip",
    mimeType: "application/zip",
    buffer: storedZip("eicar.com", EICAR),
  });
  await expect(aysel.getByText("yükləndi")).toBeVisible({ timeout: 15_000 });
  await send(aysel, `Arxiv ${marker}-zip`);
  const onAysel = messageLog(aysel)
    .getByRole("article")
    .filter({ hasText: `${marker}-zip` });
  await expect(onAysel.getByText(/Faylda virus aşkarlandı/)).toBeVisible({ timeout: 120_000 });
  const zipOnRamin = messageLog(ramin)
    .getByRole("article")
    .filter({ hasText: `${marker}-zip` });
  await expect(zipOnRamin).toBeVisible();
  await expect(zipOnRamin.getByText("test.zip")).toHaveCount(0);
  await expectNoSeriousViolations(aysel);

  await aysel.context().close();
  await ramin.context().close();
});

test("the teacher is in the course channel but not in the subject community", async ({ page }) => {
  await signIn(page, AYSEL.username, "/chat");
  const nav = sidebar(page);
  await expect(courses(page).first()).toBeVisible();
  // Statistika: Leyla Həsənova teaches it to 765a2 (offerings.csv).
  const course = courses(page)
    .filter({ hasText: /^Statistika/ })
    .first();
  test.skip(
    (await course.count()) === 0,
    "Statistika is not running in the sample semester of today",
  );
  await course.click();
  await page.getByRole("button", { name: "Üzvlər" }).click();
  const members = page.getByRole("dialog", { name: "Kanalın üzvləri" });
  const teacher = members.getByRole("button", { name: /Leyla Həsənova/ });
  await expect(teacher).toBeVisible();
  await expect(teacher).toContainText("Müəllim");
  await page.keyboard.press("Escape");

  await nav
    .getByRole("region", { name: "Fənn icmaları" })
    .getByRole("link", { name: /^Statistika/ })
    .click();
  await page.getByRole("button", { name: "Üzvlər" }).click();
  await expect(members.getByRole("button", { name: /Aysel Məmmədova/ })).toBeVisible();
  await expect(members.getByRole("button", { name: /Leyla Həsənova/ })).toHaveCount(0);
});

/*
 * A student moved to another group by an import loses the old group's channel while connected (§5.9,
 * §13.1): the provisioning job revokes the membership and the open socket is told at once.
 */
test("a student moved out of the group loses its channel while connected", async ({
  page,
  browser,
  accounts,
  records,
}) => {
  test.setTimeout(240_000);
  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  records.person(student.email);
  const code = `E2E-${randomBytes(4).toString("hex")}`;
  await signInWithSecondFactor(page, await accounts.create("staff", STAFF_NAME), "/admin/imports");
  for (const kind of REGISTRY) {
    await importFile(page, { value: kind }, path.join(SEED_DIR, `${kind}.csv`));
  }
  const roster = (group: string) => ({
    name: `students-${code}-${group}.csv`,
    content: `university_id,family_name,given_name,email,group_code\n${code},Şükürova,Nərmin,${student.email},${group}\n`,
  });
  await importFile(page, { value: "students" }, roster("765a2"));

  const context = await browser.newContext();
  const chat = await context.newPage();
  await signIn(chat, student, "/chat");
  const group = sidebar(chat)
    .getByRole("region", { name: "Qrup" })
    .getByRole("link", { name: /765a2/ });
  await expect(group).toBeVisible({ timeout: 90_000 });
  await group.click();
  await online(chat);
  await expect(chat.getByRole("heading", { level: 2, name: "765a2" })).toBeVisible();

  await importFile(page, { value: "students" }, roster("765a1"));
  await expect(chat.getByText("Bu kanala artıq daxil ola bilmirsiniz.")).toBeVisible({
    timeout: 90_000,
  });
  await expect(sidebar(chat).getByRole("link", { name: /765a2/ })).toHaveCount(0);
  await expect(sidebar(chat).getByRole("link", { name: /765a1/ })).toBeVisible({ timeout: 30_000 });
  await context.close();
});

test.describe("chat on a phone", () => {
  test.use({ viewport: { width: 320, height: 640 } });

  test("shows one pane at a time and fits the screen", async ({ page, records }) => {
    const marker = records.chatMessages(randomBytes(6).toString("hex"), [AYSEL.email]);
    await signIn(page, AYSEL.username, "/chat");
    await expect(page.getByRole("heading", { level: 1, name: "Çat" })).toBeVisible();
    await courses(page).first().click();
    await expect(sidebar(page)).toBeHidden();
    await expect(page.getByRole("combobox", { name: "Mesaj" })).toBeEnabled();
    await send(page, `Telefondan yazıram. ${marker}`);
    await expect(messageLog(page).getByText(marker)).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBe(0);
    await expectNoSeriousViolations(page);
    await page.getByRole("link", { name: "Kanallara qayıdın" }).click();
    await expect(sidebar(page)).toBeVisible();
  });
});

test("chat screens pass the accessibility check in dark mode", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await signIn(page, AYSEL.username, "/chat");
  await expectNoSeriousViolations(page);
  await courses(page).first().click();
  await expect(page.getByRole("combobox", { name: "Mesaj" })).toBeVisible();
  await expectNoSeriousViolations(page);
});

import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { hydrated, openPage, password, signIn, test } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
test.describe.configure({ mode: "serial" });

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

/*
 * Sprint 12 happy path (D-090): a student posts to the feed, another marks it helpful, comments and reports it;
 * the first asks a forum question, the other answers, the asker accepts the answer and a teacher verifies it.
 * Every account is a throwaway one (D-040) and `records` removes the posts and questions afterwards.
 */
test("a feed post and a forum question go from asking to an accepted, verified answer", async ({
  browser,
  records,
  accounts,
}) => {
  test.setTimeout(240_000);
  const marker = records.community(randomBytes(6).toString("hex"));
  const postText = `Kitabxana şənbə günü də açıqdır. ${marker}`;
  const questionTitle = `Statistika imtahanında kalkulyator olar? ${marker}`;
  const answerText = `Bəli, sadə kalkulyatora icazə verilir. ${marker}`;

  const asker = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  const helper = await accounts.create("student", { givenName: "Orxan", familyName: "Rzayev" });
  const teacher = await accounts.create("teacher", { givenName: "Leyla", familyName: "Həsənova" });

  const askerContext = await browser.newContext();
  const askerPage = await askerContext.newPage();
  await signIn(askerPage, asker, "/feed");
  await expect(askerPage.getByText(/Hələ heç bir paylaşım yoxdur/)).toBeVisible();
  await askerPage.getByRole("textbox", { name: /Yeni paylaşım/ }).fill(postText);
  await askerPage.getByRole("checkbox", { name: "Kitabxana" }).check();
  await askerPage.getByRole("button", { name: "Paylaşın" }).click();
  const ownPost = askerPage.getByRole("article").filter({ hasText: postText });
  await expect(ownPost).toBeVisible();
  await expect(ownPost.getByText("Kitabxana", { exact: true })).toBeVisible();
  // Nobody marks their own post helpful or reports it; they can delete it.
  await expect(ownPost.getByRole("button", { name: "Faydalıdır" })).toHaveCount(0);
  await expect(ownPost.getByRole("button", { name: "Silin" })).toBeVisible();
  await expectNoSeriousViolations(askerPage);

  const helperContext = await browser.newContext();
  const helperPage = await helperContext.newPage();
  await signIn(helperPage, helper, "/feed");
  const post = helperPage.getByRole("article").filter({ hasText: postText });
  await expect(post).toBeVisible();
  await post.getByRole("button", { name: /Faydalıdır/ }).click();
  await expect(post.getByRole("button", { name: /Faydalıdır/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await post.getByRole("button", { name: /Şərh yazın/ }).click();
  await post.getByRole("textbox", { name: "Şərhiniz" }).fill(`Təşəkkürlər! ${marker}`);
  await post.getByRole("button", { name: "Şərh göndərin" }).click();
  await expect(post.getByText(`Təşəkkürlər! ${marker}`)).toBeVisible();
  await post.getByRole("button", { name: "Şikayət edin" }).first().click();
  const report = helperPage.getByRole("dialog", { name: "Paylaşımdan şikayət" });
  await report.getByRole("radio", { name: "Spam" }).click();
  await report.getByRole("button", { name: "Şikayət göndərin" }).click();
  await expect(helperPage.getByText("Şikayətiniz qeydə alındı.").first()).toBeVisible();
  await expectNoSeriousViolations(helperPage);

  // The author sees the effect of the other person's reaction and comment.
  await askerPage.reload();
  await hydrated(askerPage);
  await expect(askerPage.getByRole("article").filter({ hasText: postText })).toContainText(
    "1 nəfər faydalı hesab edib",
  );

  await openPage(askerPage, "/forum");
  await askerPage.getByRole("button", { name: "Sual verin" }).click();
  await askerPage.getByRole("button", { name: "Sualı dərc edin" }).click();
  await expect(askerPage.getByText("Başlıq ən azı 3 simvol olmalıdır.")).toBeVisible();
  await askerPage.getByRole("textbox", { name: /Sualın başlığı/ }).fill(questionTitle);
  await askerPage
    .getByRole("textbox", { name: /Sualın mətni/ })
    .fill(`Keçən il icazə verilirdi. ${marker}`);
  await askerPage.getByRole("button", { name: "Sualı dərc edin" }).click();
  await expect(askerPage).toHaveURL(/\/forum\/questions\/[0-9a-f-]{36}$/);
  const questionUrl = askerPage.url();
  await expect(askerPage.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(askerPage.getByText("Bu suala hələ cavab verilməyib.")).toBeVisible();

  await openPage(helperPage, questionUrl);
  await helperPage.getByRole("textbox", { name: "Cavabınız" }).fill(answerText);
  await helperPage.getByRole("button", { name: "Cavabı göndərin" }).click();
  const answer = helperPage.getByRole("article").filter({ hasText: answerText });
  await expect(answer).toBeVisible();
  // One cannot vote on, or report, one's own answer.
  await expect(answer.getByRole("button", { name: "Faydalı cavab" })).toBeDisabled();
  await expect(answer.getByRole("button", { name: "Cavabı qəbul edin" })).toHaveCount(0);

  await askerPage.reload();
  await hydrated(askerPage);
  const asked = askerPage.getByRole("article").filter({ hasText: answerText });
  await asked.getByRole("button", { name: "Faydalı cavab" }).click();
  await expect(asked.getByRole("button", { name: "Faydalı cavab" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await asked.getByRole("button", { name: "Cavabı qəbul edin" }).click();
  await expect(asked.getByText("Qəbul edilmiş cavab")).toBeVisible();
  // A student cannot verify an answer.
  await expect(asked.getByRole("button", { name: "Cavabı təsdiqləyin" })).toHaveCount(0);
  await expectNoSeriousViolations(askerPage);

  const teacherContext = await browser.newContext();
  const teacherPage = await teacherContext.newPage();
  await signIn(teacherPage, teacher, questionUrl);
  const toVerify = teacherPage.getByRole("article").filter({ hasText: answerText });
  await toVerify.getByRole("button", { name: "Cavabı təsdiqləyin" }).click();
  await expect(toVerify.getByText("Leyla Həsənova təsdiqləyib")).toBeVisible();

  // The list now shows both marks, and the tag filter finds the post.
  await openPage(askerPage, "/forum");
  const row = askerPage.getByRole("article").filter({ hasText: questionTitle });
  await expect(row.getByText("Qəbul edilmiş cavab")).toBeVisible();
  await expect(row.getByText("Müəllim təsdiqləyib")).toBeVisible();
  await openPage(askerPage, "/feed?tag=kitabxana");
  await expect(askerPage.getByRole("article").filter({ hasText: postText })).toBeVisible();
  await openPage(askerPage, "/forum/tags/kitabxana");
  await expect(askerPage).toHaveURL(/\/forum\?tag=kitabxana$/);
  await expect(askerPage.getByText(questionTitle)).toHaveCount(0);

  await Promise.all([askerContext.close(), helperContext.close(), teacherContext.close()]);
});

test.describe("feed on a phone in dark mode", () => {
  test.use({ viewport: { width: 320, height: 640 }, colorScheme: "dark" });

  test("fits a 320 px screen and passes the accessibility check", async ({ page, accounts }) => {
    await signIn(
      page,
      await accounts.create("student", { givenName: "Səbinə", familyName: "Rəsulova" }),
      "/feed",
    );
    await expect(page.getByRole("textbox", { name: /Yeni paylaşım/ })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    await expectNoSeriousViolations(page);
  });
});

import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { openPage, password, signIn, signInWithSecondFactor, test } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

/*
 * Sprint 6 pilot support (D-074): a student finds the support channel in chat and sends feedback from the
 * profile menu; staff read it on the feedback list and close it.
 */
test("a student reaches the support channel and sends feedback that staff close", async ({
  page,
  browser,
  records,
  accounts,
}) => {
  const marker = records.feedback(randomBytes(6).toString("hex"));
  records.rateLimit("feedback_create", ["aysel.mammadova@smartazmiu.test"]);
  const studentContext = await browser.newContext();
  const student = await studentContext.newPage();
  await signIn(student, "aysel.mammadova", "/chat");
  await expect(
    student
      .getByRole("navigation", { name: "Kanallar" })
      .getByRole("link", { name: /SmartAzMİU dəstəyi/ }),
  ).toBeVisible();

  await openPage(student, "/schedule");
  await student.getByRole("button", { name: /Profil menyusu/ }).click();
  await student.getByRole("menuitem", { name: "Rəy bildirin" }).click();
  const dialog = student.getByRole("dialog", { name: "Rəy bildirin" });
  await dialog.getByRole("radio", { name: "Problem" }).click();
  await dialog.getByRole("textbox").fill(`Cədvəldə otaq görünmür. ${marker}`);
  const { violations } = await new AxeBuilder({ page: student }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  await dialog.getByRole("button", { name: "Göndərin" }).click();
  // Generous: the first request through a freshly compiled dev proxy route can take seconds.
  await expect(student.getByText("Rəyiniz göndərildi. Təşəkkür edirik.").first()).toBeVisible({
    timeout: 15_000,
  });
  await studentContext.close();

  await signInWithSecondFactor(
    page,
    await accounts.create("staff", { givenName: "Günel", familyName: "Səfərova" }),
    "/admin/feedback",
  );
  const row = page.getByRole("row").filter({ hasText: marker });
  await expect(row).toContainText("Problem");
  await expect(row).toContainText("Səhifə: /schedule");
  await expect(row).toContainText("Aysel Məmmədova");
  await row.getByRole("button", { name: "Bağlayın" }).click();
  await expect(page.getByText("Rəyin vəziyyəti dəyişdi.").first()).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: marker })).toHaveCount(0);
});

async function expectNoSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

/*
 * The support page (D-081): reached from the profile menu, it leads registry members to the support channel and
 * everyone else to the feedback form; it fits a 320 px screen in dark mode.
 */
test.describe("the support page", () => {
  test.use({ viewport: { width: 320, height: 640 }, colorScheme: "dark" });

  test("leads to the support channel or, without one, to the feedback form", async ({
    page,
    browser,
    accounts,
  }) => {
    const studentContext = await browser.newContext({
      viewport: { width: 320, height: 640 },
      colorScheme: "dark",
    });
    const student = await studentContext.newPage();
    await signIn(student, "aysel.mammadova", "/schedule");
    await student.getByRole("button", { name: /Profil menyusu/ }).click();
    await student.getByRole("menuitem", { name: "Dəstək" }).click();
    await expect(student.getByRole("heading", { level: 1, name: "Dəstək" })).toBeVisible();
    const channel = student.getByRole("link", { name: "Dəstək kanalını açın" });
    await expect(channel).toHaveAttribute("href", /^\/chat\/[0-9a-f-]{36}$/);
    const overflow = await student.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    await expectNoSeriousViolations(student);
    await openPage(student, (await channel.getAttribute("href"))!);
    await expect(
      student.getByRole("heading", { level: 2, name: /SmartAzMİU dəstəyi/ }),
    ).toBeVisible();
    await studentContext.close();

    // Someone outside the registry is not in the channel; the page says so and offers the form instead.
    await signIn(
      page,
      await accounts.create("student", { givenName: "Orxan", familyName: "Səmədov" }),
      "/support",
    );
    await expect(page.getByRole("link", { name: "Dəstək kanalını açın" })).toHaveCount(0);
    await expect(
      page
        .getByRole("region", { name: "Dəstək kanalı" })
        .getByText(/Dəstək kanalı registrdə olan tələbə və müəllimlər üçündür/),
    ).toBeVisible();
    await page.getByRole("button", { name: "Rəy bildirin" }).click();
    await expect(page.getByRole("dialog", { name: "Rəy bildirin" })).toBeVisible();
    await expectNoSeriousViolations(page);
  });
});

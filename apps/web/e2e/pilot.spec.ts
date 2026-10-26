import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";

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

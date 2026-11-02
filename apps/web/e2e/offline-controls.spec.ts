import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";

import { openPage, password, signIn, test } from "./support/auth";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

/*
 * §13.6, Sprint 15 follow-up: what needs the server is switched off while the browser is offline, with the reason
 * in text, and comes back with the connection. The chat composer is the one exception: it queues (§13.2, D-064).
 * No service worker is involved, so this runs on the development server as well.
 */
const REASON = "İnternet bağlantısı olmadan bu əməliyyat mümkün deyil.";

test("a profile edit is switched off with its reason offline and back on when the connection returns", async ({
  page,
}) => {
  await signIn(page, "aysel.mammadova", "/");
  await openPage(page, "/profile");
  const save = page.getByRole("button", { name: "Yadda saxlayın" });
  await expect(save).toBeEnabled();

  await page.context().setOffline(true);
  await expect(page.getByText("İnternet bağlantısı yoxdur")).toBeVisible();
  await expect(save).toBeDisabled();
  await expect(save).toHaveAttribute("title", REASON);
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  await page.context().setOffline(false);
  await expect(save).toBeEnabled();
  await expect(page.getByText("İnternet bağlantısı yoxdur")).toHaveCount(0);
});

test("in a chat, uploads are switched off offline while writing stays possible", async ({
  page,
}) => {
  await signIn(page, "aysel.mammadova", "/chat");
  await expect(page.getByRole("navigation", { name: "Kanallar" }).getByRole("status")).toHaveCount(
    0,
    { timeout: 15_000 },
  );
  await page
    .getByRole("navigation", { name: "Kanallar" })
    .getByRole("region", { name: "Fənlər" })
    .locator("> ul")
    .getByRole("link")
    .first()
    .click();
  const attach = page.getByRole("button", { name: "Fayl əlavə edin" });
  await expect(attach).toBeEnabled();

  await page.context().setOffline(true);
  await expect(attach).toBeDisabled();
  await expect(attach).toHaveAttribute("title", REASON);
  const field = page.getByRole("combobox", { name: "Mesaj" });
  await field.fill("Bağlantı olmayanda yazılan mesaj");
  await expect(page.getByRole("button", { name: "Göndərin" })).toBeEnabled();

  await page.context().setOffline(false);
  await expect(attach).toBeEnabled();
});

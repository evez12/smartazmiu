import { expect, test } from "@playwright/test";

import { password, signIn } from "./support/auth";

/*
 * Regression for the 502 at /auth/callback (D-037): a user carrying Keycloak's default roles plus extra roles
 * signs in through nginx, the callback answers 302 with small cookies, and the server-side session works.
 */
test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");

/** Mirrors SET_COOKIE_BUDGET_BYTES in src/lib/auth/session.ts. */
const SET_COOKIE_BUDGET_BYTES = 1024;

test("a user with default and extra roles signs in and keeps a working session", async ({
  page,
  browser,
}, testInfo) => {
  const callback = page.waitForResponse((response) =>
    new URL(response.url()).pathname.startsWith("/auth/callback"),
  );
  await signIn(page, "kanan.babayev");

  const response = await callback;
  expect(response.status()).toBe(302);
  const setCookies = await response.headerValues("set-cookie");
  const total = setCookies.reduce((sum, header) => sum + Buffer.byteLength(header), 0);
  // The measured size goes into the report, so a growing cookie is visible long before it hits the budget.
  const measured = `${total} B in ${setCookies.length} headers (budget ${SET_COOKIE_BUDGET_BYTES} B)`;
  testInfo.annotations.push({ type: "Set-Cookie size at /auth/callback", description: measured });
  console.log(`Set-Cookie size at /auth/callback: ${measured}`);
  expect(total).toBeLessThanOrEqual(SET_COOKIE_BUDGET_BYTES);

  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Profil menyusu/ })).toContainText(
    "Tələbə · Moderator",
  );

  // Only an opaque id reaches the browser; the tokens stay on the server.
  const cookies = await page.context().cookies();
  const session = cookies.find((cookie) => cookie.name === "sa_session");
  expect(session?.value).toMatch(/^[A-Za-z0-9_-]{43}$/);
  expect(session?.httpOnly).toBe(true);
  expect(cookies.map((cookie) => cookie.name)).not.toContain("sa_access");

  // Browser calls go through the same session, and Keycloak's default roles are never mapped.
  const me = await page.request.get("/api/v1/me");
  expect(me.status()).toBe(200);
  expect(((await me.json()) as { roles: string[] }).roles.sort()).toEqual(["moderator", "student"]);

  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Ana səhifə" })).toBeVisible();

  // Signing out deletes the server-side session: a copy of the old cookie no longer opens anything.
  await page.getByRole("button", { name: /Profil menyusu/ }).click();
  await page.getByRole("menuitem", { name: "Çıxış edin" }).click();
  await expect(page).toHaveURL(/\/login\?status=signed_out/);
  const replay = await browser.newContext();
  await replay.addCookies([{ ...session!, sameSite: "Lax" }]);
  expect((await replay.request.get("/api/v1/me")).status()).toBe(401);
  await replay.close();
});

import { createHmac } from "node:crypto";

import { expect, type Page } from "@playwright/test";

/** Shared password of the seeded Keycloak test users (D-020); `make e2e` exports it from .env. */
export const password = process.env.KEYCLOAK_TEST_USER_PASSWORD;

const keycloakUrl = process.env.OIDC_PUBLIC_URL ?? "http://localhost:8080";
const realm = process.env.KEYCLOAK_REALM ?? "smartazmiu";

/** RFC 6238 code; Keycloak keys the HMAC with the UTF-8 bytes of the generated secret. */
export function totp(secret: string, at = Date.now()): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 1000 / 30)));
  const digest = createHmac("sha1", Buffer.from(secret, "utf8")).update(counter).digest();
  const offset = digest[digest.length - 1]! & 0x0f;
  const code = (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return String(code).padStart(6, "0");
}

async function adminToken(): Promise<string> {
  const response = await fetch(`${keycloakUrl}/realms/master/protocol/openid-connect/token`, {
    method: "POST",
    body: new URLSearchParams({
      grant_type: "password",
      client_id: "admin-cli",
      username: process.env.KEYCLOAK_ADMIN_USER ?? "admin",
      password: process.env.KEYCLOAK_ADMIN_PASSWORD ?? "",
    }),
  });
  if (!response.ok) throw new Error(`Keycloak admin sign-in failed: ${response.status}`);
  return ((await response.json()) as { access_token: string }).access_token;
}

/** Forgets a staff member's authenticator, so the next sign-in enrols a new one the test controls. */
async function removeOtpCredentials(username: string): Promise<void> {
  const headers = { Authorization: `Bearer ${await adminToken()}` };
  const base = `${keycloakUrl}/admin/realms/${realm}/users`;
  const users = (await (
    await fetch(`${base}?exact=true&username=${encodeURIComponent(username)}`, { headers })
  ).json()) as { id: string }[];
  const user = users[0];
  if (!user) throw new Error(`Keycloak user ${username} not found`);
  const credentials = (await (
    await fetch(`${base}/${user.id}/credentials`, { headers })
  ).json()) as { id: string; type: string }[];
  for (const credential of credentials.filter((item) => item.type === "otp")) {
    await fetch(`${base}/${user.id}/credentials/${credential.id}`, { method: "DELETE", headers });
  }
}

/** Opens the app signed out and submits the Keycloak login form. */
export async function signIn(page: Page, username: string, startAt = "/") {
  await page.goto(startAt);
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  await page.getByRole("link", { name: "Universitet hesabı ilə daxil olun" }).click();

  await expect(page.getByRole("heading", { name: "Hesabınıza daxil olun" })).toBeVisible();
  await page.getByLabel("İstifadəçi adı və ya e-poçt").fill(username);
  await page.getByLabel("Şifrə", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Daxil olun" }).click();
}

/** Signs in a staff or admin user, enrolling a fresh authenticator on the way (D-018). */
export async function signInWithSecondFactor(page: Page, username: string, startAt = "/") {
  await removeOtpCredentials(username);
  await signIn(page, username, startAt);
  await expect(page.getByRole("heading", { name: "İki mərhələli girişi qurun" })).toBeVisible();
  const secret = await page.locator("#totpSecret").inputValue();
  await page.locator("#totp").fill(totp(secret));
  await page.locator("#userLabel").fill("Playwright");
  await page.locator("#saveTOTPBtn").click();
}

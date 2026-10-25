import { createHmac, randomBytes } from "node:crypto";

import { expect, test as base, type Page } from "@playwright/test";

import { TestRecords } from "./database";

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

async function keycloakAdmin(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${keycloakUrl}/admin/realms/${realm}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${await adminToken()}`,
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) throw new Error(`Keycloak ${init.method ?? "GET"} ${path}: ${response.status}`);
  return response;
}

export type TestAccount = {
  username: string;
  email: string;
  password: string;
  givenName: string;
  familyName: string;
};

/**
 * Creates and deletes Keycloak accounts that exist only for one test, so tests never change the seeded users
 * (their roles, authenticators or passwords). Mirrored rows in the application database stay behind, like those
 * of any account removed from the identity provider, and are recognisable by their `e2e-` e-mail address.
 */
export class TestAccounts {
  private readonly ids: string[] = [];

  async create(
    role: "student" | "teacher" | "staff" | "admin",
    name: { givenName: string; familyName: string },
  ): Promise<TestAccount> {
    const username = `e2e-${role}-${randomBytes(4).toString("hex")}`;
    const account = {
      ...name,
      username,
      email: `${username}@smartazmiu.test`,
      password: randomBytes(18).toString("base64url"),
    };
    const created = await keycloakAdmin("/users", {
      method: "POST",
      body: JSON.stringify({
        username,
        email: account.email,
        emailVerified: true,
        firstName: name.givenName,
        lastName: name.familyName,
        enabled: true,
        credentials: [{ type: "password", value: account.password, temporary: false }],
      }),
    });
    const id = created.headers.get("location")!.split("/").pop()!;
    this.ids.push(id);
    const roleRepresentation = await (await keycloakAdmin(`/roles/${role}`)).json();
    await keycloakAdmin(`/users/${id}/role-mappings/realm`, {
      method: "POST",
      body: JSON.stringify([roleRepresentation]),
    });
    return account;
  }

  async deleteAll(): Promise<void> {
    for (const id of this.ids.splice(0)) {
      await keycloakAdmin(`/users/${id}`, { method: "DELETE" });
    }
  }
}

const appOrigin = new URL(process.env.E2E_BASE_URL ?? "http://localhost:3000").origin;

/**
 * Waits until the current app page has hydrated (`src/lib/hydration-mark.tsx`). Server-rendered controls are
 * visible earlier, but a file chosen or a button pressed before hydration is silently lost; on a cold browser
 * cache right after sign-in this took longer than the test's next step.
 */
export async function hydrated(page: Page): Promise<void> {
  await page.waitForURL((url) => url.origin === appOrigin && !url.pathname.startsWith("/auth/"));
  await expect(page.locator("html[data-hydrated]")).toBeAttached({ timeout: 15_000 });
}

/** A full navigation followed by interaction with client-side controls. */
export async function openPage(page: Page, url: string): Promise<void> {
  await page.goto(url);
  await hydrated(page);
}

async function submitCredentials(page: Page, user: string | TestAccount, startAt: string) {
  const [username, secret] =
    typeof user === "string" ? [user, password!] : [user.username, user.password];
  await page.goto(startAt);
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  await page.getByRole("link", { name: "Universitet hesabı ilə daxil olun" }).click();

  await expect(page.getByRole("heading", { name: "Hesabınıza daxil olun" })).toBeVisible();
  await page.getByLabel("İstifadəçi adı və ya e-poçt").fill(username);
  await page.getByLabel("Şifrə", { exact: true }).fill(secret);
  await page.getByRole("button", { name: "Daxil olun" }).click();
}

/** Opens the app signed out, submits the Keycloak login form and waits for the hydrated landing page. */
export async function signIn(page: Page, user: string | TestAccount, startAt = "/"): Promise<void> {
  await submitCredentials(page, user, startAt);
  await hydrated(page);
}

/** First sign-in of a new staff or admin account, which must enrol an authenticator (D-018). */
export async function signInWithSecondFactor(page: Page, account: TestAccount, startAt = "/") {
  await submitCredentials(page, account, startAt);
  await expect(page.getByRole("heading", { name: "İki mərhələli girişi qurun" })).toBeVisible();
  const secret = await page.locator("#totpSecret").inputValue();
  await page.locator("#totp").fill(totp(secret));
  await page.locator("#userLabel").fill("Playwright");
  await page.locator("#saveTOTPBtn").click();
  await hydrated(page);
}

/**
 * Playwright `test` with fixtures that undo what a test set up: `accounts` deletes its Keycloak accounts and
 * `records` removes the academic records it imported.
 */
export const test = base.extend<{ accounts: TestAccounts; records: TestRecords }>({
  accounts: async ({}, provide) => {
    const accounts = new TestAccounts();
    try {
      await provide(accounts);
    } finally {
      await accounts.deleteAll();
    }
  },
  records: async ({}, provide) => {
    const records = new TestRecords();
    try {
      await provide(records);
    } finally {
      await records.removeAll();
    }
  },
});

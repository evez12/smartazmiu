import { beforeAll, describe, expect, it } from "vitest";

import { contentSecurityPolicy } from "@/lib/csp";
import { scrubEvent } from "@/lib/observability";

import { safeReturnTo } from "./return-to";
import { seal, unseal } from "./seal";

const SECRET = "test-secret-0123456789abcdef0123456789";

beforeAll(() => {
  process.env.SESSION_SECRET = SECRET;
  process.env.APP_URL = "http://localhost:3000";
});

describe("safeReturnTo", () => {
  it.each([
    ["/", "/"],
    ["/design-system?tab=forms#colors", "/design-system?tab=forms#colors"],
    [null, "/"],
    ["", "/"],
    ["https://evil.example/", "/"],
    ["//evil.example/steal", "/"],
    ["/\\evil.example", "/"],
    ["javascript:alert(1)", "/"],
    ["/auth/signout", "/"],
    ["/\u0000x", "/"],
  ])("%s -> %s", (input, expected) => {
    expect(safeReturnTo(input)).toBe(expected);
  });
});

describe("sealed cookies", () => {
  it("round-trips a payload", async () => {
    const value = await seal({ refreshToken: "rt", subject: "s" }, SECRET, 60);
    expect(value).not.toContain("rt");
    expect(await unseal(value, SECRET)).toMatchObject({ refreshToken: "rt", subject: "s" });
  });

  it("rejects tampering, another key and expiry", async () => {
    const value = await seal({ refreshToken: "rt" }, SECRET, 60);
    const tampered = `${value.slice(0, -4)}${value.endsWith("AAAA") ? "BBBB" : "AAAA"}`;
    expect(await unseal(tampered, SECRET)).toBeNull();
    expect(await unseal(value, `${SECRET}-rotated`)).toBeNull();
    expect(await unseal(await seal({ refreshToken: "rt" }, SECRET, -10), SECRET)).toBeNull();
    expect(await unseal(undefined, SECRET)).toBeNull();
  });
});

describe("session cookies", () => {
  it("keeps the refresh token and CSRF token across a refresh", async () => {
    const { sessionCookies, readSession, readAccess, SESSION_COOKIE, ACCESS_COOKIE } =
      await import("./session");
    const header = Buffer.from(JSON.stringify({ alg: "none" })).toString("base64url");
    const claims = Buffer.from(JSON.stringify({ sub: "kc-aysel" })).toString("base64url");
    const accessToken = `${header}.${claims}.sig`;

    const first = await sessionCookies({
      access_token: accessToken,
      refresh_token: "rt-1",
      expires_in: 900,
      refresh_expires_in: 28800,
    });
    const jar = (cookies: { name: string; value: string }[]) => ({
      get: (name: string) => cookies.find((cookie) => cookie.name === name),
    });
    const session = await readSession(jar(first));
    expect(session).toMatchObject({ refreshToken: "rt-1", subject: "kc-aysel" });
    expect(first.find((c) => c.name === SESSION_COOKIE)?.maxAge).toBe(28800);
    expect(first.find((c) => c.name === ACCESS_COOKIE)?.maxAge).toBe(900);

    // Keycloak may omit a new refresh token; the previous one and the CSRF token are kept.
    const second = await sessionCookies({ access_token: accessToken, expires_in: 900 }, session);
    const refreshed = await readSession(jar(second));
    expect(refreshed?.refreshToken).toBe("rt-1");
    expect(refreshed?.csrfToken).toBe(session?.csrfToken);
    expect((await readAccess(jar(second)))?.accessToken).toBe(accessToken);
  });
});

describe("contentSecurityPolicy", () => {
  it("allows scripts only with the nonce in production", () => {
    const csp = contentSecurityPolicy({ nonce: "abc", isDev: false, isHttps: true });
    expect(csp).toContain("script-src 'self' 'nonce-abc' 'strict-dynamic'");
    expect(csp).not.toContain("unsafe-eval");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("upgrade-insecure-requests");
  });

  it("relaxes only what local development needs", () => {
    const csp = contentSecurityPolicy({ nonce: "abc", isDev: true, isHttps: false });
    expect(csp).toContain("'unsafe-eval'");
    expect(csp).not.toContain("upgrade-insecure-requests");
  });
});

describe("scrubEvent", () => {
  it("removes credentials and personal data", () => {
    const event = scrubEvent({
      type: undefined,
      request: {
        headers: { Authorization: "Bearer x", Cookie: "sa_session=1", Accept: "*/*" },
        cookies: { sa_session: "1" },
        query_string: "code=abc",
      },
      user: { id: "0190", email: "aysel.mammadova@smartazmiu.test" },
    });
    expect(event.request).toEqual({ headers: { Accept: "*/*" } });
    expect(event.user).toEqual({ id: "0190" });
  });
});

describe("session readers without configuration", () => {
  it("return null without touching SESSION_SECRET when no cookie is present", async () => {
    const { readSession, readAccess } = await import("./session");
    const secret = process.env.SESSION_SECRET;
    delete process.env.SESSION_SECRET;
    try {
      const emptyJar = { get: () => undefined };
      expect(await readSession(emptyJar)).toBeNull();
      expect(await readAccess(emptyJar)).toBeNull();
    } finally {
      process.env.SESSION_SECRET = secret;
    }
  });
});

import { beforeAll, describe, expect, it } from "vitest";

import { contentSecurityPolicy } from "@/lib/csp";
import { socketUrlFor } from "@/lib/env";
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
    // Long enough that random base64 ciphertext never contains it by chance ("rt" did about 3 % of the time).
    const token = "refresh-token-plaintext";
    const value = await seal({ refreshToken: token, subject: "s" }, SECRET, 60);
    expect(value).not.toContain(token);
    expect(await unseal(value, SECRET)).toMatchObject({ refreshToken: token, subject: "s" });
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

  it("lets the page open the chat socket and nothing else", () => {
    const csp = contentSecurityPolicy({
      nonce: "abc",
      isDev: false,
      isHttps: true,
      socketUrl: "wss://smartazmiu.example/ws",
    });
    expect(csp).toContain("connect-src 'self' wss://smartazmiu.example;");
    expect(socketUrlFor("https://smartazmiu.example")).toBe("wss://smartazmiu.example/ws");
    expect(socketUrlFor("http://localhost")).toBe("ws://localhost/ws");
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

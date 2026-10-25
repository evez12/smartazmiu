import { NextRequest } from "next/server";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionStore, StoredSession } from "./session-store";

const SECRET = "test-secret-0123456789abcdef0123456789";

class MemoryStore implements SessionStore {
  entries = new Map<string, { session: StoredSession; ttl: number }>();
  calls = 0;
  async get(key: string) {
    this.calls += 1;
    return this.entries.get(key)?.session ?? null;
  }
  async set(key: string, session: StoredSession, ttl: number) {
    this.calls += 1;
    this.entries.set(key, { session, ttl });
  }
  async delete(key: string) {
    this.calls += 1;
    this.entries.delete(key);
  }
}

const store = new MemoryStore();
vi.mock("./session-store", () => ({ sessionStore: () => store }));

const completeSignIn = vi.fn();
vi.mock("./oidc", () => ({ completeSignIn: (...args: unknown[]) => completeSignIn(...args) }));

function jwt(claims: Record<string, unknown>) {
  const part = (value: unknown) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${part({ alg: "RS256", typ: "JWT" })}.${part(claims)}.${"s".repeat(342)}`;
}

/** Larger than anything Keycloak issued in the verification run (default roles, client roles, long names). */
const bulkyTokens = {
  access_token: jwt({
    sub: "kc-kanan",
    email: "kanan.babayev.with.a.long.address@smartazmiu.test",
    name: "Kənan Babayev",
    realm_access: {
      roles: [
        "default-roles-smartazmiu",
        "offline_access",
        "uma_authorization",
        "student",
        "moderator",
      ],
    },
    resource_access: {
      account: { roles: ["manage-account", "manage-account-links", "view-profile"] },
      ...Object.fromEntries(
        Array.from({ length: 20 }, (_, i) => [`client-${i}`, { roles: ["role"] }]),
      ),
    },
  }),
  refresh_token: `rt-${"r".repeat(2000)}`,
  expires_in: 900,
  refresh_expires_in: 28800,
};

const jar = (cookies: Record<string, string>) => ({
  get: (name: string) => (name in cookies ? { value: cookies[name]! } : undefined),
});

beforeAll(() => {
  process.env.SESSION_SECRET = SECRET;
  process.env.APP_URL = "http://localhost";
});

beforeEach(() => {
  store.entries.clear();
  store.calls = 0;
});

afterEach(() => completeSignIn.mockReset());

describe("server-side sessions", () => {
  it("keeps tokens out of the cookie and keys the store by a hash of the id", async () => {
    const { createSession, readSession, SESSION_COOKIE } = await import("./session");
    const cookie = await createSession(bulkyTokens);

    expect(cookie.name).toBe(SESSION_COOKIE);
    expect(cookie.value).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(cookie.maxAge).toBe(28800);
    const [key, entry] = [...store.entries][0]!;
    expect(key).not.toBe(cookie.value);
    expect(entry!.ttl).toBe(28800);
    expect(entry!.session.accessToken).toBe(bulkyTokens.access_token);

    const session = await readSession(jar({ [SESSION_COOKIE]: cookie.value }));
    expect(session).toMatchObject({ id: cookie.value, subject: "kc-kanan" });
    expect(session?.csrfToken).toMatch(/^[A-Za-z0-9_-]{43}$/);
  });

  it("keeps the CSRF token and refresh token across a refresh", async () => {
    const { createSession, readSession, updateSession, SESSION_COOKIE } = await import("./session");
    const cookie = await createSession(bulkyTokens);
    const before = (await readSession(jar({ [SESSION_COOKIE]: cookie.value })))!;

    // Keycloak may omit a new refresh token.
    const renewed = await updateSession(before, {
      access_token: jwt({ sub: "kc-kanan" }),
      expires_in: 900,
    });
    const after = (await readSession(jar({ [SESSION_COOKIE]: cookie.value })))!;

    expect(renewed.value).toBe(cookie.value);
    expect(after.refreshToken).toBe(bulkyTokens.refresh_token);
    expect(after.csrfToken).toBe(before.csrfToken);
    expect(after.accessToken).not.toBe(before.accessToken);
  });

  it("ends a session", async () => {
    const { createSession, destroySession, readSession, SESSION_COOKIE } =
      await import("./session");
    const cookie = await createSession(bulkyTokens);
    const session = (await readSession(jar({ [SESSION_COOKIE]: cookie.value })))!;
    await destroySession(session);
    expect(await readSession(jar({ [SESSION_COOKIE]: cookie.value }))).toBeNull();
  });

  it("never contacts the store, secret or Redis without a well-formed cookie", async () => {
    const { readSession, SESSION_COOKIE } = await import("./session");
    const secret = process.env.SESSION_SECRET;
    delete process.env.SESSION_SECRET;
    try {
      expect(await readSession(jar({}))).toBeNull();
      expect(await readSession(jar({ [SESSION_COOKIE]: "not-a-session-id" }))).toBeNull();
      expect(store.calls).toBe(0);
    } finally {
      process.env.SESSION_SECRET = secret;
    }
  });
});

describe("/auth/callback", () => {
  it("signs in with a 302 and Set-Cookie headers within the budget, whatever the token size", async () => {
    const { oidcFlowCookie, OIDC_COOKIE, SET_COOKIE_BUDGET_BYTES } = await import("./session");
    const { GET } = await import("@/app/auth/callback/route");
    completeSignIn.mockResolvedValue(bulkyTokens);
    const flow = await oidcFlowCookie({ state: "s", nonce: "n", codeVerifier: "v", returnTo: "/" });
    const request = new NextRequest("http://localhost/auth/callback?code=c&state=s", {
      headers: { cookie: `${OIDC_COOKIE}=${flow.value}` },
    });

    const response = await GET(request);

    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("http://localhost/");
    const setCookies = response.headers.getSetCookie();
    const total = setCookies.reduce((sum, header) => sum + Buffer.byteLength(header), 0);
    expect(total).toBeLessThanOrEqual(SET_COOKIE_BUDGET_BYTES);
    expect(setCookies.map((header) => header.split("=")[0])).toEqual(["sa_session", OIDC_COOKIE]);
    // The access token is ~2.5 KB here; none of it may travel to the browser.
    expect(setCookies.join("")).not.toContain(bulkyTokens.access_token.slice(0, 40));
    expect(setCookies.join("")).not.toContain("rt-rrrr");
  });

  it("sends the user back to sign in when the session cannot be stored", async () => {
    const { oidcFlowCookie, OIDC_COOKIE } = await import("./session");
    const { GET } = await import("@/app/auth/callback/route");
    completeSignIn.mockResolvedValue(bulkyTokens);
    const failing = vi.spyOn(store, "set").mockRejectedValueOnce(new Error("redis down"));
    const flow = await oidcFlowCookie({ state: "s", nonce: "n", codeVerifier: "v", returnTo: "/" });
    const response = await GET(
      new NextRequest("http://localhost/auth/callback?code=c&state=s", {
        headers: { cookie: `${OIDC_COOKIE}=${flow.value}` },
      }),
    );
    expect(response.headers.get("location")).toBe("http://localhost/login?error=signin_failed");
    failing.mockRestore();
  });
});

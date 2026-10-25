import "server-only";

import { env } from "@/lib/env";

import { seal, unseal } from "./seal";
import { sessionStore, type StoredSession } from "./session-store";

export const SESSION_COOKIE = "sa_session";
export const OIDC_COOKIE = "sa_oidc";

/**
 * Upper bound for all Set-Cookie headers of one response. Tokens never travel in cookies, so a sign-in stays far
 * below the 4 KB response-header buffers of proxies whatever roles the identity provider adds (DECISIONS D-037).
 */
export const SET_COOKIE_BUDGET_BYTES = 1024;

/** A signed-in browser session: the opaque id from the cookie and the server-side state behind it. */
export type SessionData = StoredSession & { id: string };

/** Transient state of a sign-in in progress (PKCE, state, nonce). */
export type OidcFlowData = {
  state: string;
  nonce: string;
  codeVerifier: string;
  returnTo: string;
};

export type TokenSet = {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  refresh_expires_in?: number;
};

type CookieWrite = {
  name: string;
  value: string;
  maxAge: number;
};

export type CookieJar = {
  get(name: string): { value: string } | undefined;
};

export const OIDC_FLOW_MAX_AGE = 10 * 60;
const DEFAULT_ACCESS_LIFETIME = 15 * 60;
const DEFAULT_SESSION_LIFETIME = 8 * 60 * 60;
const SESSION_ID = /^[A-Za-z0-9_-]{43}$/;

export function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    // Browsers treat http://localhost as a secure context, so Secure works for local development too.
    secure: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}

/** The store keys on a hash of the id, so a dump of the store holds nothing a browser could present. */
async function storeKey(id: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(id));
  return Buffer.from(digest).toString("base64url");
}

function stored(tokens: TokenSet, previous?: StoredSession | null) {
  const refreshToken = tokens.refresh_token ?? previous?.refreshToken;
  if (!refreshToken) throw new Error("token response without refresh token");
  const lifetime = tokens.refresh_expires_in || DEFAULT_SESSION_LIFETIME;
  const session: StoredSession = {
    refreshToken,
    accessToken: tokens.access_token,
    accessExpiresAt: Math.floor(Date.now() / 1000) + (tokens.expires_in ?? DEFAULT_ACCESS_LIFETIME),
    subject: previous?.subject ?? subjectOf(tokens.access_token),
    csrfToken: previous?.csrfToken ?? randomToken(),
  };
  return { session, lifetime };
}

/** Stores a new session for a token endpoint response and returns the cookie that refers to it. */
export async function createSession(tokens: TokenSet): Promise<CookieWrite> {
  const id = randomToken();
  const { session, lifetime } = stored(tokens);
  await sessionStore().set(await storeKey(id), session, lifetime);
  return { name: SESSION_COOKIE, value: id, maxAge: lifetime };
}

/**
 * Replaces the tokens after a refresh; keeps the CSRF token and, if Keycloak sends none, the refresh token.
 * Returns the cookie again with the new lifetime, so its expiry follows the Keycloak session.
 */
export async function updateSession(session: SessionData, tokens: TokenSet): Promise<CookieWrite> {
  const { session: next, lifetime } = stored(tokens, session);
  await sessionStore().set(await storeKey(session.id), next, lifetime);
  return { name: SESSION_COOKIE, value: session.id, maxAge: lifetime };
}

export async function destroySession(session: SessionData): Promise<void> {
  await sessionStore().delete(await storeKey(session.id));
}

/**
 * The session behind the request's cookie, or null. The store is only contacted when a well-formed cookie is
 * present, so pages that never see a session (e.g. /design-system in the screenshot container) work without
 * Redis or auth configuration.
 */
export async function readSession(jar: CookieJar): Promise<SessionData | null> {
  const id = jar.get(SESSION_COOKIE)?.value;
  if (!id || !SESSION_ID.test(id)) return null;
  const session = await sessionStore().get(await storeKey(id));
  return session ? { ...session, id } : null;
}

export async function readOidcFlow(jar: CookieJar): Promise<OidcFlowData | null> {
  const value = jar.get(OIDC_COOKIE)?.value;
  return value ? unseal<OidcFlowData>(value, env.sessionSecret) : null;
}

export async function oidcFlowCookie(flow: OidcFlowData): Promise<CookieWrite> {
  return {
    name: OIDC_COOKIE,
    value: await seal(flow, env.sessionSecret, OIDC_FLOW_MAX_AGE),
    maxAge: OIDC_FLOW_MAX_AGE,
  };
}

export function randomToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Buffer.from(bytes).toString("base64url");
}

function subjectOf(accessToken: string): string {
  const payload = accessToken.split(".")[1];
  if (!payload) return "";
  try {
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as {
      sub?: string;
    };
    return claims.sub ?? "";
  } catch {
    return "";
  }
}

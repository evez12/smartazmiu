import "server-only";

import { env } from "@/lib/env";

import { seal, unseal } from "./seal";

export const SESSION_COOKIE = "sa_session";
export const ACCESS_COOKIE = "sa_access";
export const OIDC_COOKIE = "sa_oidc";

/** Long-lived part: the refresh token and the CSRF token for cookie-authenticated form posts. */
export type SessionData = {
  refreshToken: string;
  subject: string;
  csrfToken: string;
};

/** Short-lived part: the 15-minute access token forwarded to the API. */
export type AccessData = {
  accessToken: string;
  /** Unix seconds. */
  expiresAt: number;
};

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

/** Builds the session and access cookies from a token endpoint response. */
export async function sessionCookies(
  tokens: TokenSet,
  previous?: SessionData | null,
): Promise<CookieWrite[]> {
  const refreshToken = tokens.refresh_token ?? previous?.refreshToken;
  if (!refreshToken) throw new Error("token response without refresh token");
  const accessLifetime = tokens.expires_in ?? DEFAULT_ACCESS_LIFETIME;
  const sessionLifetime = tokens.refresh_expires_in || DEFAULT_SESSION_LIFETIME;
  const session: SessionData = {
    refreshToken,
    subject: previous?.subject ?? subjectOf(tokens.access_token),
    csrfToken: previous?.csrfToken ?? randomToken(),
  };
  const access: AccessData = {
    accessToken: tokens.access_token,
    expiresAt: Math.floor(Date.now() / 1000) + accessLifetime,
  };
  return [
    {
      name: SESSION_COOKIE,
      value: await seal(session, env.sessionSecret, sessionLifetime),
      maxAge: sessionLifetime,
    },
    {
      name: ACCESS_COOKIE,
      value: await seal(access, env.sessionSecret, accessLifetime),
      maxAge: accessLifetime,
    },
  ];
}

// The secret is read only when a cookie is present, so pages that never see a session (e.g. /design-system
// in the screenshot container) work without auth configuration.
async function readSealed<T>(jar: CookieJar, name: string): Promise<T | null> {
  const value = jar.get(name)?.value;
  return value ? unseal<T>(value, env.sessionSecret) : null;
}

export function readSession(jar: CookieJar): Promise<SessionData | null> {
  return readSealed<SessionData>(jar, SESSION_COOKIE);
}

export function readAccess(jar: CookieJar): Promise<AccessData | null> {
  return readSealed<AccessData>(jar, ACCESS_COOKIE);
}

export function readOidcFlow(jar: CookieJar): Promise<OidcFlowData | null> {
  return readSealed<OidcFlowData>(jar, OIDC_COOKIE);
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

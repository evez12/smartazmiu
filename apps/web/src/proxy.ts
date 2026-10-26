import { NextResponse, type NextRequest } from "next/server";

import { refreshTokens } from "@/lib/auth/oidc";
import {
  cookieOptions,
  destroySession,
  readSession,
  SESSION_COOKIE,
  updateSession,
  type SessionData,
} from "@/lib/auth/session";
import { contentSecurityPolicy } from "@/lib/csp";
import { env } from "@/lib/env";
import { PATHNAME_HEADER } from "@/lib/request-headers";

/** Refresh a little before expiry so a page never renders with a token that dies mid-request. */
const REFRESH_MARGIN_SECONDS = 60;

type SessionUpdate = { cookie: { name: string; value: string; maxAge: number } } | "clear" | null;

async function refreshIfNeeded(request: NextRequest): Promise<SessionUpdate> {
  if (request.nextUrl.pathname.startsWith("/auth/")) return null;
  if (!request.cookies.has(SESSION_COOKIE)) return null;
  let session: SessionData | null;
  try {
    session = await readSession(request.cookies);
  } catch (error) {
    // Session store unreachable: the page renders its "unavailable" state instead of signing the user out.
    console.warn(JSON.stringify({ event: "session_store_unavailable", error: String(error) }));
    return null;
  }
  // A cookie whose session expired or was ended elsewhere.
  if (!session) return "clear";
  const now = Math.floor(Date.now() / 1000);
  if (session.accessExpiresAt - now > REFRESH_MARGIN_SECONDS) return null;
  try {
    return { cookie: await updateSession(session, await refreshTokens(session.refreshToken)) };
  } catch (error) {
    // Expired or revoked session (logout elsewhere, admin action, rotation reuse): sign out locally.
    console.warn(JSON.stringify({ event: "session_refresh_failed", error: String(error) }));
    await destroySession(session).catch(() => undefined);
    return "clear";
  }
}

export async function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy({
    nonce,
    isDev: process.env.NODE_ENV === "development",
    isHttps: env.isHttps,
    socketUrl: env.socketUrl,
  });

  const update = await refreshIfNeeded(request);
  // Server components read the session id from the request cookies; a cleared session must not reach them.
  if (update === "clear") request.cookies.delete(SESSION_COOKIE);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", csp);
  requestHeaders.set(PATHNAME_HEADER, `${request.nextUrl.pathname}${request.nextUrl.search}`);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  if (env.isHttps) {
    response.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  }
  if (update === "clear") {
    response.cookies.delete(SESSION_COOKIE);
  } else if (update) {
    // Same id; renewed so the cookie expires together with the Keycloak session.
    response.cookies.set(
      update.cookie.name,
      update.cookie.value,
      cookieOptions(update.cookie.maxAge),
    );
  }
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|icon.svg|healthz).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};

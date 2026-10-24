import { NextResponse, type NextRequest } from "next/server";

import { refreshTokens } from "@/lib/auth/oidc";
import {
  ACCESS_COOKIE,
  cookieOptions,
  readAccess,
  readSession,
  SESSION_COOKIE,
  sessionCookies,
} from "@/lib/auth/session";
import { contentSecurityPolicy } from "@/lib/csp";
import { env } from "@/lib/env";
import { PATHNAME_HEADER } from "@/lib/request-headers";

/** Refresh a little before expiry so a page never renders with a token that dies mid-request. */
const REFRESH_MARGIN_SECONDS = 60;

type SessionUpdate = { set: { name: string; value: string; maxAge: number }[] } | "clear" | null;

async function refreshIfNeeded(request: NextRequest): Promise<SessionUpdate> {
  if (request.nextUrl.pathname.startsWith("/auth/")) return null;
  const session = await readSession(request.cookies);
  if (!session) return null;
  const access = await readAccess(request.cookies);
  const now = Math.floor(Date.now() / 1000);
  if (access && access.expiresAt - now > REFRESH_MARGIN_SECONDS) return null;
  try {
    return { set: await sessionCookies(await refreshTokens(session.refreshToken), session) };
  } catch (error) {
    // Expired or revoked session (logout elsewhere, admin action, rotation reuse): sign out locally.
    console.warn(JSON.stringify({ event: "session_refresh_failed", error: String(error) }));
    return "clear";
  }
}

export async function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy({
    nonce,
    isDev: process.env.NODE_ENV === "development",
    isHttps: env.isHttps,
  });

  const update = await refreshIfNeeded(request);
  // Server components read cookies from the request, so the refreshed values are forwarded there too.
  if (update === "clear") {
    request.cookies.delete(SESSION_COOKIE);
    request.cookies.delete(ACCESS_COOKIE);
  } else if (update) {
    for (const cookie of update.set) request.cookies.set(cookie.name, cookie.value);
  }

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
    response.cookies.delete(ACCESS_COOKIE);
  } else if (update) {
    for (const cookie of update.set) {
      response.cookies.set(cookie.name, cookie.value, cookieOptions(cookie.maxAge));
    }
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

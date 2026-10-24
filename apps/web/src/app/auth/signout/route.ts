import { NextResponse, type NextRequest } from "next/server";

import { endSession } from "@/lib/auth/oidc";
import { ACCESS_COOKIE, readSession, SESSION_COOKIE } from "@/lib/auth/session";
import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Sign-out is a cookie-authenticated POST, so it requires the session's CSRF token (§14) and a same-origin
 * Origin header when the browser sends one.
 */
export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(env.appUrl).origin) {
    return new NextResponse(null, { status: 403 });
  }
  const session = await readSession(request.cookies);
  const form = await request.formData().catch(() => null);
  if (session && form?.get("csrf") !== session.csrfToken) {
    return new NextResponse(null, { status: 403 });
  }

  if (session) {
    try {
      await endSession(session.refreshToken);
    } catch (error) {
      // The local session is cleared regardless; Keycloak expires its session on its own.
      console.warn(JSON.stringify({ event: "keycloak_logout_failed", error: String(error) }));
    }
  }

  const response = NextResponse.redirect(new URL("/login?status=signed_out", env.appUrl), 303);
  response.cookies.delete(SESSION_COOKIE);
  response.cookies.delete(ACCESS_COOKIE);
  return response;
}

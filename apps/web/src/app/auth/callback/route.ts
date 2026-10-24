import { NextResponse, type NextRequest } from "next/server";

import { completeSignIn } from "@/lib/auth/oidc";
import { cookieOptions, OIDC_COOKIE, readOidcFlow, sessionCookies } from "@/lib/auth/session";
import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

function toLogin(reason: string) {
  const response = NextResponse.redirect(new URL(`/login?error=${reason}`, env.appUrl));
  response.cookies.delete(OIDC_COOKIE);
  return response;
}

/** Keycloak returns here with an authorization code; it is exchanged server-side for tokens. */
export async function GET(request: NextRequest) {
  const flow = await readOidcFlow(request.cookies);
  if (!flow) return toLogin("signin_expired");
  if (request.nextUrl.searchParams.has("error")) return toLogin("signin_failed");

  // Behind nginx the request URL is the internal one; the code is bound to the public redirect URI.
  const currentUrl = new URL(`${request.nextUrl.pathname}${request.nextUrl.search}`, env.appUrl);
  try {
    const tokens = await completeSignIn(currentUrl, flow);
    const response = NextResponse.redirect(new URL(flow.returnTo, env.appUrl));
    for (const cookie of await sessionCookies(tokens)) {
      response.cookies.set(cookie.name, cookie.value, cookieOptions(cookie.maxAge));
    }
    response.cookies.delete(OIDC_COOKIE);
    return response;
  } catch (error) {
    console.warn(JSON.stringify({ event: "signin_callback_failed", error: String(error) }));
    return toLogin("signin_failed");
  }
}

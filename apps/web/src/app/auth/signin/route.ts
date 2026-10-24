import { NextResponse, type NextRequest } from "next/server";

import { beginSignIn } from "@/lib/auth/oidc";
import { safeReturnTo } from "@/lib/auth/return-to";
import { cookieOptions, oidcFlowCookie } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

/** Starts the authorization code flow with PKCE and sends the browser to Keycloak. */
export async function GET(request: NextRequest) {
  const returnTo = safeReturnTo(request.nextUrl.searchParams.get("returnTo"));
  const { url, codeVerifier, state, nonce } = await beginSignIn();
  const flow = await oidcFlowCookie({ codeVerifier, state, nonce, returnTo });

  const response = NextResponse.redirect(url);
  response.cookies.set(flow.name, flow.value, cookieOptions(flow.maxAge));
  return response;
}

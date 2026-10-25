import { NextResponse, type NextRequest } from "next/server";
import { getTranslations } from "next-intl/server";

import {
  apiPath,
  CSRF_HEADER,
  FORWARDED_REQUEST_HEADERS,
  FORWARDED_RESPONSE_HEADERS,
  isAllowedMutation,
  SAFE_METHODS,
} from "@/lib/api/proxy";
import { readAccess, readSession } from "@/lib/auth/session";
import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 30_000;

type ProxyErrorKey = "sessionExpired" | "forbidden" | "notFound" | "unavailable";

async function proxyError(status: number, code: string, messageKey: ProxyErrorKey) {
  const t = await getTranslations("api");
  return NextResponse.json(
    { error: { code, message: t(messageKey), details: {}, request_id: null } },
    { status },
  );
}

/**
 * Same-origin entry point for browser calls to the API (DECISIONS D-025, D-037): the access token stays in
 * the httpOnly cookie and is added here, so page JavaScript never sees it. The proxy in `src/proxy.ts` has
 * already refreshed the token when it was about to expire.
 */
async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = apiPath((await context.params).path);
  if (!path) return proxyError(404, "request.not_found", "notFound");

  const [session, access] = await Promise.all([
    readSession(request.cookies),
    readAccess(request.cookies),
  ]);
  if (!session || !access) return proxyError(401, "auth.unauthenticated", "sessionExpired");

  const method = request.method.toUpperCase();
  const allowed = isAllowedMutation({
    method,
    origin: request.headers.get("origin"),
    appOrigin: new URL(env.appUrl).origin,
    csrfHeader: request.headers.get(CSRF_HEADER),
    sessionCsrf: session.csrfToken,
  });
  if (!allowed) return proxyError(403, "auth.csrf_failed", "forbidden");

  const headers = new Headers({
    Authorization: `Bearer ${access.accessToken}`,
    "Accept-Language": "az",
  });
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const requestId = request.headers.get("x-request-id");
  if (requestId) headers.set("X-Request-ID", requestId);

  let upstream: Response;
  try {
    upstream = await fetch(new URL(`${path}${request.nextUrl.search}`, env.apiInternalUrl), {
      method,
      headers,
      body: SAFE_METHODS.has(method) ? undefined : request.body,
      // Streams uploads instead of buffering them in memory.
      duplex: "half",
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    } as RequestInit);
  } catch (error) {
    console.warn(JSON.stringify({ event: "api_proxy_failed", path, error: String(error) }));
    return proxyError(503, "server.unavailable", "unavailable");
  }

  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new NextResponse(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export { forward as DELETE, forward as GET, forward as PATCH, forward as POST, forward as PUT };

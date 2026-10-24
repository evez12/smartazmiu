import "server-only";

import createClient from "openapi-fetch";
import { cookies, headers } from "next/headers";
import { cache } from "react";

import { readAccess, readSession, type SessionData } from "@/lib/auth/session";
import { env } from "@/lib/env";

import type { components, paths } from "./schema";

export type Me = components["schemas"]["MeResponse"];
export type ApiError = components["schemas"]["ErrorResponse"]["error"];

/** Typed client for calls made by the Next.js server on behalf of the signed-in user. */
export function apiClient(accessToken: string) {
  return createClient<paths>({
    baseUrl: env.apiInternalUrl,
    headers: { Authorization: `Bearer ${accessToken}`, "Accept-Language": "az" },
  });
}

export type CurrentUserResult =
  | { status: "signed_out" }
  | { status: "ok"; user: Me; session: SessionData }
  | { status: "inactive" }
  | { status: "unavailable" };

/**
 * The signed-in user for this request, fetched once per render. "signed_out" covers a missing or rejected
 * session; "unavailable" means the API could not answer and the shell shows an error state with retry.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUserResult> => {
  const jar = await cookies();
  const [session, access] = await Promise.all([readSession(jar), readAccess(jar)]);
  if (!session || !access) return { status: "signed_out" };

  const requestId = (await headers()).get("x-request-id") ?? undefined;
  try {
    const { data, error, response } = await apiClient(access.accessToken).GET("/api/v1/me", {
      headers: requestId ? { "X-Request-ID": requestId } : undefined,
      signal: AbortSignal.timeout(5000),
    });
    if (data) return { status: "ok", user: data, session };
    if (response.status === 401) return { status: "signed_out" };
    if (error?.error.code === "auth.account_inactive") return { status: "inactive" };
    console.warn(
      JSON.stringify({
        event: "me_request_failed",
        status: response.status,
        request_id: error?.error.request_id,
      }),
    );
    return { status: "unavailable" };
  } catch {
    return { status: "unavailable" };
  }
});

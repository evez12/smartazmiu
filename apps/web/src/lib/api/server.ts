import "server-only";

import createClient from "openapi-fetch";
import { cookies, headers } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { cache } from "react";

import { readSession, type SessionData } from "@/lib/auth/session";
import { env } from "@/lib/env";
import { PATHNAME_HEADER } from "@/lib/request-headers";

import type { components, paths } from "./schema";

export type Me = components["schemas"]["MeResponse"];
export type ApiError = components["schemas"]["ErrorResponse"]["error"];

/** Typed client for calls made by the Next.js server on behalf of the signed-in user. */
export function apiClient(accessToken: string, requestId?: string) {
  return createClient<paths>({
    baseUrl: env.apiInternalUrl,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Accept-Language": "az",
      ...(requestId ? { "X-Request-ID": requestId } : {}),
    },
  });
}

export type CurrentUserResult =
  | { status: "signed_out" }
  | { status: "ok"; user: Me; session: SessionData }
  | { status: "inactive" }
  | { status: "unavailable" };

async function signInUrl(): Promise<string> {
  const pathname = (await headers()).get(PATHNAME_HEADER) ?? "/";
  return `/login?returnTo=${encodeURIComponent(pathname)}`;
}

/**
 * The signed-in user for this request, fetched once per render. "signed_out" covers a missing or rejected
 * session; "unavailable" means the API could not answer and the shell shows an error state with retry.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUserResult> => {
  let session: SessionData | null;
  try {
    session = await readSession(await cookies());
  } catch {
    return { status: "unavailable" };
  }
  if (!session) return { status: "signed_out" };

  const requestId = (await headers()).get("x-request-id") ?? undefined;
  try {
    const { data, error, response } = await apiClient(session.accessToken, requestId).GET(
      "/api/v1/me",
      { signal: AbortSignal.timeout(5000) },
    );
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

/** Whether the signed-in user holds a permission; pages use it to show the forbidden state early. */
export async function hasPermission(code: string): Promise<boolean> {
  const result = await getCurrentUser();
  return result.status === "ok" && result.user.permissions.includes(code);
}

/**
 * API client for server components. Layouts and pages render in parallel, so a page cannot rely on the
 * layout's sign-in redirect having happened first.
 */
export const serverApi = cache(async () => {
  const session = await readSession(await cookies());
  if (!session) redirect(await signInUrl());
  return apiClient(session.accessToken, (await headers()).get("x-request-id") ?? undefined);
});

export type Loaded<T> = { status: "ok"; data: T } | { status: "forbidden" };

/** Maps an API result to page states: 401 signs in again, 403 is the forbidden state, 404 the not-found page. */
export async function loaded<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): Promise<Loaded<T>> {
  if (result.data !== undefined) return { status: "ok", data: result.data };
  const { status } = result.response;
  if (status === 401) redirect(await signInUrl());
  if (status === 403) return { status: "forbidden" };
  if (status === 404) notFound();
  throw new Error(`API request failed with status ${status}`);
}

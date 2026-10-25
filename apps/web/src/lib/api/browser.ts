import createClient from "openapi-fetch";

import { CSRF_HEADER, SAFE_METHODS } from "./proxy";
import type { components, paths } from "./schema";

type ErrorBody = components["schemas"]["ErrorResponse"]["error"];

/** A failed API call, carrying the envelope's stable code and its localized message (§4.2). */
export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

/** Typed client for calls from the browser, through the same-origin proxy in `app/api/v1`. */
export function createBrowserApi(csrfToken: string) {
  const client = createClient<paths>({
    baseUrl: globalThis.location?.origin ?? "",
    headers: { "Accept-Language": "az" },
  });
  client.use({
    onRequest({ request }) {
      if (!SAFE_METHODS.has(request.method)) request.headers.set(CSRF_HEADER, csrfToken);
      return request;
    },
  });
  return client;
}

export type BrowserApi = ReturnType<typeof createBrowserApi>;

/**
 * The data of an openapi-fetch result (undefined for 204 No Content), or an ApiRequestError built from the
 * error envelope.
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok) return result.data as T;
  const body = (result.error as { error?: Partial<ErrorBody> } | undefined)?.error;
  throw new ApiRequestError(
    result.response.status,
    body?.code ?? "request.failed",
    body?.message ?? "",
    (body?.details as Record<string, unknown> | undefined) ?? {},
  );
}

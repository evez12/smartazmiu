/** Header carrying the per-session CSRF token on browser mutations through the API proxy (§14). */
export const CSRF_HEADER = "x-csrf-token";

export const SAFE_METHODS = new Set(["GET", "HEAD"]);

/** Request headers worth passing to the API; cookies and the browser's own Authorization never are. */
export const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "if-match",
  "if-none-match",
  "idempotency-key",
];

export const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-disposition",
  "content-type",
  "etag",
  "last-modified",
  "retry-after",
  "x-request-id",
];

type MutationCheck = {
  method: string;
  origin: string | null;
  appOrigin: string;
  csrfHeader: string | null;
  sessionCsrf: string;
};

/**
 * Cookie-authenticated mutations need the session's CSRF token in a header (which a cross-site form cannot set)
 * and, when the browser sends one, a same-origin Origin header.
 */
export function isAllowedMutation({
  method,
  origin,
  appOrigin,
  csrfHeader,
  sessionCsrf,
}: MutationCheck): boolean {
  if (SAFE_METHODS.has(method)) return true;
  if (origin !== null && origin !== appOrigin) return false;
  return csrfHeader !== null && csrfHeader.length > 0 && csrfHeader === sessionCsrf;
}

/** Path segments are re-encoded so the forwarded URL can only address the API's own routes. */
export function apiPath(segments: string[]): string | null {
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    return null;
  }
  return `/api/v1/${segments.map(encodeURIComponent).join("/")}`;
}

import type { ErrorEvent } from "@sentry/nextjs";

const SCRUBBED_HEADERS = new Set(["authorization", "cookie", "set-cookie", "x-csrf-token"]);

/** Drops credentials and personal data before an event leaves the server (§14), mirroring the API. */
export function scrubEvent(event: ErrorEvent): ErrorEvent {
  if (event.request) {
    delete event.request.cookies;
    delete event.request.data;
    delete event.request.query_string;
    if (event.request.headers) {
      event.request.headers = Object.fromEntries(
        Object.entries(event.request.headers).filter(
          ([name]) => !SCRUBBED_HEADERS.has(name.toLowerCase()),
        ),
      );
    }
  }
  if (event.user) {
    event.user = event.user.id === undefined ? {} : { id: event.user.id };
  }
  return event;
}

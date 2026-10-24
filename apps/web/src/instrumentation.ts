import type { Instrumentation } from "next";

/*
 * Server-side error reporting. Sentry loads only when SENTRY_DSN is set, so local stacks without a DSN
 * do not load it at all. Browser-side reporting is planned for pilot hardening (DECISIONS D-025).
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs" || !process.env.SENTRY_DSN) return;
  const [Sentry, { scrubEvent }] = await Promise.all([
    import("@sentry/nextjs"),
    import("@/lib/observability"),
  ]);
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    environment: process.env.APP_ENV ?? process.env.NODE_ENV,
    // Collect no personal data at the source; scrubEvent is a second line of defence (§14).
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpBodies: [],
      urlQueryParams: false,
      httpHeaders: {
        request: { deny: ["authorization", "cookie", "x-csrf-token"] },
        response: false,
      },
    },
    tracesSampleRate: 0.1,
    beforeSend: scrubEvent,
  });
}

export const onRequestError: Instrumentation.onRequestError = async (...args) => {
  if (!process.env.SENTRY_DSN) return;
  const Sentry = await import("@sentry/nextjs");
  Sentry.captureRequestError(...args);
};

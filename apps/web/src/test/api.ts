import { vi } from "vitest";

export const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Answers each request by its method and path; an unexpected one fails the test loudly. */
export function serve(routes: Record<string, (request: Request) => Response>): void {
  fetchMock.mockImplementation(async (request) => {
    const key = `${request.method} ${new URL(request.url).pathname}`;
    const route = routes[key];
    if (!route) throw new Error(`Unexpected request: ${key}`);
    return route(request);
  });
}

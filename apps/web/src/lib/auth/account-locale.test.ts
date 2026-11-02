import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { accountLocale } from "./account-locale";

beforeAll(() => {
  process.env.API_INTERNAL_URL = "http://api:8000";
});

afterEach(() => vi.unstubAllGlobals());

function answer(response: Response | Error) {
  const fetchMock = vi.fn(async () => {
    if (response instanceof Error) throw response;
    return response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("accountLocale", () => {
  it("asks /me with the access token and returns the saved language", async () => {
    const fetchMock = answer(Response.json({ locale: "en", display_name: "Aysel Məmmədova" }));
    expect(await accountLocale("token-1")).toBe("en");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.pathname).toBe("/api/v1/me");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-1");
    expect(init.cache).toBe("no-store");
  });

  it.each([
    ["an account that never chose", Response.json({ locale: null })],
    ["a language the app does not have", Response.json({ locale: "fr" })],
    ["a refused request", new Response(null, { status: 401 })],
    ["an answer that is not JSON", new Response("<html>", { status: 200 })],
    ["a network failure", new TypeError("fetch failed")],
    ["a timeout", new DOMException("timed out", "TimeoutError")],
  ])("is null for %s, and never throws", async (_name, response) => {
    answer(response);
    expect(await accountLocale("token-1")).toBeNull();
  });
});

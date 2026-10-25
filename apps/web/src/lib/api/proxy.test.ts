import { describe, expect, it } from "vitest";

import { apiPath, isAllowedMutation } from "./proxy";

const base = {
  appOrigin: "http://localhost",
  sessionCsrf: "csrf-0123",
};

describe("isAllowedMutation", () => {
  it("lets reads through without a token", () => {
    expect(
      isAllowedMutation({
        ...base,
        method: "GET",
        origin: "https://evil.example",
        csrfHeader: null,
      }),
    ).toBe(true);
  });

  it("requires the session's CSRF token on mutations", () => {
    const post = { ...base, method: "POST", origin: "http://localhost" };
    expect(isAllowedMutation({ ...post, csrfHeader: "csrf-0123" })).toBe(true);
    expect(isAllowedMutation({ ...post, csrfHeader: "csrf-9999" })).toBe(false);
    expect(isAllowedMutation({ ...post, csrfHeader: null })).toBe(false);
    expect(isAllowedMutation({ ...post, csrfHeader: "", sessionCsrf: "" })).toBe(false);
  });

  it("refuses cross-site origins even with a token", () => {
    expect(
      isAllowedMutation({
        ...base,
        method: "DELETE",
        origin: "https://evil.example",
        csrfHeader: "csrf-0123",
      }),
    ).toBe(false);
    // Some clients send no Origin on same-origin requests; the token alone is then enough.
    expect(
      isAllowedMutation({ ...base, method: "PATCH", origin: null, csrfHeader: "csrf-0123" }),
    ).toBe(true);
  });
});

describe("apiPath", () => {
  it("re-encodes segments", () => {
    expect(apiPath(["admin", "imports", "01a1"])).toBe("/api/v1/admin/imports/01a1");
    expect(apiPath(["users", "a b", "photo?v=1"])).toBe("/api/v1/users/a%20b/photo%3Fv%3D1");
  });

  it("refuses dot segments that would leave the API prefix", () => {
    expect(apiPath(["..", "healthz"])).toBeNull();
    expect(apiPath(["me", "."])).toBeNull();
    expect(apiPath(["me", ""])).toBeNull();
  });
});

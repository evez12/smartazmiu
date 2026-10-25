import { describe, expect, it } from "vitest";

import { isActive, visibleNavigation } from "./nav";

describe("visibleNavigation", () => {
  it("hides sections the user has no permission for", () => {
    expect(visibleNavigation([]).map((section) => section.labelKey)).toEqual(["main"]);
  });

  it("shows the admin section to importers", () => {
    const sections = visibleNavigation(["academics.import"]);
    expect(sections.map((section) => section.labelKey)).toEqual(["main", "admin"]);
    expect(sections[1]?.items.map((item) => item.href)).toEqual(["/admin/imports"]);
  });

  it("lists every admin entry for administrators", () => {
    const sections = visibleNavigation([
      "academics.import",
      "admin.users.read",
      "admin.audit.read",
    ]);
    expect(sections[1]?.items.map((item) => item.href)).toEqual([
      "/admin/users",
      "/admin/imports",
      "/admin/audit",
    ]);
  });
});

describe("isActive", () => {
  it("matches the section and its sub-pages", () => {
    expect(isActive("/admin/imports/01a1", "/admin/imports")).toBe(true);
    expect(isActive("/admin/importsx", "/admin/imports")).toBe(false);
    expect(isActive("/admin/imports", "/")).toBe(false);
  });
});

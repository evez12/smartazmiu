import { describe, expect, it } from "vitest";

import { negotiateLocale, resolveLocale } from "./resolve";

describe("negotiateLocale", () => {
  it.each([
    [null, null],
    ["", null],
    ["ru-RU,ru;q=0.9,en;q=0.8", "ru"],
    ["en-GB,en;q=0.9", "en"],
    ["de-DE,de;q=0.9", null],
    ["ru;q=0.5,en;q=0.9", "en"],
    ["az-AZ", "az"],
    ["ru;q=0", null],
    ["EN", "en"],
  ])("%s -> %s", (header, expected) => {
    expect(negotiateLocale(header)).toBe(expected);
  });
});

describe("resolveLocale", () => {
  it("prefers the cookie, then Accept-Language, then Azerbaijani", () => {
    expect(resolveLocale("ru", "en")).toBe("ru");
    expect(resolveLocale(undefined, "en-US,en;q=0.9")).toBe("en");
    expect(resolveLocale("de", "ru")).toBe("ru");
    expect(resolveLocale(undefined, "fr")).toBe("az");
    expect(resolveLocale(undefined, null)).toBe("az");
  });
});

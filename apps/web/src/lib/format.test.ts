import { describe, expect, it } from "vitest";

import {
  formatDate,
  formatDateTime,
  formatDayMonth,
  formatNumber,
  formatWeekdayDate,
} from "./format";

describe("formatting", () => {
  it("writes dates like 24 Oktyabr 2026 in Baku time", () => {
    expect(formatDate("2026-10-24T10:30:00Z")).toBe("24 Oktyabr 2026");
    // 21:30 UTC is already the next day in Baku (UTC+4).
    expect(formatDateTime("2026-10-24T21:30:00Z")).toBe("25 Oktyabr 2026, 01:30");
    expect(formatDate("2027-02-22T00:00:00Z")).toBe("22 Fevral 2027");
  });

  it("writes month and weekday names itself, so browsers without Azerbaijani data agree", () => {
    expect(formatDate("2027-06-01T08:00:00Z")).toBe("1 İyun 2027");
    expect(formatDateTime("2026-12-31T20:00:00Z")).toBe("1 Yanvar 2027, 00:00");
    expect(formatDayMonth("2026-11-09")).toBe("9 Noyabr");
    expect(formatWeekdayDate("2026-10-26")).toBe("Bazar ertəsi, 26 Oktyabr");
    expect(formatWeekdayDate("2026-11-01")).toBe("Bazar, 1 Noyabr");
  });

  it("uses Azerbaijani number grouping", () => {
    expect(formatNumber(20000)).toBe("20.000");
  });

  it("writes the same instant in English and Russian, day first, in Baku time", () => {
    expect(formatDate("2026-10-24T10:30:00Z", "en")).toBe("24 October 2026");
    expect(formatDate("2026-10-24T10:30:00Z", "ru")).toBe("24 октября 2026 г.");
    expect(formatDateTime("2026-10-24T21:30:00Z", "ru")).toBe("25 октября 2026 г., 01:30");
    expect(formatDayMonth("2026-11-09", "ru")).toBe("9 ноября");
    expect(formatWeekdayDate("2026-10-26", "en")).toBe("Monday, 26 October");
    expect(formatWeekdayDate("2026-11-01", "ru")).toBe("Воскресенье, 1 ноября");
  });

  it("starts the week on Monday in every language", () => {
    for (const locale of ["az", "en", "ru"] as const) {
      expect(formatWeekdayDate("2026-10-26", locale).split(",")[0]).toBe(
        { az: "Bazar ertəsi", en: "Monday", ru: "Понедельник" }[locale],
      );
    }
  });

  it("groups numbers per language", () => {
    expect(formatNumber(20000, "en")).toBe("20,000");
    expect(formatNumber(1234.5, "ru")).toMatch(/^1\s234,5$/);
  });
});

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
});

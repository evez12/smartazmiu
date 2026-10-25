import { describe, expect, it } from "vitest";

import { formatDate, formatDateTime, formatNumber } from "./format";

describe("formatting", () => {
  it("writes dates like 24 Oktyabr 2026 in Baku time", () => {
    expect(formatDate("2026-10-24T10:30:00Z")).toBe("24 Oktyabr 2026");
    // 21:30 UTC is already the next day in Baku (UTC+4).
    expect(formatDateTime("2026-10-24T21:30:00Z")).toBe("25 Oktyabr 2026, 01:30");
    expect(formatDate("2027-02-22T00:00:00Z")).toBe("22 Fevral 2027");
  });

  it("uses Azerbaijani number grouping", () => {
    expect(formatNumber(20000)).toBe("20.000");
  });
});

import { describe, expect, it } from "vitest";

import { displayStatus, IMPORT_KINDS, issueReport, type ImportKind, type ImportOut } from "./model";

const record: ImportOut = {
  id: "01a1",
  kind: "students",
  status: "ready",
  file_name: "telebeler.csv",
  encoding: "utf-8",
  row_count: 22,
  summary: { created: 22, updated: 0, unchanged: 0 },
  error_count: 0,
  created_at: "2026-10-24T10:00:00Z",
  created_by: null,
  applied_at: null,
  applied_by: null,
  expires_at: "2026-10-25T10:00:00Z",
};

describe("displayStatus", () => {
  it("marks ready previews past their expiry", () => {
    expect(displayStatus(record, new Date("2026-10-25T09:59:59Z"))).toBe("ready");
    expect(displayStatus(record, new Date("2026-10-25T10:00:00Z"))).toBe("expired");
    expect(displayStatus({ ...record, status: "applied", expires_at: null })).toBe("applied");
  });
});

describe("IMPORT_KINDS", () => {
  it("lists every kind exactly once", () => {
    const complete: Record<ImportKind, true> = {
      faculties: true,
      specialties: true,
      subjects: true,
      semesters: true,
      teachers: true,
      groups: true,
      students: true,
      offerings: true,
      enrollments: true,
    };
    expect([...IMPORT_KINDS].sort()).toEqual(Object.keys(complete).sort());
  });
});

describe("issueReport", () => {
  it("writes a UTF-8 CSV that Excel opens with Azerbaijani letters intact", () => {
    const report = issueReport(
      [
        { row: null, column: "kod", code: "unknown_column" },
        { row: 4, column: "email", code: "invalid_email" },
      ],
      { row: "Sətir", column: "Sütun", problem: "Xəta", wholeFile: "Bütün fayl" },
      (code) =>
        code === "invalid_email" ? 'E-poçt "ad@x" düzgün deyil, yoxlayın' : "Naməlum sütun",
    );
    expect(report.charCodeAt(0)).toBe(0xfeff);
    expect(report.slice(1).split("\r\n")).toEqual([
      "Sətir,Sütun,Xəta",
      "Bütün fayl,kod,Naməlum sütun",
      '4,email,"E-poçt ""ad@x"" düzgün deyil, yoxlayın"',
      "",
    ]);
  });
});

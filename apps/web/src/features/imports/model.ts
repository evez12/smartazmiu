import type { components } from "@/lib/api/schema";

export type ImportKind = components["schemas"]["ImportKind"];
export type ImportOut = components["schemas"]["ImportOut"];
export type ImportDetail = components["schemas"]["ImportDetail"];
export type ImportIssue = components["schemas"]["ImportIssueOut"];
export type FileEncoding = components["schemas"]["FileEncoding"];

/** Import order: later kinds reference earlier ones (codes, university IDs). */
export const IMPORT_KINDS = [
  "faculties",
  "specialties",
  "subjects",
  "semesters",
  "teachers",
  "groups",
  "students",
  "offerings",
  "enrollments",
] as const satisfies readonly ImportKind[];

export const FILE_ENCODINGS = [
  "utf-8",
  "windows-1254",
  "windows-1251",
] as const satisfies readonly FileEncoding[];

export const IMPORT_PERMISSION = "academics.import";

export type DisplayStatus = ImportOut["status"] | "expired";

/** A ready preview past its expiry can no longer be applied; the API refuses it as well. */
export function displayStatus(record: ImportOut, now: Date = new Date()): DisplayStatus {
  if (record.status === "ready" && record.expires_at && new Date(record.expires_at) <= now) {
    return "expired";
  }
  return record.status;
}

export const STATUS_TONE = {
  ready: "info",
  invalid: "danger",
  applied: "success",
  failed: "danger",
  expired: "warning",
} as const satisfies Record<DisplayStatus, string>;

function csvCell(value: string): string {
  return /[",\r\n;]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

/**
 * Row-level error report as CSV (§6.1). Built in the browser from the issue list, with a byte-order mark so
 * Excel opens the Azerbaijani text correctly.
 */
export function issueReport(
  issues: ImportIssue[],
  labels: { row: string; column: string; problem: string; wholeFile: string },
  describe: (code: string) => string,
): string {
  const lines = [
    [labels.row, labels.column, labels.problem],
    ...issues.map((issue) => [
      issue.row === null ? labels.wholeFile : String(issue.row),
      issue.column ?? "",
      describe(issue.code),
    ]),
  ];
  return `\ufeff${lines.map((line) => line.map(csvCell).join(",")).join("\r\n")}\r\n`;
}

import { randomBytes } from "node:crypto";

import type { Page } from "@playwright/test";

import type { TestAccount } from "./auth";
import type { TestRecords } from "./database";
import { importFile } from "./imports";

export type TestStructure = { code: string; faculty: string; group: string };

/**
 * Imports a faculty, specialty and group of their own (all coded `E2E-…`) with `student` as its only member,
 * so announcements and events addressed to them reach nobody else. `records` removes them afterwards.
 */
export async function importStructure(
  page: Page,
  records: TestRecords,
  student: TestAccount,
): Promise<TestStructure> {
  const code = records.structureCodes(`E2E-${randomBytes(4).toString("hex").toUpperCase()}`);
  records.person(student.email);
  const faculty = `Tətbiqi incəsənət fakültəsi ${code}`;
  const rows = {
    faculties: `code,name_az,name_en\n${code},${faculty},Faculty of Applied Arts\n`,
    specialties: `code,faculty_code,name_az,name_en\n${code},${code},Dizayn,Design\n`,
    groups: `code,specialty_code,admission_year,language,curator_id\n${code},${code},2026,az,\n`,
    students:
      "university_id,family_name,given_name,email,group_code,status\n" +
      `${code},${student.familyName},${student.givenName},${student.email},${code},active\n`,
  };
  for (const [kind, content] of Object.entries(rows)) {
    await importFile(page, { value: kind }, { name: `${kind}-${code}.csv`, content });
  }
  return { code, faculty, group: code };
}

/** A `datetime-local` value `hours` from now, in Baku time (UTC+4, no DST). */
export function bakuInput(hours: number): string {
  return new Date(Date.now() + (hours + 4) * 3600 * 1000).toISOString().slice(0, 16);
}

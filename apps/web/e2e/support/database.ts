import { Pool } from "pg";

/*
 * Direct access to the stack's database, for test hygiene only: removing what a test imported and checking that a
 * full run leaves the sample data as it found it. The product has no delete for imported academic records, so
 * the tests cannot clean up through the UI. `make e2e` exports the connection settings from .env.
 */
let pool: Pool | undefined;

function database(): Pool {
  if (!process.env.POSTGRES_PASSWORD) {
    throw new Error("POSTGRES_* settings are missing; run the suite through `make e2e`.");
  }
  pool ??= new Pool({
    host: "127.0.0.1",
    port: Number(process.env.POSTGRES_PORT ?? 5433),
    user: process.env.POSTGRES_USER,
    password: process.env.POSTGRES_PASSWORD,
    database: process.env.POSTGRES_DB,
    max: 2,
    allowExitOnIdle: true,
  });
  return pool;
}

/** Tables filled by the sample data (`make seed`); people from the registry, not accounts created at sign-in. */
const SEED_TABLES: Record<string, string> = {
  faculties: "SELECT count(*) FROM faculties",
  specialties: "SELECT count(*) FROM specialties",
  subjects: "SELECT count(*) FROM subjects",
  semesters: "SELECT count(*) FROM semesters",
  academic_groups: "SELECT count(*) FROM academic_groups",
  "users (registry)": "SELECT count(*) FROM users WHERE university_id IS NOT NULL",
  course_offerings: "SELECT count(*) FROM course_offerings",
  course_offering_groups: "SELECT count(*) FROM course_offering_groups",
  course_offering_teachers: "SELECT count(*) FROM course_offering_teachers",
  enrollments: "SELECT count(*) FROM enrollments",
  buildings: "SELECT count(*) FROM buildings",
  floors: "SELECT count(*) FROM floors",
  rooms: "SELECT count(*) FROM rooms",
  week_parity_overrides: "SELECT count(*) FROM week_parity_overrides",
  schedule_entries: "SELECT count(*) FROM schedule_entries",
  schedule_entry_groups: "SELECT count(*) FROM schedule_entry_groups",
  schedule_changes: "SELECT count(*) FROM schedule_changes",
};

export type RowCounts = Record<string, number>;

export async function seedRowCounts(): Promise<RowCounts> {
  const counts: RowCounts = {};
  for (const [table, query] of Object.entries(SEED_TABLES)) {
    const { rows } = await database().query<{ count: string }>(query);
    counts[table] = Number(rows[0]!.count);
  }
  return counts;
}

/** Every table whose count differs, as `table: before → after`. */
export function countDifferences(before: RowCounts, after: RowCounts): string[] {
  return Object.keys(before)
    .filter((table) => before[table] !== after[table])
    .map((table) => `${table}: ${before[table]} → ${after[table]}`);
}

/**
 * Records a test imported for itself, removed when the test ends (also on failure or timeout). Only rows marked
 * as test data are touched: offerings coded `E2E-…` and people with an `e2e-…` address.
 */
export class TestRecords {
  private readonly offerings: string[] = [];
  private readonly people: string[] = [];

  /** An offering (with its enrollments and timetable) the test is about to import. */
  offering(code: string): string {
    if (!code.startsWith("E2E-")) throw new Error(`Not a test offering code: ${code}`);
    this.offerings.push(code);
    return code;
  }

  /** A throwaway account the test is about to import into the registry (as a student of a group). */
  person(email: string): string {
    if (!email.startsWith("e2e-")) throw new Error(`Not a test account: ${email}`);
    this.people.push(email);
    return email;
  }

  async removeAll(): Promise<void> {
    if (!this.offerings.length && !this.people.length) return;
    const client = await database().connect();
    try {
      await client.query("BEGIN");
      const offerings = "SELECT id FROM course_offerings WHERE code = ANY($1)";
      await client.query(`DELETE FROM enrollments WHERE course_offering_id IN (${offerings})`, [
        this.offerings,
      ]);
      // Groups, teachers and timetable entries (with their changes) cascade from the offering.
      await client.query("DELETE FROM course_offerings WHERE code = ANY($1)", [this.offerings]);
      // The account row stays like every mirrored e2e- account (D-040); it leaves the registry and its group.
      await client.query(
        `UPDATE users SET university_id = NULL, academic_group_id = NULL, person_type = NULL
         WHERE email = ANY($1)`,
        [this.people],
      );
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
      this.offerings.length = 0;
      this.people.length = 0;
    }
  }
}

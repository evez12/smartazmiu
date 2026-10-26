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
  // Channels derived from the registry (provisioning, D-061); DMs and messages are test data, not seed.
  "channels (registry)": "SELECT count(*) FROM channels WHERE type <> 'dm'",
  channel_topics: "SELECT count(*) FROM channel_topics",
  "channel_members (registry)":
    "SELECT count(*) FROM channel_members m JOIN channels c ON c.id = m.channel_id WHERE c.type <> 'dm'",
  // Not seed data, but rows that hang off test messages without a foreign key (ADR 0002): a run that leaves
  // any behind has a cleanup gap (D-067).
  message_reactions: "SELECT count(*) FROM message_reactions",
  message_mentions: "SELECT count(*) FROM message_mentions",
  "notifications (chat)": "SELECT count(*) FROM notifications WHERE category = 'chat'",
  "message_attachments (sent)":
    "SELECT count(*) FROM message_attachments WHERE message_id IS NOT NULL",
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
 * Records a test created for itself, removed when the test ends (also on failure or timeout). Only rows marked
 * as test data are touched: codes starting with `E2E-`, people with an `e2e-…` address, and the events and
 * announcements whose ids the test registered.
 */
export class TestRecords {
  private readonly structure = {
    faculties: [] as string[],
    specialties: [] as string[],
    groups: [] as string[],
  };
  private readonly offerings: string[] = [];
  private readonly people: string[] = [];
  private readonly published = { events: [] as string[], announcements: [] as string[] };
  private readonly chat = { markers: [] as string[], people: [] as string[] };
  private readonly mailboxes: string[] = [];

  /** A faculty, specialty and group (one of each, all coded `code`) the test is about to import. */
  structureCodes(code: string): string {
    testCode(code);
    this.structure.faculties.push(code);
    this.structure.specialties.push(code);
    this.structure.groups.push(code);
    return code;
  }

  /** An offering (with its enrollments and timetable) the test is about to import. */
  offering(code: string): string {
    this.offerings.push(testCode(code));
    return code;
  }

  /** A throwaway account the test is about to import into the registry (as a student of a group). */
  person(email: string): string {
    if (!email.startsWith("e2e-")) throw new Error(`Not a test account: ${email}`);
    this.people.push(email);
    this.mailboxes.push(email);
    return email;
  }

  /**
   * Chat written by seeded accounts: messages containing `marker`, the direct messages among `people` (e-mail
   * addresses) and their read markers. Seeded people may write messages; nothing else about them changes.
   */
  chatMessages(marker: string, people: string[]): string {
    if (marker.length < 8) throw new Error(`Marker too short to be unique: ${marker}`);
    this.chat.markers.push(marker);
    this.chat.people.push(...people);
    return marker;
  }

  event(id: string): void {
    this.published.events.push(id);
  }

  announcement(id: string): void {
    this.published.announcements.push(id);
  }

  async removeAll(): Promise<void> {
    await removeMail(this.mailboxes.splice(0));
    const client = await database().connect();
    try {
      await client.query("BEGIN");
      const markers = this.chat.markers.map((marker) => `%${marker}%`);
      // Replies are removed with their thread root, whatever their own text.
      const written =
        "SELECT id FROM messages WHERE body LIKE ANY($1) OR parent_id IN (SELECT id FROM messages WHERE body LIKE ANY($1))";
      for (const table of ["message_client_ids", "message_reactions", "message_mentions"]) {
        await client.query(`DELETE FROM ${table} WHERE message_id IN (${written})`, [markers]);
      }
      // Files become abandoned uploads, which the worker purges with their objects (D-068).
      await client.query(
        `UPDATE message_attachments SET message_id = NULL, created_at = now() - interval '2 days' WHERE message_id IN (${written})`,
        [markers],
      );
      await client.query(
        `DELETE FROM notifications WHERE kind = 'chat.attachment_rejected' AND subject_id IN (SELECT id FROM message_attachments WHERE message_id IS NULL AND created_at < now() - interval '1 day')`,
      );
      // Chat notifications carry the message id as a UUID (D-067).
      await client.query(
        `DELETE FROM notifications WHERE category = 'chat' AND subject_id IN (SELECT lpad(to_hex(id), 32, '0')::uuid FROM (${written}) AS m)`,
        [markers],
      );
      await client.query(`DELETE FROM messages WHERE id IN (${written})`, [markers]);
      const people = "SELECT id FROM users WHERE email = ANY($1)";
      // Topics, members, read markers and the rest of their messages cascade from the channel.
      await client.query(
        `DELETE FROM channels WHERE type = 'dm' AND user_low_id IN (${people}) AND user_high_id IN (${people})`,
        [this.chat.people],
      );
      await client.query(`DELETE FROM channel_reads WHERE user_id IN (${people})`, [
        this.chat.people,
      ]);
      const subjects = [...this.published.events, ...this.published.announcements];
      // Notifications point at their subject without a foreign key; recipients and RSVPs cascade.
      await client.query("DELETE FROM notifications WHERE subject_id = ANY($1::uuid[])", [
        subjects,
      ]);
      await client.query("DELETE FROM events WHERE id = ANY($1::uuid[])", [this.published.events]);
      await client.query("DELETE FROM announcements WHERE id = ANY($1::uuid[])", [
        this.published.announcements,
      ]);
      const offerings = "SELECT id FROM course_offerings WHERE code = ANY($1)";
      // Channels provisioned for test records go first: they refer to the offering, group or faculty, and
      // their topics, members and messages cascade.
      await client.query(
        `DELETE FROM channels WHERE course_offering_id IN (${offerings})
           OR academic_group_id IN (SELECT id FROM academic_groups WHERE code = ANY($2))
           OR faculty_id IN (SELECT id FROM faculties WHERE code = ANY($3))`,
        [this.offerings, this.structure.groups, this.structure.faculties],
      );
      // Memberships of people leaving the registry; the provisioning job would remove them within a minute.
      await client.query(
        `DELETE FROM channel_members WHERE user_id IN (SELECT id FROM users WHERE email = ANY($1))
           AND channel_id IN (SELECT id FROM channels WHERE type <> 'dm')`,
        [this.people],
      );
      await client.query(`DELETE FROM enrollments WHERE course_offering_id IN (${offerings})`, [
        this.offerings,
      ]);
      // Groups, teachers and timetable entries (with their changes) cascade from the offering.
      await client.query("DELETE FROM course_offerings WHERE code = ANY($1)", [this.offerings]);
      // The account row stays like every mirrored e2e- account (D-040, D-046); it leaves the registry.
      await client.query(
        `UPDATE users SET university_id = NULL, academic_group_id = NULL, person_type = NULL
         WHERE email = ANY($1)`,
        [this.people],
      );
      await client.query("DELETE FROM academic_groups WHERE code = ANY($1)", [
        this.structure.groups,
      ]);
      await client.query("DELETE FROM specialties WHERE code = ANY($1)", [
        this.structure.specialties,
      ]);
      await client.query("DELETE FROM faculties WHERE code = ANY($1)", [this.structure.faculties]);
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
      for (const list of [
        this.offerings,
        this.people,
        this.structure.faculties,
        this.structure.specialties,
        this.structure.groups,
        this.published.events,
        this.published.announcements,
        this.chat.markers,
        this.chat.people,
      ]) {
        list.length = 0;
      }
    }
  }
}

function testCode(code: string): string {
  if (!code.startsWith("E2E-")) throw new Error(`Not a test code: ${code}`);
  return code;
}

const mailpitUrl = `http://localhost:${process.env.MAILPIT_UI_PORT ?? 8025}`;

type MailSummary = { ID: string; Subject: string; To: { Address: string }[] };

/** Messages Mailpit caught for an address (newest first). */
export async function mailFor(address: string): Promise<MailSummary[]> {
  const response = await fetch(
    `${mailpitUrl}/api/v1/search?query=${encodeURIComponent(`to:"${address}"`)}`,
  );
  if (!response.ok) throw new Error(`Mailpit search failed: ${response.status}`);
  return ((await response.json()) as { messages: MailSummary[] }).messages;
}

export async function mailText(id: string): Promise<string> {
  const response = await fetch(`${mailpitUrl}/api/v1/message/${id}`);
  return ((await response.json()) as { Text: string }).Text;
}

async function removeMail(addresses: string[]): Promise<void> {
  const ids = (await Promise.all(addresses.map(mailFor))).flat().map((message) => message.ID);
  if (!ids.length) return;
  await fetch(`${mailpitUrl}/api/v1/messages`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ IDs: ids }),
  });
}

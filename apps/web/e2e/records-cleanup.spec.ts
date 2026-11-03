import { randomBytes } from "node:crypto";

import { expect, test } from "@playwright/test";
import { Pool } from "pg";

import { TestRecords } from "./support/database";

/*
 * D-045, D-134: the records a test created are removed also when the other services they touch fail. `removeAll`
 * calls Mailpit and Redis before it cleans the database; a reset on either call used to skip the database part and
 * leave the records behind. Here both calls fail on purpose and the database part must still run, with the other
 * failures reported after it. Needs the stack's database only.
 */
const SEEDED_STUDENT = "aysel.mammadova@smartazmiu.test";

function pool(): Pool {
  return new Pool({
    host: "127.0.0.1",
    port: Number(process.env.POSTGRES_PORT ?? 5433),
    user: process.env.POSTGRES_USER,
    password: process.env.POSTGRES_PASSWORD,
    database: process.env.POSTGRES_DB,
    max: 1,
  });
}

test.skip(!process.env.POSTGRES_PASSWORD, "needs the stack's database settings (.env)");

test("a failing Mailpit or Redis call does not skip the database cleanup, and is reported afterwards", async () => {
  const marker = `cleanup-${randomBytes(6).toString("hex")}`;
  const db = pool();
  const saved = { mailpit: process.env.MAILPIT_UI_PORT, redis: process.env.REDIS_URL };
  try {
    await db.query(
      "INSERT INTO feedback (id, category, message) VALUES (gen_random_uuid(), 'other', $1)",
      [`Silinməli qeyd ${marker}`],
    );
    const count = async () =>
      Number(
        (await db.query("SELECT count(*) FROM feedback WHERE message LIKE $1", [`%${marker}%`]))
          .rows[0].count,
      );
    expect(await count()).toBe(1);

    const records = new TestRecords();
    records.feedback(marker);
    // A mailbox to empty (Mailpit) and a rate limit to reset (Redis) make the two other services part of the cleanup.
    records.person(`e2e-${marker}@smartazmiu.test`);
    records.rateLimit("report_create", [SEEDED_STUDENT]);

    process.env.MAILPIT_UI_PORT = "1"; // nothing listens there: the connection is refused
    process.env.REDIS_URL = "not a url"; // the client cannot even be created
    const failure = await records.removeAll().then(
      () => null,
      (error: unknown) => error,
    );

    expect(await count(), "the database part ran although the other steps failed").toBe(0);
    expect(failure).toBeInstanceOf(AggregateError);
    expect((failure as AggregateError).message).toContain("cleanup outside the database failed");
    expect((failure as AggregateError).errors).toHaveLength(2);
  } finally {
    for (const [name, value] of [
      ["MAILPIT_UI_PORT", saved.mailpit],
      ["REDIS_URL", saved.redis],
    ] as const) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
    await db.query("DELETE FROM feedback WHERE message LIKE $1", [`%${marker}%`]);
    await db.end();
  }
});

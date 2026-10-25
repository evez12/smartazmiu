# ADR 0002 — Messages: monthly partitions and snowflake ids

- Status: accepted (2026-10-26) with the product owner's changes (lease timing, idempotency registry)
- Related: §5.3, §5.7 (partitioning note), §5.9 (ordering), §13.2 (duplicate send, snowflake restart); DECISIONS
  D-006, D-053, D-056, D-058

## Context

`messages` is the largest and fastest-growing table: every course, community, group and DM channel writes to it,
history is read newest-first with `before`/`after` cursors, and archived course channels are exported and deleted
after two years (§5.4). §5.7 asks for monthly partitions with `PRIMARY KEY (id, created_at)` and snowflake ids that
double as the cursor and the ordering key. PostgreSQL requires the partition key in every unique constraint and
does not allow foreign keys that reference a partitioned table by `id` alone.

## Decision

### Snowflake ids

- 63 usable bits of a signed `BIGINT` (always positive): **41 bits** milliseconds since the custom epoch
  `2026-01-01T00:00:00Z` (about 69 years), **10 bits** worker id (1,024 concurrent generators), **12 bits**
  sequence (4,096 ids per millisecond per worker).
- Serialised as strings in JSON (§4.2). Clients order by id, never by arrival (§5.9).
- **Worker ids are leased** (D-006) from Redis instance A, which never evicts (D-053): `SET snowflake:worker:<n>
  <process uuid> NX EX 60`, starting at a random `n` and probing upward. Every process that issues message ids
  (each API process; an ARQ worker only once it writes messages, D-060) leases its own id at start-up and
  renews it every 20 s with a compare-and-set script (renew only if the value is still ours).
- **The TTL (60 s) is three renewal intervals (20 s)**, so a Redis A outage of up to about 40 s (two missed
  renewals) does not stop id generation: the lease is still ours when Redis returns and the next renewal succeeds.
- **A lease that cannot be confirmed stops the generator**: each id checks that the last successful renewal is
  younger than 50 s (monotonic clock), which leaves a 10 s margin before the TTL could expire. If not, or if a
  renewal finds the key gone or held by another process, generating fails with a typed error (`chat.unavailable`,
  the client retries) until a lease is held again. A process that was paused longer than the TTL therefore cannot
  collide with the process that took over its worker id.
- **Clock regression**: the generator keeps the last millisecond it used. If the wall clock steps back by up to
  10 ms it waits until it catches up; beyond that it refuses to issue ids (`chat.unavailable`), logs an error and
  reports to Sentry, rather than risk an id that sorts before an earlier message. Sequence exhaustion within one
  millisecond waits for the next millisecond.
- The primary key remains the last line of defence: a duplicate id fails the insert, which is retried once with a
  fresh id.

### Partitioned table

- `messages` is `PARTITION BY RANGE (created_at)` with `PRIMARY KEY (id, created_at)`.
- **`created_at` is derived from the id** (`epoch + (id >> 22) ms`), never taken from `now()` separately. Any
  query that knows an id therefore knows its partition: cursor queries add `created_at <= created_at_of(before)`
  (or `>=` for `after`) so the planner prunes partitions, and single-message lookups by id use the exact
  `created_at`.
- **Monthly partitions** named `messages_yYYYYmMM`, created by the migration for the current month and the next
  three, and by an ARQ cron job (daily, idempotent `CREATE TABLE IF NOT EXISTS … PARTITION OF … FOR VALUES FROM …
  TO …`) that always keeps three future months. **No default partition**: rows in a default partition would block
  attaching the matching month later. A missing partition makes inserts fail with `chat.unavailable`; the cron job
  logs a warning when fewer than two future months exist, and `/readyz` reports degraded when the current month is
  missing.
- Indexes are declared on the parent (one per partition): `(channel_id, id DESC)` for history, `(parent_id)` for
  threads, and GIN on `body_tsv`. *(Amended 2026-10-26, D-060: `body_tsv` and its index exist from Sprint 5 and
  are written with every message from both `normalize_az` forms; only the search endpoints wait for Sprint 10.)*
- Outgoing foreign keys (`channel_id → channels`, `author_id → users`) stay; partitioned tables support them.
  Tables that refer to messages (`message_attachments`, `message_reactions`, `message_mentions`,
  `pinned_messages`, `saved_messages`) store `message_id` (plus `message_created_at` where they need to reach the
  row) without a foreign key; the service layer checks existence, and a weekly ARQ consistency job deletes orphans
  and reports their count. *(D-060: the job ships in Sprint 6 together with the first code that writes such
  rows; in Sprint 5 these tables are schema only and nothing can be orphaned.)*

### Idempotent sends

- §5.7's `UNIQUE (channel_id, client_msg_id)` cannot exist on the partitioned table without `created_at`, which
  would make it useless (a retry has a new time). Instead an unpartitioned lookup table
  `message_client_ids(channel_id, client_msg_id, message_id, message_created_at, created_at,
  PRIMARY KEY (channel_id, client_msg_id))` maps a client id to its message. The send first claims the client id
  with `INSERT … ON CONFLICT DO NOTHING` and inserts the message in the same transaction; when the claim finds a
  row, the send returns the original message and the same `ack` (§13.2). Two concurrent sends of one
  `client_msg_id` therefore produce exactly one message: the second waits on the first's uncommitted key and then
  sees it.
- Entries are kept seven days and purged by an idempotent daily ARQ job. The reconnect backfill window (§5.9) is
  capped below that (three days), so a client never retries a send older than the registry remembers; an offline
  queue older than that is resent as new messages only after the user confirms.

### Retention

- Archived course channels are exported and deleted after two years (§5.4) by deleting their rows; partitions are
  dropped only when they are empty. Dropping whole months is not possible because DMs live until account deletion.

## Consequences

- History, cursors and backfill touch one or two partitions in the common case; old months stay cold.
- Redis instance A becomes a hard dependency for sending messages (not for reading). If it is unreachable for more
  than about 50 s, sends fail with a typed error while reads continue.
- Every partition-aware query must go through the helper that adds the `created_at` bound; a unit test checks the
  plans of the history queries for partition pruning.
- Tests: uniqueness across 4 generators × 50,000 ids, sequence overflow, clock regression of 5 ms (waits) and 1 s
  (refuses), a short Redis outage (keeps issuing), lease loss (refuses), partition job idempotency, insert into a
  missing month (typed error), two concurrent sends of one `client_msg_id` (one message, the same ack), purge job
  idempotency.

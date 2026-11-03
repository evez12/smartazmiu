# ADR 0005 — Account deletion

- Status: proposed (2026-11-03), not accepted. Nothing in this document is implemented; no code, migration or
  setting changes with it.
- Related: §5.4 (retention, compliance), §13.2 ("Account deleted"), §14; DECISIONS D-038, D-040, D-046, D-062, D-091,
  D-093, D-108, D-112, D-113, D-126
- Planned as the first Phase 4 item. Phase 4 has not started.

## Context

§5.4 promises account deletion under the Azerbaijan Law "On Personal Data", next to consent records and the data
export. Every sprint so far deferred it and recorded what it would have to do. This document collects those
requirements in one place so the build starts from a complete list, and ends with the decisions only the product owner
can make. Account deletion touches personal data, authentication and hard deletion, all of which are ask-first.

### Requirements already recorded

| Source | Requirement |
|---|---|
| §5.4 | DMs are kept until the user deletes the account: soft delete, then a 30-day purge. Consent records and the export (`GET /me/export`) exist; deletion is the remaining right. |
| §13.2 | Messages stay with the author shown as "Silinmiş istifadəçi"; personal data is scrubbed; DMs follow §5.4. |
| D-046 | The leftover `e2e-…` rows (inactive mirror rows of throwaway accounts, D-040) are purged through this feature's purge path, not by a script. |
| D-038, D-040 | Audit entries of deleted accounts exist already (`actor_id` is `SET NULL`); sign-out deletes the Redis session; E2E accounts are removed in Keycloak by the tests. |
| D-062 | Blocks must never become inferable; deleting a blocked or blocking account must not reveal that a block existed. |
| D-091 | Feed posts and comments and forum questions and answers keep their text with no author; today their foreign keys cascade, so the text would disappear. |
| D-093 | Assignment submissions, their files and quiz attempts of the deleted person need a decision; today their foreign keys cascade. |
| D-108, D-112 | Attendance records and past papers are anonymized: the rows stay, the user reference becomes NULL (done in migration 0036), the interface shows "Silinmiş istifadəçi". Titles and notes the person wrote on past papers are cleared if they name the person. |
| D-113 | `users.locale` is part of the export; it is personal data and goes with the row. |
| D-126 | The cabinet mirror (grades, transcript, appeals) is per person; the next sync would recreate it unless the person is no longer an active student. |

### What the schema does today

A query of the development database lists every foreign key that points at `users` (82 of them, partitions left out):

- **`ON DELETE SET NULL` (41 columns):** `messages.author_id`, `message_attachments.uploader_id`, the
  `reports`, `material_reports`, `feedback` reporter and sender columns, `attendance_records.student_id`,
  `attendance_sessions.opened_by`, `past_papers.uploader_id`, `material_versions.uploader_id`, `audit_logs.actor_id`,
  `moderation_actions.target_user_id` and `moderator_id`, and every "created_by / handled_by / reviewed_by" column.
  Deleting the user already anonymizes these rows without a migration.
- **`ON DELETE CASCADE` (37 columns) and personal by nature (deleted with the account):** `user_roles`, `consent_records`, `notifications`,
  `push_subscriptions`, `notification_preferences`, `notification_quiet_hours`, `announcement_recipients`,
  `event_recipients`, `event_registrations`, `channel_members`, `channel_reads`, `saved_messages`, `message_reactions`,
  `message_mentions`, `poll_votes`, `user_blocks` (both sides), `mentor_profiles`, `mentor_requests` (requester),
  `channel_bans`, `global_chat_bans`, `tip_upvotes`, `helpful_reactions`, `forum_votes`, the five `cabinet_*` tables.
- **`ON DELETE CASCADE` and content others read (the problem):** `feed_posts.author_id`, `feed_comments.author_id`,
  `forum_questions.author_id`, `forum_answers.author_id`, `course_tips.author_id` (all NOT NULL),
  `assignment_submissions.student_id`, `assignment_files.student_id`, `quiz_attempts.student_id`.
- **No `ON DELETE` rule (deletion is refused today):** `course_offering_teachers.teacher_id`, `enrollments.user_id`,
  `channels.user_low_id` and `channels.user_high_id` (the two sides of a DM).
- **Not a foreign key:** objects in storage (avatars under `photo_key`, attachments, submission files, paper files),
  Redis keys (sessions, tickets, presence), Keycloak accounts, the push endpoints held by browsers, and mail already
  sent. Rows that name a message by id without a foreign key (D-056) are cleaned by the consistency job.

## Proposed design

### Two phases, because of the 30 days

1. **Request.** A signed-in person asks for deletion in their profile. The person is shown what happens, offered the
   export first (it is the same `GET /me/export`), and must re-authenticate (a fresh Keycloak login, no new cookie or
   session rules). The account becomes `status = pending_deletion`: sign-in and all sessions end at once (the Redis
   session keys are deleted), the person is hidden from search, member lists, mentions and DM creation, and new
   notifications stop. The request is reversible by signing in again within the grace period (decision 1).
2. **Purge.** An idempotent ARQ job (daily, advisory lock, like the other consistency jobs) finds accounts whose grace
   period ended and runs the purge for each in one transaction, then removes objects and the identity-provider account.
   A failed step leaves the account in `pending_deletion` and the job retries (§13.5, at-least-once).

### The purge

For one user, in order:

1. **Anonymize what others read.** Chat messages already keep a NULL author. Feed, forum and tip rows keep their text:
   `author_id` becomes nullable `SET NULL` (migration, reversible only while no NULL exists, as migration 0036 does),
   and the screens show "Silinmiş istifadəçi". Submissions, files and attempts follow decision 4.
2. **Scrub personal data.** Text the person wrote that identifies them is cleared where it is theirs alone: `bio`,
   profile photo object, mentor profile text, notification and push data, free-text fields of their own feedback and
   reports (decision 6). The `users` row keeps its id and is reduced to a tombstone (name "Silinmiş istifadəçi",
   `email`, `university_id`, `idp_subject`, `search_key`, `bio`, `photo_key`, `locale` cleared or replaced by a random
   value) so SET NULL columns do not need rewriting and the id cannot be matched to a person (decision 2).
3. **Delete personal rows.** The cascade list above, explicitly, in the same transaction, so that the job is correct
   even if a future foreign key is added with no rule (a test fails when a table that points at `users` is neither
   listed as personal nor as anonymized).
4. **DMs.** See decision 3; in either variant the soft delete comes first and the physical purge 30 days later.
5. **Objects.** Avatar, attachments and files of the person, through the existing purge job path, after the database
   transaction commits; a failure there is retried and never rolls the deletion back.
6. **Cabinet.** The mirror rows go with the cascade; the sync must not recreate them (the account is not active), and
   the audit entry for the purge holds no grade value.
7. **Identity provider.** The Keycloak account is removed through the admin API only after the database step has
   committed (decision 5). A failure is retried; the account cannot sign in meanwhile because the row is a tombstone.
8. **Audit.** One `account.deleted` entry in `audit_logs` records the time, the reason (self-service, staff, E2E
   purge) and the user id as a hash, not the name; earlier entries keep `actor_id` NULL, which is already the case.

### Who can request it

- **Self-service** for students, teachers and staff.
- **Staff** with a new permission (for example `accounts.delete`) for departed students and teachers, with a reason,
  audited. Both paths use the same purge.
- **Teachers and staff with duties** (the sole teacher of an offering, a curator of a group, the only moderator of a
  channel): the request is refused with a plain message naming what to hand over first, or the duty is released
  automatically (decision 7). `course_offering_teachers`, `enrollments` and DM channels have no `ON DELETE` rule and
  would otherwise fail the delete.
- **The `e2e-` rows** (D-046) are purged by the same job, selected by their prefix on a development stack only; the
  rule is a guard in the job and a test, and does nothing in production.

### Edge cases (§13) to test when built

The purge runs twice at once or is retried halfway; the person is a member of an active exam-mode channel; the
person has a pending upload or an unscanned file; a message of the person is quoted, replied to, pinned, saved by
someone else or reported; the person is the only teacher of an offering or the last administrator; the person is
blocked by or blocks someone (the other side must see no change, D-062); the export is requested during the
grace period; Keycloak or storage is down; the person signs in again during the grace period; the same university id
registers again afterwards (it must get a new account, not the old id); an offline-cached copy of channels on the
person's device is wiped at sign-out (D-117); the audit trail keeps no name.

## Decisions the product owner must make

1. **Grace period and reversal.** §5.4 gives 30 days for DMs only. Is the whole account recoverable for 30 days (the
   proposal: yes, sign in again cancels it), or is the account removed at once and only DM text waits 30 days?
2. **Tombstone or hard delete of the `users` row.** The proposal keeps an anonymous row so that SET NULL and historic
   audit work. Hard deletion of the row itself (after every reference is NULL) is cleaner but is irreversible and loses
   the guarantee that an id is never reused. Which?
3. **DMs.** Are the person's sent DM messages deleted for both sides after 30 days, or does the other participant keep
   them with the author shown as "Silinmiş istifadəçi" (as for channel messages)? §5.4 says "kept until the user
   deletes" and does not say what the other person keeps.
4. **Assignment submissions, files and quiz attempts (D-093).** These carry grades. Options: delete them with the
   account (current behaviour, loses the teacher's gradebook rows), or anonymize them (the teacher keeps the score, the
   student is "Silinmiş istifadəçi"), as D-108 did for attendance. Anything touching grades is yours to decide.
5. **Keycloak.** Is the identity-provider account removed by SmartAzMİU through the admin API (needs an admin
   credential for the service), or does the university's identity team remove it, with SmartAzMİU only revoking
   sessions? This is an authentication change.
6. **Scrub depth.** Which free text of the person is cleared rather than kept: their own feedback and report texts,
   past-paper titles and notes (D-108 left this open), material and forum titles, event registrations? And do
   moderation records that name the person as a target keep the id or lose it?
7. **Staff, teacher and curator duties.** Refuse deletion until duties are handed over, or release them
   automatically and notify the faculty office?
8. **Audit retention.** `audit_logs` has no retention rule in the spec. How long are entries kept, and may an entry about
   a deleted person keep a hash of the id for that time?
9. **Who may delete whom.** Self-service only, or also staff on behalf of a departed student, and who holds the new
   permission?
10. **Backups.** A deleted person remains in database backups until they expire. Is a stated backup retention (and no
    restore of a deleted account) acceptable under the Law, or is a re-deletion step after any restore required?
11. **Cabinet.** Confirm that the cabinet mirror is deleted with the account and that the registry, not SmartAzMİU, is
    the record of the person's grades (D-126).
12. **Notice.** What does the person see and receive (an e-mail at request and at completion, the exact Azerbaijani
    text, English and Russian later), and is a legal wording from the university required?

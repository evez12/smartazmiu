# SmartAzMİU — AzMİU Web Platform

> **Purpose of this file:** implementation spec + roadmap for Claude Code.
> Product owner: Avaz Huseynov · Version 2.2 · 2026-10-24
> UI language: **Azerbaijani (primary)**, EN/RU later. All code, comments, docs, commit messages: **English**.

---

## 0. How to use this document (instructions for Claude Code)

### 0.1 Operating rules

1. **Read this entire file before writing any code.** Then create `CLAUDE.md` in the repo root that summarizes §0, §3.2, §12 and §15 in under 120 lines, so the rules survive context resets. Create `docs/DECISIONS.md` (decision log, see §0.3).
2. Work **phase by phase, sprint by sprint**. Do not start a sprint until the previous sprint's acceptance criteria pass.
3. Each sprint lists tasks as checkboxes. Tick them (`- [x]`) in this file as you complete them.
4. Keep the architecture a **modular monolith** (one FastAPI app, one Next.js app). Do not introduce microservices.
5. Everything listed in **§3.2 Out of scope** must NOT be implemented, even partially (no AI endpoints, no WebRTC, no React Native/Flutter).
6. Every backend feature ships with: Alembic migration (reversible), Pydantic schemas, service layer, router, pytest tests (≥ 80% coverage for the module).
7. Every frontend feature ships with: typed API client, loading / empty / error / forbidden states, mobile layout (≥ 320 px), Azerbaijani strings in i18n files (never hard-coded), and compliance with the **UI Design Standard (§12)**.
8. Before marking a sprint done: `make lint test` passes, `docker compose up` brings the full stack up from scratch, and the demo scenario of the sprint works end-to-end.
9. Every feature must be checked against the **Edge-case catalogue (§13)** for its module. Cases that apply must have a test; cases that do not apply must be consciously skipped (note in the PR).

### 0.2 Precedence when instructions conflict

1. §3.2 Out of scope (hard prohibition)
2. §5.4 Privacy & safety and §14 Security (never weakened for convenience)
3. §12 UI Design Standard
4. Module specs (§5, §6)
5. Roadmap sprint scope (§8)

### 0.3 When the spec is silent or ambiguous

- Choose the **simplest option consistent with the rest of the spec**, implement it, and append an entry to `docs/DECISIONS.md`: `date · context · options considered · decision · consequences`.
- Stop and ask the product owner **only** if the decision is irreversible or touches: grades/personal data exposure, authentication, data deletion, or anything in §3.2.
- Never silently drop a requirement. If a requirement is impossible or conflicting, record it in `docs/DECISIONS.md` and flag it in the sprint summary.
- Do not add features that are not in this document. Do not "improve" scope.

### 0.4 Definition of Ready (before starting a task)

Entities, permissions, states, and error cases for the task are identifiable from this file. If not, resolve via §0.3 first.

---

## 1. Product summary

A single web platform (responsive + PWA) for AzMİU students, teachers and administration:

- **Academic:** schedule, video lessons, materials, assignments, quizzes, attendance, exams.
- **Campus:** events, announcements, campus map, e-requests, clubs, career.
- **Social:** **Chat (core differentiator)**, feed, Q&A forum, subject groups, reputation.

### Core differentiator: Subject Chat + Cross-Cohort Mentorship

Every subject has:
1. A **Course Channel** per offering (subject × semester × group) — current students + teacher.
2. A **Subject Community** that persists across years — current students + students who **already passed** the subject (verified "Bələdçi" / guide badge). Students taking a subject for the first time can ask people who took it last year.

### 1.1 Product principles (use these to resolve ambiguity)

1. **Zero-setup for students:** channels, memberships and schedules appear automatically from imported academic data.
2. **Academic integrity first:** nothing in the product may make cheating easier (exam mode, no grade exposure, `exam_leak` reports).
3. **Privacy by default:** the most restrictive visibility is the default; users opt in to sharing.
4. **Institutional trust:** the product must look and read like an official university service (§12), not a consumer social app.
5. **Reliability over novelty:** idempotent operations, explicit states, no silent failures.

### 1.2 Glossary

| Term | Meaning |
|---|---|
| Fənn | Subject (course) |
| Fənn icması | Subject community (persistent, cross-cohort) |
| Qrup | Academic group, e.g. `765a2` |
| İxtisas | Specialty |
| Bələdçi | Guide — a student who passed a subject and mentors others |
| Kurator | Group curator (staff/teacher assigned to a group) |
| Üst / alt həftə | Upper / lower week (alternating schedule parity) |
| Semestr | Semester: Payız (fall), Yaz (spring), Yay (summer) |
| Tədris ili | Academic year |
| Dekanlıq | Dean's office |

### 1.3 Locale & time conventions

- Time zone: **Asia/Baku (UTC+4, no DST)**. Store all timestamps as UTC `timestamptz`; render in Asia/Baku. Never store local times without zone, except schedule slots (which are wall-clock `time` + weekday by design).
- Date format in UI: `24 Oktyabr 2026`, time `14:30` (24-hour). Week starts on Monday.
- Azerbaijani alphabet: `A B C Ç D E Ə F G Ğ H X I İ J K Q L M N O Ö P R S Ş T U Ü V Y Z`. Sorting must use Azerbaijani collation (ICU `az-AZ`), not ASCII order.

---

## 2. Users & roles

| Role | Code | Notes |
|---|---|---|
| Student | `student` | Default role, linked to academic group (e.g. `765a2`) |
| Teacher | `teacher` | Can post in course channels, verify answers, upload materials |
| Dean's office / Academic staff | `staff` | Schedule, announcements, requests, data import |
| Moderator | `moderator` | Student-council members; scoped to channels/communities |
| System admin | `admin` | RBAC, audit logs, integrations |
| Guest | `guest` | Public pages only (news, programs, map) |

RBAC is permission-based (`permissions` table), roles are bundles of permissions. Channel-level roles (`owner`, `moderator`, `member`, `readonly`) are separate from global roles. A user may hold multiple global roles (e.g. `student` + `moderator`). Authorization is always checked **server-side** (REST and WebSocket).

---

## 3. Scope

### 3.1 In scope (by phase — see §8)
Authentication, profile, homepage, schedule, map, events & announcements, notifications, **chat (channels, DM, threads, mentorship, course tips, moderation)**, materials, video lessons, feed, Q&A forum, assignments, quizzes, QR attendance, exam center, GPA calculator, personal cabinet integration, PWA, i18n, reputation, e-requests/helpdesk, clubs, career center, library, analytics, office hours.

### 3.2 Out of scope — DO NOT BUILD
| Removed feature | Reason |
|---|---|
| AI assistant / chatbot | Product decision (v2.0) — may return in a later version |
| All AI features (video summaries, flashcard generation, RAG, risk prediction, AI plagiarism, AutoCAD AI review, semantic search, NLP moderation) | Product decision |
| Voice & video calls (WebRTC, LiveKit) | Product decision |
| Native mobile apps (iOS/Android) | Web + PWA only |
| Online tuition payment | Legal/security load — future |
| Cafeteria ordering, second-hand marketplace | Low priority — future |

> Moderation and search must be **rule-based / full-text**, not ML-based. Do not add AI/LLM SDKs or API keys anywhere in the repo.

---

## 4. Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (latest stable at scaffold time, App Router) + TypeScript (strict), Tailwind CSS, shadcn/ui (**heavily re-themed, see §12**), TanStack Query, Zustand (chat client state), next-intl |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + Alembic, Pydantic v2 |
| Real-time | FastAPI WebSocket gateway + Redis Pub/Sub (fan-out across workers) |
| DB | PostgreSQL 16 (FTS with `simple` config + Azerbaijani-aware normalization, see §5.7.1) |
| Cache / presence / rate limit | Redis 7 |
| Background jobs | ARQ (Redis-based) — notifications, video transcoding, imports, digests |
| Object storage | MinIO (S3 API), presigned upload/download URLs |
| Video | FFmpeg → HLS (360p/720p), hls.js player |
| Auth | Keycloak (OIDC) — university SSO; JWT access (15 min) + refresh (httpOnly cookie) |
| Push | Web Push (VAPID) + e-mail (SMTP) |
| DevOps | Docker, docker compose (dev/pilot), GitHub Actions CI, Nginx reverse proxy |
| Observability | Sentry, Prometheus + Grafana, structured JSON logs |
| Testing | pytest + httpx + pytest-asyncio, Playwright (E2E), Vitest (FE unit) |

At scaffold time, **pin exact versions** of every dependency (lockfiles committed) and record them in `docs/DECISIONS.md`.

### 4.1 Repository layout
```
smartazmiu/
├── apps/
│   ├── web/                 # Next.js
│   │   ├── src/app/(public)/ (auth)/ (app)/
│   │   ├── src/features/    # chat/, schedule/, events/, materials/ ...
│   │   ├── src/components/ui/   # design-system primitives (§12)
│   │   ├── src/styles/tokens.css # design tokens (§12.2) — single source of truth
│   │   ├── src/lib/api/     # generated typed client (openapi-typescript)
│   │   └── messages/az.json en.json ru.json
│   └── api/                 # FastAPI
│       ├── app/core/        # config, security, db, redis, rbac
│       ├── app/modules/     # one package per domain
│       │   ├── auth/ users/ academics/ schedule/ events/
│       │   ├── notifications/ chat/ mentorship/ materials/
│       │   ├── video/ feed/ forum/ assignments/ attendance/ ...
│       │   └── <module>/{models,schemas,service,router,ws,tests}.py
│       ├── app/workers/     # ARQ tasks
│       └── alembic/
├── infra/ (docker, nginx, keycloak realm export, grafana)
├── docker-compose.yml
├── Makefile
├── CLAUDE.md                # condensed rules for Claude Code
└── docs/ (this file, DECISIONS.md, ADRs)
```

### 4.2 Cross-cutting API conventions

- Base path `/api/v1`. Resource IDs: UUIDv7 for general entities; **snowflake BIGINT** for `messages` (time-ordered, used as cursor). IDs are serialized as strings in JSON (avoid JS 53-bit overflow).
- **Error envelope** (all non-2xx): `{ "error": { "code": "chat.channel_readonly", "message": "<localized>", "details": {...}, "request_id": "..." } }`. Codes are stable, namespaced, English; messages localized via `Accept-Language`.
- **Pagination:** cursor-based for feeds/messages (`before`/`after`/`limit`, max 100); offset-based allowed only for admin tables.
- **Idempotency:** all mutating endpoints that can be retried accept `Idempotency-Key` (or `client_msg_id` for messages). Duplicate requests return the original result.
- **Optimistic concurrency:** editable entities carry `updated_at`/`version`; stale writes return `409`.
- **Soft delete** (`deleted_at`) for user content; hard delete only via retention jobs.
- **Rate limits** return `429` with `Retry-After`.
- **OpenAPI** is the contract; the TypeScript client is generated from it in CI. A diff in the generated client without a matching backend change fails CI.
- All list endpoints are permission-filtered **in the query**, never post-filtered in Python.

---

## 5. Chat module — detailed specification

### 5.1 Channel types

| Type | Code | Members | Created | Lifetime | Teacher present |
|---|---|---|---|---|---|
| Course channel | `course_offering` | Enrolled students of a subject offering + its teacher(s) | Auto, on enrollment import | Semester; then archived read-only | Yes |
| Subject community | `subject_community` | All current enrollees of the subject (any group) + verified past students who opted in as guides | Auto, one per subject | Permanent | No (student space, moderated) |
| Academic group | `academic_group` | Students of the group (e.g. 765a2) + curator | Auto | Until graduation | Curator only |
| Faculty / specialty | `faculty` | All students of faculty/specialty | Auto | Permanent | Optional |
| Announcement | `announcement` | Target audience, read-only | Staff | Permanent | — |
| Club | `club` | Club members | Club owner (approved) | Permanent | — |
| Private group | `private_group` | Invited users (max 50) | Any user | Until deleted | — |
| Direct message | `dm` | 2 users | On first message | Permanent | — |

**Topics inside course & community channels** (Slack-like sub-channels, fixed defaults, editable by moderators):
`#ümumi` (general) · `#suallar` (questions) · `#materiallar` (materials) · `#imtahan-hazırlığı` (exam prep) · `#məsləhət` (advice — community only).
Topic `slug` values are stored transliterated ASCII (`umumi`, `suallar`, `materiallar`, `imtahan-hazirligi`, `meslehet`) for URLs; the display `name` keeps Azerbaijani letters.

### 5.2 Cross-cohort mentorship ("Bələdçi" program)

**Goal:** a student taking *Mikroiqtisadiyyat* for the first time can get advice from someone who passed it last year.

**Eligibility to become a Guide (`guide`) for a subject:**
- Has an `enrollment` for that subject with `status = completed` and `passed = true` in a past semester.
- Account in good standing (no active chat ban).
- Opt-in (explicit consent). Eligible students get an invitation automatically when semester results are imported.
- A student currently re-enrolled in the same subject (retake) is **not** eligible for that subject until passed again.
- Guide eligibility is evaluated server-side on every opt-in and re-checked on every results import (a later correction of `passed` revokes the guide status for that subject).

**Guide profile per subject (`mentor_profiles`):**
- `subject_id`, `user_id`, `semester_taken` (e.g. 2025-Fall), `teacher_id_taken_with` (optional, shown only if guide allows)
- `grade_visibility`: `hidden` | `range` (51–70 / 71–90 / 91–100) | `exact` — default `hidden`
- `bio` (≤ 300 chars), `availability`: `available` | `busy` | `paused`, `max_open_requests` (default 3)
- Stats: `helped_count`, `helpful_rate`, `avg_response_minutes`

**Guide badge** shown next to name in that subject's community as a text badge `Bələdçi · 2025 Payız` with a compass SVG icon (no emoji in the UI chrome, see §12).

**Flows:**
1. **Ask in community** — student posts in `#məsləhət`; guides get a (rate-limited) notification for new unanswered advice posts in their subjects.
2. **Find a guide** — "Bələdçi tap" page per subject: list of available guides, sorted by: same teacher taken with → same specialty → most recent semester → helpful rate. Filters: specialty, semester, teacher.
3. **Advice request** (`mentor_requests`) — structured form: topic (enum: `exam`, `workload`, `materials`, `teacher_expectations`, `project`, `other`), free text. Guide accepts → opens a DM tagged with the request. Status: `open → accepted → resolved | declined | expired (72h)`.
4. **Feedback** — after `resolved`, the asker marks "Faydalı oldu / Faydalı olmadı" (+ optional comment, private to admins). Updates `helpful_rate` and reputation XP.
5. **Subject Guide card (`course_tips`)** — at semester end, students who passed are prompted to fill a short structured card:
   - difficulty (1–5), weekly hours (enum), most important topics, recommended resources (links/materials), exam format advice, "what I'd do differently".
   - Aggregated on the subject page: avg difficulty, avg workload, top tips (upvotable). Moderated before publish.

**Mentor request state machine (enforced in the service layer, covered by tests):**

| From | Event | To | Guard |
|---|---|---|---|
| — | create | `open` | requester ≠ mentor; requester not blocked by mentor; mentor `available` and below `max_open_requests`; requester has no other `open` request to the same mentor for the same subject |
| `open` | accept | `accepted` | only the addressed mentor (or any eligible guide if `mentor_id` is NULL); row-level lock to prevent double accept |
| `open` | decline | `declined` | mentor only |
| `open` | timeout 72 h | `expired` | ARQ job, idempotent |
| `accepted` | resolve | `resolved` | requester or mentor |
| `resolved` | feedback | `resolved` (feedback set once) | requester only, once |

**Academic integrity rules (enforced by policy + moderation):**
- Sharing actual exam questions/answers of the current semester is prohibited (report reason `exam_leak`).
- **Exam mode**: during a scheduled exam slot for subject X (from exam timetable), the course channel and subject community become read-only and attachments are disabled from `exam_start − 15 min` to `exam_end`. Configurable per subject by staff.
- Every guide-facing screen shows the label: "Tələbə məsləhətidir, rəsmi məlumat deyil" (student advice, not official information).

### 5.3 Messaging features

| Feature | Phase | Notes |
|---|---|---|
| Real-time send/receive (WebSocket) | 1 | Optimistic UI, `client_msg_id` for idempotency |
| History with cursor pagination | 1 | 50 per page, `before`/`after` cursors |
| Unread counters + last-read marker | 1 | `channel_reads.last_read_message_id` |
| Typing indicator, online presence | 1 | Redis TTL keys, throttled 1 event / 3 s |
| Replies & threads | 1 | `parent_id`; thread panel |
| Reactions (emoji) | 1 | Fixed set of 8 + picker |
| @mentions (`@user`, `@channel` for mods/teachers only) | 1 | Triggers notification |
| Attachments (images, PDF, DOCX, PPTX, ZIP ≤ 25 MB) | 1 | Presigned MinIO upload, PDF/image preview, virus scan (ClamAV) |
| Edit (15 min) / delete (soft) | 1 | "redaktə olunub" label |
| Markdown + LaTeX math (`$...$` via KaTeX) + code blocks | 1 | Important for math/engineering subjects |
| Pinned messages | 2 | Max 50 per channel |
| Polls | 2 | Single/multi choice, deadline |
| Anonymous question (in `#suallar`) | 2 | Hidden from students; visible to moderators (logged) |
| Teacher/guide verified answer | 2 | Teacher in course channel, guide in community |
| Message search (per channel + global) | 2 | Postgres FTS (`simple`) + trigram for names |
| Saved messages (bookmarks) | 2 | |
| Link previews | 2 | Server-side fetch with allowlist + timeout |
| Slow mode | 2 | Per channel, e.g. 1 msg / 30 s |
| Mute channel / notification levels (all / mentions / none) | 1 | |
| Drafts per channel | 2 | Local storage |
| Message forwarding to DM / channel | 3 | Respects source channel permissions |
| Scheduled announcements | 3 | Staff only |
| Weekly digest e-mail ("Bu həftə fənlərində nə oldu") | 3 | ARQ cron |

### 5.4 Privacy & safety

- **DM permissions** (user setting `dm_policy`): `everyone` | `shared_context` (same group/course/community — default) | `guides_and_teachers` | `nobody` (teachers/staff can always DM).
- Block user (hides messages, prevents DM), report message/user (reasons: `spam`, `harassment`, `hate`, `exam_leak`, `privacy`, `other`).
- Grades are **never** exposed through chat except via the guide's chosen `grade_visibility`. No grade data may appear in any WebSocket or chat REST payload other than the guide profile view.
- Phone numbers / e-mails not displayed by default.
- Data retention: archived course channels kept 2 years, then exported to cold storage and deleted from hot DB; DMs kept until user deletes account (soft delete + 30-day purge).
- Compliance: Azerbaijan Law "On Personal Data" — consent records, data export endpoint (`GET /me/export`), account deletion.

### 5.5 Moderation (rule-based)

- Keyword/regex blocklist (az/en/ru), configurable by admin → message held for review or rejected. Matching runs on the normalized text (§5.7.1) so `İ/ı` and diacritic variants cannot bypass it.
- Rate limits: 10 messages / 10 s per user per channel; 30 new DMs / day; attachment 20 / hour.
- New accounts (< 24 h) cannot post links or attachments in communities.
- Moderator actions: delete message, mute user in channel (1h / 24h / 7d), kick, ban from channel, global ban (admin only), lock thread, enable slow mode.
- Report queue UI with SLA indicator (target: handled < 12 h); all actions written to `moderation_actions` (audit).
- Auto-hide message after N (default 3) distinct reporters until reviewed. Reports from the same user on the same target count once. Auto-hidden content stays visible to author and moderators with a "gizlədilib" marker.
- Moderators cannot act on admins/teachers; moderator scope is limited to their assigned channels/communities.

### 5.6 Notifications

| Event | In-app | Web push | E-mail |
|---|---|---|---|
| DM received (offline) | ✓ | ✓ | digest |
| @mention / reply to my message | ✓ | ✓ | digest |
| Advice request to me (guide) | ✓ | ✓ | ✓ |
| My question got verified answer | ✓ | ✓ | — |
| New message in channel | badge only | per user level | — |
| Moderation action against me | ✓ | — | ✓ |

Quiet hours setting (default 23:00–08:00 Asia/Baku, push suppressed). Notifications are de-duplicated (same event never notifies twice) and respect mute levels, blocks, and channel membership at delivery time (not only at creation time).

### 5.7 Data model (chat + mentorship)

```text
subjects(id, code, name_az, name_en, faculty_id, credits)
semesters(id, year, term ENUM(fall,spring,summer), starts_at, ends_at)
course_offerings(id, subject_id, semester_id, academic_group_id, teacher_id)
enrollments(id, user_id, course_offering_id, status ENUM(active,completed,dropped), passed BOOL, grade SMALLINT NULL)

channels(id, type, name, slug, subject_id NULL, course_offering_id NULL, academic_group_id NULL,
         is_archived, is_readonly, slow_mode_seconds, created_by, created_at)
channel_topics(id, channel_id, slug, name, position, is_default)
channel_members(channel_id, user_id, role ENUM(owner,moderator,member,readonly), joined_at,
                notify_level ENUM(all,mentions,none), muted_until, PRIMARY KEY(channel_id,user_id))
channel_reads(channel_id, user_id, last_read_message_id, updated_at)

messages(id BIGINT snowflake, channel_id, topic_id NULL, author_id, parent_id NULL,
         body TEXT, body_tsv TSVECTOR, is_anonymous, is_verified_answer, verified_by NULL,
         client_msg_id UUID, edited_at, deleted_at, created_at)          -- partitioned by month
message_attachments(id, message_id, object_key, mime, size_bytes, width, height, scan_status)
message_reactions(message_id, user_id, emoji, created_at, PK(message_id,user_id,emoji))
message_mentions(message_id, user_id)
pinned_messages(channel_id, message_id, pinned_by, pinned_at)
polls(id, message_id, multi, closes_at) ; poll_options(id, poll_id, text) ; poll_votes(poll_id, option_id, user_id)
saved_messages(user_id, message_id, created_at)

mentor_profiles(id, user_id, subject_id, semester_taken_id, teacher_taken_with_id NULL,
                grade_visibility ENUM(hidden,range,exact), show_teacher BOOL, bio,
                availability ENUM(available,busy,paused), max_open_requests,
                helped_count, helpful_count, unhelpful_count, avg_response_minutes, created_at)
mentor_requests(id, subject_id, requester_id, mentor_id NULL, topic ENUM, body,
                status ENUM(open,accepted,resolved,declined,expired), dm_channel_id NULL,
                feedback ENUM(helpful,not_helpful) NULL, feedback_note, created_at, updated_at)
course_tips(id, subject_id, author_id, semester_taken_id, difficulty 1-5, weekly_hours ENUM,
            key_topics, resources JSONB, exam_advice, retrospective,
            status ENUM(pending,published,rejected), upvotes, created_at)

user_blocks(blocker_id, blocked_id, created_at)
reports(id, reporter_id, target_type ENUM(message,user,tip), target_id, reason ENUM, note,
        status ENUM(open,actioned,dismissed), handled_by, handled_at)
moderation_actions(id, moderator_id, action ENUM, target_user_id, channel_id NULL, message_id NULL,
                   duration_seconds NULL, reason, created_at)
blocked_terms(id, pattern, is_regex, action ENUM(hold,reject), lang)
exam_slots(id, course_offering_id, starts_at, ends_at, room)       -- drives exam mode
```

Indexes: `messages(channel_id, id DESC)`, `messages(parent_id)`, GIN on `body_tsv`, `channel_members(user_id)`, `enrollments(user_id, status)`, `mentor_profiles(subject_id, availability)`.

Additional constraints:
- `UNIQUE (channel_id, client_msg_id)` on messages (idempotency).
- `UNIQUE (user_id, subject_id)` on `mentor_profiles`.
- `CHECK (difficulty BETWEEN 1 AND 5)` on `course_tips`; one tip per `(author_id, subject_id, semester_taken_id)`.
- DM channels are unique per unordered user pair (store `user_low_id`, `user_high_id` with a unique index).
- **Partitioning note:** PostgreSQL requires the partition key in every unique/primary key. Partition `messages` by `created_at` (monthly) with PK `(id, created_at)`; because snowflake IDs embed time, queries by `id` cursor can also supply a `created_at` range derived from the ID to enable partition pruning. Record the final choice in an ADR. A foreign key to a partitioned `messages` table is not possible from other tables on `id` alone, so referencing tables (`message_reactions`, `message_mentions`, etc.) store `message_id` and enforce integrity in the service layer plus a periodic consistency job.

#### 5.7.1 Azerbaijani-aware text normalization (search, moderation)

Postgres `simple` FTS does no stemming; correctness for Azerbaijani depends on normalization **before** indexing and querying. Implement one shared function `normalize_az(text)` used by tsvector generation, search queries and the blocklist:
1. Unicode NFKC.
2. Locale-aware lowercase: `İ → i`, `I → ı` (not the default `I → i`).
3. Produce two forms: the **exact** form and an **ASCII-folded** form (`ə→e, ı→i, ö→o, ü→u, ç→c, ş→s, ğ→g`), index both so that `mikroiqtisadiyyat` and typed-without-diacritics queries (`İqtisadi riyaziyyat` ↔ `Iqtisadi riyaziyyat`) match.
4. Strip zero-width characters and collapse repeated whitespace.
Unit tests must include: `İSTİFADƏÇİ`, `ISTIFADECI`, `ıspanaq`, mixed az/en/ru text.

### 5.8 API (REST, prefix `/api/v1`)

```
GET    /chat/channels                         # my channels + unread counts
GET    /chat/channels/{id}
GET    /chat/channels/{id}/messages?before=&after=&topic=&limit=
POST   /chat/channels/{id}/messages           # fallback when WS unavailable
PATCH  /chat/messages/{id}                    # edit
DELETE /chat/messages/{id}
POST   /chat/messages/{id}/reactions          # {emoji}
DELETE /chat/messages/{id}/reactions/{emoji}
GET    /chat/messages/{id}/thread
POST   /chat/messages/{id}/verify             # teacher / guide
POST   /chat/channels/{id}/pins/{message_id}
POST   /chat/channels/{id}/read               # {last_read_message_id}
POST   /chat/attachments/presign              # {filename, mime, size} -> {url, object_key}
GET    /chat/search?q=&channel_id=
POST   /chat/dm                               # {user_id} -> channel (checks dm_policy, blocks)
POST   /chat/groups                           # private group
PATCH  /chat/channels/{id}/members/me         # notify_level, mute

GET    /subjects/{id}/guides?specialty=&semester=&teacher=
POST   /subjects/{id}/guides/me               # opt-in (eligibility check)
PATCH  /subjects/{id}/guides/me
POST   /mentor-requests                       # {subject_id, mentor_id?, topic, body}
POST   /mentor-requests/{id}/accept|decline|resolve
POST   /mentor-requests/{id}/feedback
GET    /subjects/{id}/tips ; POST /subjects/{id}/tips ; POST /tips/{id}/upvote

POST   /reports ; GET /moderation/reports ; POST /moderation/actions
POST   /users/{id}/block ; DELETE /users/{id}/block
```

### 5.9 WebSocket protocol (`/ws?token=`)

JSON envelope: `{ "type": "...", "id": "<client uuid>", "data": {...} }`

Client → server: `subscribe {channel_ids}`, `message.send {channel_id, topic_id?, parent_id?, body, attachments[], client_msg_id, is_anonymous?}`, `message.edit`, `message.delete`, `typing {channel_id}`, `read {channel_id, message_id}`, `reaction.add|remove`, `ping`.

Server → client: `ack {id, message_id}`, `error {id, code, detail}`, `message.created|updated|deleted`, `reaction.updated`, `typing`, `presence {user_id, status}`, `read.updated`, `channel.updated` (readonly/exam mode/slow mode), `notification`.

Server rules: authorize every event against `channel_members` + channel state (archived, readonly, exam mode, slow mode, mute); persist **before** publish to Redis channel `chat:{channel_id}`; heartbeat every 25 s; reconnect with `after=<last_seen_id>` to backfill.

Additional protocol requirements:
- **Auth in the query string is acceptable only over TLS and must be a short-lived, single-purpose WS ticket** (obtained from `POST /ws/ticket`, valid 60 s, one use), not the main JWT, so tokens do not end up in access logs.
- **Token expiry mid-connection:** server sends `error {code: "auth.expired"}` and closes with a specific code; client refreshes the session and reconnects. Also send `auth.refresh` flow so long sessions do not drop silently.
- **Membership changes while connected** (kicked, group transfer, exam mode, channel archived) must take effect immediately: gateway subscribes to a per-user control channel and unsubscribes sockets from revoked channels.
- **Multiple tabs/devices:** one user may have N sockets; presence is `online` while ≥ 1 socket alive, with a 30 s grace period before `offline`.
- **Backpressure:** per-socket send queue limit; slow consumers are disconnected with a reconnect hint rather than blocking the broker.
- **Ordering:** clients order by snowflake `id`, not arrival time; optimistic messages are reconciled by `client_msg_id` on `ack`.
- **Message size limit:** 4 000 characters body; larger payloads rejected with a typed error.

Load target: 3 000 concurrent sockets, p95 message delivery < 300 ms (pilot hardware: 2 API workers, 4 vCPU, 8 GB).

---

## 6. Other modules (summary spec)

| Module | Key entities | Key screens |
|---|---|---|
| Auth & profile | users, roles, permissions, sessions, consents | Login (SSO), onboarding, profile, privacy settings |
| Academic data import | faculties, specialties, academic_groups, subjects, course_offerings, enrollments | Admin CSV/XLSX import wizard with validation report |
| Homepage | widgets config | Today's classes, upcoming exam, unread chat, new announcements |
| Schedule | schedule_entries (offering, weekday, slot, room, week_parity upper/lower), schedule_changes | Week/day view, changes highlighted, `.ics` export |
| Campus map | buildings, floors, rooms (code, type, coordinates) | Building/floor plan (SVG), room search, deep link from schedule |
| Events & announcements | events, rsvps, tickets(QR), announcements(target audience) | List/filter, detail, RSVP, my tickets, staff editor |
| Notifications | notifications, push_subscriptions, preferences | Bell dropdown, settings |
| Materials | materials(subject, semester, type, object_key, version), material_reports | Catalog by subject/semester, preview, upload with copyright consent |
| Video lessons | videos, video_renditions, video_progress, chapters | Teacher upload, HLS player, chapters, progress, subtitles (.vtt upload) |
| Feed & Q&A forum | posts, comments, votes, tags, accepted_answer | Feed, question page, tag pages |
| Assignments & quizzes | assignments, submissions, grades, quizzes, questions, attempts | Teacher builder, student submit, grading view |
| Attendance | attendance_sessions(rotating QR token), attendance_records | Teacher QR screen (rotates 30 s), student scanner, report |
| Exam center | exam_slots, past_papers | Countdown, room, archive |
| GPA calculator | client-side + grades API | Current GPA, "what-if" simulator |
| Personal cabinet integration | external API adapter | Grades, transcript, appeals status (read-only mirror) |
| Reputation | xp_events, badges, leaderboards | Profile badges, weekly leaderboard |
| E-requests & helpdesk | requests(type, status), tickets | Submit, track, staff inbox |
| Clubs, career, library, office hours | clubs, vacancies, books/loans, office_hour_slots | Respective pages |
| Admin & analytics | audit_logs, aggregated metrics | Users/roles, imports, moderation, dashboards |

### 6.1 Module rules that must not be missed

- **Schedule:** entries are wall-clock (`weekday`, `slot` start/end, `week_parity` ∈ `every|upper|lower`). The current parity is computed from a configurable semester start date and a per-semester override table (holidays shift parity). `schedule_changes` (cancel / move / replace room / substitute teacher) overlay base entries for a specific date and are shown with a clear "dəyişiklik" marker; `.ics` export must include changes and use `Asia/Baku`.
- **Attendance QR:** token = signed, 30 s validity, bound to `attendance_session_id`; server accepts the previous token for a 5 s grace period; one record per `(session, student)`; replay and screenshot-sharing mitigated by optional geofence and per-device rate limit; teacher can manually mark/unmark with an audit entry.
- **Materials:** copyright consent is mandatory at upload; versioned (new upload = new version, old versions retained); reportable; files scanned (ClamAV) before becoming downloadable.
- **Quizzes:** attempt state persisted server-side; timer is server-authoritative (client timer is cosmetic); late submission after expiry is auto-submitted with answers received so far.
- **Imports (CSV/XLSX):** dry-run preview → confirm → apply in a single transaction per entity batch; upserts keyed by natural keys; row-level error report downloadable; re-import of the same file is a no-op; character encoding detection (UTF-8 / Windows-1254 / CP1251) with explicit user override; Azerbaijani letters validated after decoding.
- **Announcements:** audience resolved at publish time **and** re-evaluated for users who join the audience later (e.g. transfer into the group) when the announcement is still active.

---

## 7. Non-functional requirements

- **Performance:** LCP < 2.5 s on 4G, API p95 < 300 ms, chat delivery p95 < 300 ms.
- **Availability:** ≥ 99.5 %; no planned maintenance during exam sessions (January, June).
- **Security:** OWASP ASVS L2; HTTPS only; CSP; rate limiting; JWT rotation; 2FA for staff/admin; ClamAV on uploads; daily encrypted backups (pg_dump + MinIO mirror), restore tested monthly. Details in §14.
- **Accessibility:** WCAG 2.1 AA; keyboard navigation in chat; screen-reader labels.
- **Responsive:** 320 px → 4K, mobile-first; PWA installable, offline cache for schedule & last 50 messages per channel.
- **Observability:** Sentry FE+BE; Grafana dashboards (WS connections, msg/s, error rate, queue lag).

---

## 8. Detailed roadmap

**Cadence:** 2-week sprints. **Start:** Mon 2026-11-02. **Team (core):** PM, UI/UX designer, 2 frontend, 2 backend, QA, DevOps (0.5).
**Key dates:** Pilot (1 faculty) at spring semester start → **2027-02-22**. University-wide launch → **2027-09-15**.

### Milestones

| ID | Milestone | Date | Gate |
|---|---|---|---|
| M0 | PRD + clickable prototype approved | 2026-11-27 | Sponsor sign-off |
| M1 | MVP feature-complete (incl. chat core) | 2027-02-19 | All Phase 1 acceptance criteria |
| M2 | Pilot launch — 1 faculty | 2027-02-22 | ≥ 300 pilot users onboarded |
| M3 | Chat 2.0 + Mentorship live in pilot | 2027-04-16 | First guide matches done |
| M4 | Academic & social expansion complete | 2027-06-25 | Feature freeze for launch |
| M5 | Launch readiness (load, security, content) | 2027-09-03 | Pen-test passed, load test passed |
| M6 | University-wide launch | 2027-09-15 | — |
| M7 | Ecosystem release | 2027-12-17 | Phase 5 scope done |

---

### Phase 0 — Discovery & Design (Weeks 1–4 · 2026-11-02 → 2026-11-27)

- [ ] Stakeholder kickoff: rector's office, dean's offices, IT department, student council; name a project sponsor.
- [ ] Interviews: 20+ students (incl. 1st-year and 3rd/4th-year for mentorship angle), 10+ teachers, 3 staff.
- [ ] Survey (≥ 100 students): current channels used (Telegram/WhatsApp), pain points, willingness to be a guide.
- [ ] Audit existing systems: personal cabinet (API? DB export?), schedule source format, SSO/e-mail directory.
- [ ] Data-sharing agreement + personal-data compliance review.
- [ ] Information architecture, user flows (onboarding, chat, find a guide, advice request).
- [ ] Design system in Figma implementing **§12** (tokens, typography, components, dark mode); public-site and app-shell layouts reviewed against official university/government portals.
- [ ] Clickable prototype; usability test with 6–8 students.
- [ ] Technical ADRs: modular monolith, WS + Redis, Keycloak, partitioned messages table (see §5.7 partition note), Azerbaijani text normalization (§5.7.1).
- [ ] Backlog in issue tracker, estimates, risk register.
**Exit:** M0.

---

### Phase 1 — Foundation + MVP + Chat Core (Sprints 1–6 · 2026-11-30 → 2027-02-19)

#### Sprint 1 (2026-11-30 → 12-11) — Infrastructure & Auth
- [x] Monorepo scaffold (`apps/web`, `apps/api`), Makefile, pre-commit (ruff, mypy, eslint, prettier), `CLAUDE.md`, `docs/DECISIONS.md`.
- [x] docker compose: postgres, redis, minio, keycloak, mailpit, api, web, nginx.
- [x] GitHub Actions: lint, type-check, test, build images, OpenAPI client drift check.
- [x] Keycloak realm (roles, test users), OIDC login in Next.js, JWT validation in FastAPI.
- [x] `users`, `roles`, `permissions`, RBAC dependency `require_permission(...)`.
- [x] Sentry + structured logging; `/healthz`, `/readyz`.
- [x] **Design tokens + primitives (§12.2–12.4)** implemented in `tokens.css` and `components/ui/*`; internal `/design-system` page (non-production) showing every primitive in light/dark, all states, and an Azerbaijani glyph specimen.
- [x] Frontend shell: layout, sidebar, top bar, theme (light/dark), i18n (`az.json`).
**Acceptance:** fresh clone → `make up` → login with test student → see empty dashboard; `/design-system` passes the §12.9 visual checklist.

#### Sprint 2 (12-14 → 12-25) — Academic data & Profile & Admin v1
- [x] Models: faculties, specialties, academic_groups, subjects, semesters, course_offerings, enrollments.
- [x] Admin import wizard (CSV/XLSX): preview, validation errors per row, idempotent upsert (rules in §6.1).
- [x] Profile page: photo upload, bio, group, specialty, privacy settings (`dm_policy`, contact visibility).
- [x] Admin v1: user list, role assignment, audit log viewer.
- [x] Consent records + `/me/export`.
**Acceptance:** import a real (anonymized) group 765a2 roster with its subjects; student sees own group and subjects.

#### Sprint 3 (12-28 → 2027-01-08) — Homepage, Schedule, Map
- [x] Schedule model with upper/lower week parity, changes; import from source format.
- [x] Week/day views, today widget, `.ics` export.
- [x] Campus map: buildings/floors/rooms, SVG floor plans, room search, link from schedule entry.
- [x] Homepage widgets: today's classes, announcements, (placeholder) unread chat.
**Acceptance:** student opens homepage → sees today's classes → taps room → map highlights room.

#### Sprint 4 (01-11 → 01-22) — Events, Announcements, Notifications
- [x] Announcements with target audience (university / faculty / specialty / group / course offering).
- [x] Events: list, filters, detail, RSVP, QR ticket, check-in screen for staff.
- [x] Notification service: in-app (bell), Web Push (VAPID), e-mail (ARQ), preferences + quiet hours.
**Acceptance:** staff publishes an event for faculty X → students of X receive push + in-app; RSVP produces QR ticket.
*(Exam session in January — keep releases to staging only.)*

#### Sprint 5 (01-25 → 02-05) — Chat Core
- [x] Chat models (channels, topics, members, reads, messages partitioned, attachments, reactions, mentions).
- [x] Auto-provisioning job: on enrollment import create/sync `course_offering`, `subject_community`, `academic_group`, `faculty` channels and memberships; default topics. Must be idempotent and handle membership removal (dropped enrollment, group transfer).
- [x] WebSocket gateway: ticket auth, subscribe, `message.send` (persist → publish), ack, error codes, heartbeat, reconnect + backfill, live membership revocation (§5.9).
- [x] Redis pub/sub fan-out; presence; typing (throttled).
- [x] REST: channel list with unread counts, paginated history, read marker.
- [x] DM creation with `dm_policy` + block checks.
- [x] Frontend: channel sidebar (grouped: Fənlər / Fənn icmaları / Qrup / Şəxsi), message list (virtualized), composer, unread badges, presence dots — built to the chat UI rules in §12.7.
- [x] Rate limiting (10 msg / 10 s).
**Acceptance:** two browsers, two students of 765a2 → real-time messages in course channel and DM; reconnect after network drop loses nothing; teacher appears in course channel but not in subject community.

#### Sprint 6 (02-08 → 02-19) — Chat UX + Materials v1 + Pilot hardening
- [x] Threads (side panel), replies, reactions, @mentions (+ notifications), edit (15 min) / soft delete.
- [x] Attachments: presigned upload, ClamAV scan, image & PDF preview, size/type limits.
- [ ] Markdown (sanitized) + KaTeX + code blocks; mute / notification level per channel.
- [ ] Report message (basic) + admin list.
- [ ] Materials v1: catalog per subject/semester, upload with copyright consent, preview, download.
- [ ] Onboarding tour, empty states, Azerbaijani copy review (tone rules in §12.8).
- [ ] Load test (k6): 1 000 sockets, 50 msg/s. E2E Playwright suite for chat happy paths.
- [ ] Pilot runbook, support channel, feedback form.
**Acceptance:** M1. **Release:** M2 pilot on 2027-02-22.

---

### Phase 2 — Chat 2.0 & Cross-Cohort Mentorship (Sprints 7–10 · 2027-02-22 → 2027-04-16)

#### Sprint 7 (02-22 → 03-05) — Subject Communities
- [ ] Community channel UX: topics `#ümumi #suallar #materiallar #imtahan-hazırlığı #məsləhət`.
- [ ] Eligibility service: past `completed && passed` enrollments → guide eligibility per subject (rules in §5.2).
- [ ] Guide invitation flow (notification + e-mail) after results import; opt-in page with consent, `grade_visibility`, `show_teacher`, bio.
- [ ] Guide badge rendering in messages and member list.
- [ ] Import historical enrollments (previous 2 years) for pilot faculty.
**Acceptance:** a student who passed Mikroiqtisadiyyat in 2025-Fall opts in → appears with guide badge in the community; grade hidden by default.

#### Sprint 8 (03-08 → 03-19) — Find a Guide & Advice Requests
- [ ] "Bələdçi tap" page per subject: ranking (same teacher → same specialty → recency → helpful rate), filters.
- [ ] Advice request form + lifecycle per the state machine in §5.2, ARQ expiry job.
- [ ] Accept → DM channel tagged with request header card.
- [ ] Guide availability + `max_open_requests` enforcement (race-safe).
- [ ] Feedback (helpful / not helpful) → stats update; guide stats on profile.
- [ ] Notifications for guides on new `#məsləhət` posts (digest, max 5/day).
**Acceptance:** first-year student requests advice → guide accepts → DM opens → resolved → feedback recorded; stats visible.

#### Sprint 9 (03-22 → 04-02) — Knowledge in channels
- [ ] Subject Guide card (`course_tips`): end-of-semester prompt, form, moderation queue, aggregated subject page (difficulty, workload, top tips, upvotes).
- [ ] Pinned messages, channel "Faydalı" (useful) collection.
- [ ] Polls.
- [ ] Anonymous questions in `#suallar` (moderator-visible identity, logged).
- [ ] Verified answer (teacher in course channel, guide in community) + "my question answered" notification.
- [ ] Saved messages.
**Acceptance:** subject page shows aggregated tips from ≥ 3 past students; anonymous question shows "Anonim" to students and real author to moderator.

#### Sprint 10 (04-05 → 04-16) — Moderation, Search, Exam Mode
- [ ] Blocked-terms engine (hold/reject) using `normalize_az`, auto-hide after 3 reports.
- [ ] Moderator console: report queue with SLA, actions (delete, mute 1h/24h/7d, kick, ban, slow mode, lock thread), audit.
- [ ] Message search: channel + global, Postgres FTS (`simple`) + trigram, permission-filtered **inside the SQL query**.
- [ ] Exam mode from `exam_slots` (read-only + no attachments, −15 min → end), `channel.updated` WS event, banner UI.
- [ ] New-account restrictions; DM daily limit.
- [ ] Link previews (allowlist, SSRF-safe).
**Acceptance:** M3. Exam slot simulation flips channel to read-only on time; search never returns messages from channels the user isn't in.

---

### Phase 3 — Academic & Social Expansion (Sprints 11–15 · 2027-04-19 → 2027-06-25)

#### Sprint 11 (04-19 → 04-30) — Video Lessons
- [ ] Teacher upload (resumable, presigned multipart), ARQ FFmpeg → HLS 360p/720p, thumbnails.
- [ ] Player (hls.js): speed, chapters, `.vtt` subtitles, progress tracking, "continue watching".
- [ ] Link video to subject; "discuss in channel" button (opens thread in course channel).
**Acceptance:** 1 GB lecture uploads, plays adaptively; progress persists.

#### Sprint 12 (05-03 → 05-14) — Feed & Q&A Forum
- [ ] Feed: posts, tags, "faydalı" reaction, comments, report.
- [ ] Q&A forum: questions, answers, votes, accepted answer, teacher-verified badge, tag pages.
- [ ] Cross-link: promote a chat thread to a forum question (keeps knowledge searchable).

#### Sprint 13 (05-17 → 05-28) — Assignments & Quizzes
- [ ] Assignments: create, deadline, file submission, late policy, grading + feedback.
- [ ] Quizzes: MCQ / multi / short answer, timer, auto-grading (non-open), stats.

#### Sprint 14 (05-31 → 06-11) — Attendance, Exam Center, GPA
- [ ] QR attendance: teacher screen with token rotating every 30 s, optional geofence (campus bounds), student scan via PWA camera, reports/export.
- [ ] Exam center: timetable, countdown, room → map, past papers archive (teacher-approved).
- [ ] GPA calculator with what-if simulation.
*(June exam session: freeze production changes from week of 06-07 except hotfixes.)*

#### Sprint 15 (06-14 → 06-25) — Integrations, PWA, i18n
- [ ] Personal cabinet adapter (grades, transcript, appeals) — read-only mirror, nightly sync or live API.
- [ ] PWA: manifest, service worker, offline schedule + last 50 messages/channel, install prompt.
- [ ] i18n EN + RU (strings), locale switcher.
- [ ] Feature freeze. **Acceptance:** M4.

---

### Phase 4 — Launch Readiness (Weeks 35–44 · 2027-06-28 → 2027-09-03, summer)

- [ ] Load test: 3 000 concurrent sockets, 200 msg/s, homepage 500 rps; fix bottlenecks.
- [ ] External penetration test + remediation; dependency audit.
- [ ] Backup/restore drill; disaster recovery runbook.
- [ ] Production infra: separate DB host, MinIO with replication, CDN for static/HLS, monitoring alerts.
- [ ] Import all faculties' data for 2027-Fall; auto-provision all channels.
- [ ] Guide recruitment campaign: invite all students who passed subjects in 2025–2027 (target ≥ 1 guide per subject, ≥ 3 for first-year subjects).
- [ ] Content: teacher onboarding sessions, video lesson seeding (≥ 5 per first-year subject), help center articles, community guidelines (incl. exam integrity rules).
- [ ] Student ambassadors (1–2 per faculty), launch-week plan, Telegram-group migration guide.
- [ ] Accessibility audit (WCAG 2.1 AA) fixes.
**Exit:** M5 → **M6 launch 2027-09-15**.

---

### Phase 5 — Ecosystem (Sprints 16–20 · 2027-09-20 → 2027-12-17)

| Sprint | Dates | Scope |
|---|---|---|
| 16 | 09-20 → 10-01 | Post-launch stabilization, bug bash, performance tuning, feedback triage |
| 17 | 10-04 → 10-15 | Reputation: XP events (helpful answers, verified answers, guide help), badges, weekly leaderboards (anti-abuse caps) |
| 18 | 10-18 → 10-29 | E-requests (certificates, transcript, leave, transfer) + helpdesk tickets with staff inbox & SLA |
| 19 | 11-01 → 11-12 | Clubs (pages, membership, club channels, events), career center (vacancies, internships, CV builder) |
| 20 (5 wks) | 11-15 → 12-17 | Library (catalog, availability, reserve, due reminders), office hours booking, analytics dashboards, weekly chat digest e-mail, message forwarding, scheduled announcements |

### Backlog — future (not scheduled)
Online tuition payment · cafeteria menu & ordering · second-hand marketplace · dormitory module · portfolio for architecture students · SaaS for other universities.
*(AI features, calls and native apps can be re-evaluated only by an explicit product decision.)*

---

## 9. KPIs

| KPI | Target (first academic year) |
|---|---|
| Registration rate | ≥ 60 % of students |
| MAU / total students | ≥ 45 %; DAU/MAU ≥ 25 % |
| Active course channels (≥ 10 msgs/week) | ≥ 70 % of offerings |
| Subjects with ≥ 1 available guide | ≥ 80 % (100 % for 1st-year subjects) |
| Advice requests accepted within 24 h | ≥ 75 % |
| Advice marked helpful | ≥ 80 % |
| Forum/`#suallar` median time to first answer | < 6 h |
| Reports handled < 12 h | ≥ 90 % |
| Video completion rate | ≥ 50 % |
| E-request turnaround | −50 % vs. baseline |
| NPS | ≥ 30 |
| Uptime / error rate | ≥ 99.5 % / < 0.5 % |

---

## 10. Risks

| Risk | P | I | Mitigation |
|---|---|---|---|
| Students stay on Telegram/WhatsApp | H | H | Auto-created channels (zero setup), unique value (guides, materials, tips), ambassadors, migration guide |
| Too few guides / guides go inactive | M | H | Auto-invite after results, badges + XP, `max_open_requests`, recognition (certificate of mentorship) |
| Exam cheating via chat | M | H | Exam mode, `exam_leak` report reason, integrity rules, moderator alerts |
| Harassment / spam / hate | M | M | DM policy defaults, blocks, rate limits, blocked terms, moderators, fast SLA |
| Grade privacy leak | L | VH | Grades hidden by default, explicit visibility choice, no grade data in chat payloads |
| Wrong advice from guides | M | M | "Student advice, not official" label, teacher-verified answers, feedback stats |
| Integration with existing AzMİU systems | M | H | Early audit, CSV fallback import |
| Teachers inactive on platform | H | M | Training, simple upload UX, dean support |
| WebSocket scaling | L | M | Redis fan-out, horizontal workers, load tests per phase |
| Scope creep | H | M | MoSCoW discipline, frozen sprint scope, change log |
| Product looks like a generic template and loses institutional trust | M | M | §12 Design Standard, visual QA checklist per sprint, reviews against official portals |

---

## 11. Definition of Done (per ticket)
- Code reviewed, merged to `main` via PR, CI green.
- Tests: unit + integration (backend), component/E2E for critical flows; applicable cases from §13 covered.
- Migrations reversible; seed data updated.
- i18n strings added (az mandatory).
- Permissions checked server-side; no data leaks across channels/roles (test included).
- Telemetry/logging for new endpoints; docs/ADR updated if architecture changed.
- UI changes verified against §12.9 (light + dark, 320 px + desktop, keyboard-only pass).

---

## 12. UI Design Standard — professional, institutional, not template-looking

**Goal:** the product must look like an official university / government-grade service: calm, dense where useful, precise, trustworthy. A visitor must not be able to tell it was generated from a UI kit with default settings. Build to this section from Sprint 1; it overrides default shadcn/Tailwind styling.

### 12.1 Design principles

1. **Clarity over decoration.** Hierarchy comes from typography, spacing and alignment — not from colour, shadow or effects.
2. **One restrained accent.** Neutral surfaces + a single deep institutional blue; a muted secondary accent used only for highlights/badges.
3. **Flat and structured.** 1 px borders and whitespace instead of shadows and cards-in-cards.
4. **Information density appropriate to the task.** Tables, schedules and chat are compact; public pages are airy and readable.
5. **Consistency.** Every pattern (page header, table, form, empty state, confirmation) has exactly one implementation reused everywhere.

### 12.2 Design tokens (single source: `apps/web/src/styles/tokens.css`)

Define as CSS variables, map into Tailwind theme; **no raw hex values in components**.

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#FFFFFF` | `#0F141A` |
| `--bg-subtle` | `#F5F6F8` | `#141A21` |
| `--surface` | `#FFFFFF` | `#161D26` |
| `--border` | `#D9DDE3` | `#2A3441` |
| `--border-strong` | `#B8BFC9` | `#3A4656` |
| `--text` | `#1B2430` | `#E6EAF0` |
| `--text-muted` | `#5B6675` | `#9AA6B5` |
| `--primary` | `#1F3A5F` | `#6F9BD1` |
| `--primary-hover` | `#17304F` | `#8AB0E0` |
| `--primary-contrast` (text on primary) | `#FFFFFF` | `#0F141A` |
| `--accent` (sparingly) | `#8A6D1F` | `#C9A94F` |
| `--success` | `#1E6B3A` | `#4DB27A` |
| `--warning` | `#8A5A00` | `#D9A441` |
| `--danger` | `#A12A2A` | `#E06B6B` |
| `--info` | `#1F4E8C` | `#6F9BD1` |
| `--focus-ring` | `#1F3A5F` (2 px + 2 px offset) | `#8AB0E0` |

Rules: every text/background pair ≥ **4.5:1** (3:1 for large text and UI borders), verified by an automated contrast test in CI; semantic colours are never the only carrier of meaning (always pair with text or icon).
Spacing scale: 4-px base (`4, 8, 12, 16, 24, 32, 48, 64`). Radius: `4 px` controls, `6 px` panels/dialogs, avatars circular; **nothing larger**. Shadows: none on surfaces; only popovers/menus/dialogs use `0 4px 16px rgba(15,20,26,.12)`. Border width: 1 px.

### 12.3 Typography

- Family: **IBM Plex Sans** (UI/body) and **IBM Plex Mono** (code), self-hosted (no runtime Google Fonts call), `font-display: swap`, subset to Latin + Latin Extended-A/B + Cyrillic. Fallback stack: `system-ui, "Segoe UI", Roboto, Arial, sans-serif`.
- **Azerbaijani glyph gate:** Sprint 1 specimen page must render `Ə ə İ ı Ş ş Ğ ğ Ç ç Ö ö Ü ü` correctly in every weight used, with correct dotted/dotless i behaviour (`text-transform: uppercase` on `lang="az"`). Set `<html lang="az">` and switch per locale.
- Scale (px / line-height): `12/16` caption, `13/20` dense UI, `14/22` app body, `16/26` public body, `20/28` h3, `24/32` h2, `30/38` h1. Weights: 400, 500, 600 only. Headings sentence case, not all-caps. Tabular numerals (`font-variant-numeric: tabular-nums`) for tables, times, grades.
- Line length for reading text ≤ 75 characters.

### 12.4 Components & patterns (implement once, reuse everywhere)

- **App shell:** top bar 56 px (university wordmark placeholder left, global search, notifications bell, profile menu); left navigation 240 px, collapsible, grouped under small uppercase-free section labels; content max-width 1200 px; breadcrumb above the page title; page header = title + short description + right-aligned actions (max one primary button).
- **Public pages (guest):** thin utility strip (language switcher, accessibility options, contact), then main header and navigation, content, and a structured multi-column footer (about, services, contact, legal). Layout and tone follow official institutional portals: clear hierarchy, plain headings, visible focus states, skip-to-content link. No hero gradients, no decorative blobs, no stock illustrations.
- **Buttons:** primary (filled `--primary`), secondary (1 px border), tertiary (text), destructive (danger outline, filled only in confirm dialogs). Height 36 px (32 dense). One primary per view. Labels are verbs ("Yadda saxla", "Sorğu göndər").
- **Forms:** label above field, helper text below, required marker, inline validation message under the field (plain Azerbaijani, says what to do), error summary at top for long forms, never placeholder-as-label. Disabled and read-only states visually distinct.
- **Tables:** compact rows (40 px), sticky header, no zebra by default, hover highlight, right-aligned numerics, sortable columns with explicit indicator, row actions in a trailing menu, pagination or "daha çox yüklə" with total count. Mobile: tables collapse to stacked rows, never horizontal scroll of the whole page.
- **Status tags:** small rectangular tags (4 px radius) with text label; colour-coded but never colour-only. No pill-shaped gradient chips.
- **Feedback:** inline banners for page-level messages; toasts only for transient confirmations (≤ 4 s, `aria-live`); confirm dialogs for destructive actions with explicit consequence text.
- **Empty states:** one-sentence explanation + the next action, plain text, optional single-line icon (no illustrations).
- **Loading:** skeletons that match final layout for lists/tables; button spinners only for in-place actions; no full-page spinners.
- **Icons:** one set (Lucide), 1.5 px stroke, 16/20 px, consistent optical size. **No emoji used as UI icons or labels** (the 🧭/👍/👎/✅ marks in earlier drafts of this spec are rendered as SVG icons + text). Emoji appear only inside user-authored chat content and the 8-emoji reaction set.
- **Motion:** 120–160 ms opacity/position transitions only; no bounce, parallax, scale-on-hover, or animated backgrounds; respect `prefers-reduced-motion`.
- **Charts/dashboards:** muted palette derived from tokens, direct labels where possible, gridlines light, no 3D, no gradient fills.
- **Dark mode:** first-class, not an afterthought; designed with its own token values (§12.2), tested on every screen.

### 12.5 shadcn/ui customization rules

shadcn components are a starting point, **not** the visual identity. Before use: replace colour/radius/shadow/font tokens, remove default rounded-xl/2xl and soft drop-shadows, normalise focus rings to `--focus-ring`, align heights to the 32/36 px control sizes, and wrap in `components/ui/*` so feature code never imports raw library defaults.

### 12.6 Layout & responsiveness

Mobile-first from 320 px. Breakpoints: `sm 640`, `md 768`, `lg 1024`, `xl 1280`. On mobile: top bar + bottom tab bar (Ana səhifə, Cədvəl, Çat, Bildirişlər, Profil), left nav becomes a sheet. Touch targets ≥ 44 px. Respect safe-area insets (PWA). No horizontal page scroll at any width.

### 12.7 Chat UI rules

- Three-pane desktop layout (channel list · message pane · thread/details panel); single pane with back navigation on mobile.
- Messages are **left-aligned rows, not bubbles**: avatar, display name (+ role/guide badge), timestamp, body. Consecutive messages from the same author within 5 min collapse under one header. Hover toolbar (react, reply, more); day separators; a clear "new messages" divider line; compact/comfortable density toggle.
- Presence = small dot with text alternative; unread = numeric badge, mention = distinct badge style; system messages (joined, exam mode) are muted single-line text.
- Exam mode and read-only channels show a persistent banner above the composer explaining why and until when.
- Composer: multi-line, Enter to send / Shift+Enter newline (configurable), attachment chips with progress, upload/scan failure states, character counter near the limit.

### 12.8 Copy & tone (Azerbaijani)

- Formal-friendly register using **"siz"**; short, concrete sentences; no slang, no exclamation spam, no marketing superlatives, no emoji in system copy.
- Consistent terminology from the glossary (§1.2); one term per concept across the whole product.
- Error messages state what happened and what to do next; never expose internals or codes (codes go in `details` for support).
- Dates/numbers per §1.3. Pluralization via ICU message format (next-intl). Seed/demo data must be realistic (real-looking names, subjects, groups like `765a2`, rooms, dates) — **no "Lorem ipsum", no "John Doe", no placeholder gradients**.
- Public-facing legal/info pages (privacy notice, terms, community guidelines) written in clear official Azerbaijani; drafts flagged for review by the university's legal/IT office.

### 12.9 Visual QA checklist (must pass before a sprint is done)

- [ ] No gradients, glassmorphism, glow, or decorative blobs anywhere.
- [ ] No radius > 6 px (except avatars); no shadow on static surfaces.
- [ ] Only IBM Plex Sans/Mono; Azerbaijani glyph specimen renders correctly; `lang` attributes correct.
- [ ] One primary action per view; consistent page header and breadcrumb.
- [ ] All text/UI pairs meet contrast thresholds in light **and** dark.
- [ ] Every screen has loading, empty, error and forbidden states.
- [ ] Keyboard-only pass: visible focus on every interactive element, logical tab order, no traps, skip link works.
- [ ] 320 px and 1440 px screenshots reviewed; no overflow, no truncated Azerbaijani words.
- [ ] No emoji used as icons; icon set and stroke weight consistent.
- [ ] Copy reviewed for tone/terminology; no placeholder text.
- [ ] Screenshots of changed screens attached to the PR (light + dark).

### 12.10 Anti-patterns (forbidden — these make a UI look generated)

Purple/blue-to-pink gradients · centered hero with gradient headline and two CTA buttons · glassmorphism/backdrop-blur panels · oversized rounded cards with soft shadows everywhere · emoji bullets and emoji headings · identical three-column "feature cards" with icon circles · stock-style abstract illustrations · default unmodified shadcn look · mixed icon libraries · gratuitous hover scale/bounce animations · all-caps tracking-wide labels everywhere · centered body text · generic "Welcome back 👋" greetings · lorem ipsum or "Acme Inc." placeholders.

### 12.11 Brand assets

Do not fabricate or imitate the AzMİU logo or coat of arms. Use a neutral text wordmark placeholder ("SmartAzMİU") in `assets/brand/` until the university supplies official assets; make the wordmark a single swappable component and favicon/PWA icons generated from it.

---

## 13. Edge-case catalogue (check per feature; write tests for applicable rows)

### 13.1 Identity, roles, academic data
| Case | Required behaviour |
|---|---|
| Student changes group / transfers specialty | Channel memberships re-synced; old group channel access removed; messages remain, author displays unchanged |
| Academic leave / expelled / graduated | Account status `inactive`: read-only access per policy, removed from active channels, guide status retained only if policy allows (default: retained read-only off) |
| Retake of a subject (failed → re-enrolled) | New enrollment row; not eligible as guide until passed; tips from previous attempt not duplicated |
| Elective / joint lecture across groups | One offering with multiple groups; channel membership = union; schedule shows per group |
| Multiple teachers per offering / teacher replaced mid-semester | New teacher added to channel; old teacher removed (history kept); verified answers keep original verifier |
| Student with multiple roles (student + moderator) | Permissions are the union; UI shows active capacity clearly; moderator actions never apply to own content |
| User with no enrollments (new / data not imported yet) | Onboarding shows explanatory empty state, not an error |
| Duplicate/ambiguous identity on import (same e-mail, different student ID) | Row rejected with explicit error; never merged silently |
| Name changes / diacritics in names | Matching by stable ID, display name editable by admin; search uses `normalize_az` |

### 13.2 Chat & real-time
| Case | Required behaviour |
|---|---|
| Duplicate send (retry, double-click, reconnect) | `client_msg_id` makes it idempotent; one message, same `ack` |
| Offline compose then reconnect | Queued locally with state "göndərilir/uğursuz", ordered correctly after backfill, retry button on failure |
| Event arrives for a channel the user just lost access to | Dropped server-side; client removes channel and shows neutral notice |
| Edit/delete after 15 min or by non-author | Rejected with typed error; moderators may delete, not edit |
| Editing a message that has replies/thread/verified status | Allowed within window; verified status removed on edit; reactions kept |
| Deleting a parent message | Replies remain with "silinmiş mesaja cavab" placeholder |
| Mention of a user not in the channel | No notification, no leak of membership; rendered as plain text |
| `@channel` by non-privileged user | Rejected/stripped, user informed |
| Blocked user in a shared channel | Their messages collapsed for the blocker; they cannot DM; group channel behaviour unchanged |
| `dm_policy` changed after DM exists | Existing DM stays readable; new-DM creation re-evaluated; sending into `nobody` DM disabled with explanation, except teachers/staff |
| Slow mode + exam mode + mute interplay | Single authorization function returns reason code; UI shows the specific reason |
| Attachment fails virus scan / upload abandoned | `scan_status=infected` → message attachment hidden, uploader notified; orphan objects purged by job |
| Message with huge body / malicious markdown / script / SVG payload | Length limit, sanitized rendering (no raw HTML), attachments served with safe content-types and `Content-Disposition` |
| Link preview to internal/private IP | Blocked (SSRF guard), allowlist + DNS rebinding protection + timeout + size cap |
| Same user, many tabs | One logical presence, unread counts consistent across tabs via `read.updated` |
| Clock skew on client | All ordering/time decisions server-side; client times cosmetic |
| Snowflake generator restart / multiple workers | Worker IDs unique per process; monotonic within worker; tested under clock regression |
| Backfill gap too large (> 1000 missed messages) | Client discards local window and reloads latest page with "jump to unread" |
| Account deleted | Messages kept with "Silinmiş istifadəçi" author, PII scrubbed, DMs handled per §5.4 |

### 13.3 Mentorship
| Case | Required behaviour |
|---|---|
| Guide has `max_open_requests` reached / paused | Not listed as requestable; direct request rejected with clear reason |
| Two guides (or same guide twice) accept concurrently | Row lock/conditional update; second attempt gets `409` |
| Requester blocked by guide / guide blocked by requester | Guide hidden from requester, request rejected without revealing the block |
| `passed` flag corrected to false after opt-in | Guide status revoked, open requests cancelled with notification |
| Guide changes `grade_visibility` | Applies immediately everywhere (no cached copies in payloads) |
| Request expires while guide is typing accept | Accept rejected with `expired`; requester notified once |
| Feedback submitted twice / by wrong user | Idempotent single feedback; other user rejected |
| Tip submitted by someone who did not pass | Rejected; tip for the same subject+semester updates existing draft instead of duplicating |
| Abusive/inaccurate tip | Moderation queue; author can edit, which resets to `pending` |

### 13.4 Time, schedule, exams
| Case | Required behaviour |
|---|---|
| Week parity across holidays / shifted weeks | Parity override table per semester; tests for boundary weeks |
| Schedule change on a day already past | Stored for history, not re-notified |
| Two exam slots overlap for same channel/student | Exam mode union of intervals, no flicker; staff warning on creation |
| Exam slot edited after exam mode started | Re-evaluated immediately; WS `channel.updated` emitted |
| Server restart during exam window | Exam mode derived from persisted slots at read time (not only from scheduled jobs) |
| Timezone of user device ≠ Asia/Baku | UI always renders Asia/Baku, with explicit zone shown in `.ics` and exam countdowns |

### 13.5 Data import & jobs
| Case | Required behaviour |
|---|---|
| Re-import of same file / partially failed import | Idempotent; failed batch rolled back; report downloadable |
| Wrong encoding / BOM / Excel date serials / merged cells | Detected and surfaced as row/column errors, never guessed silently |
| Job retried (ARQ at-least-once) | All jobs idempotent via natural keys/idempotency keys |
| Redis outage | WS rejects new sends with typed error and client falls back to REST; no message loss because persistence precedes publish |
| Object storage outage | Uploads fail gracefully; text chat unaffected |

### 13.6 UI states
Every screen implements: loading, empty, error (with retry), forbidden (403 explanation), not found, offline (PWA), stale-data refresh, and long-text/overflow handling for Azerbaijani compound words (wrap/truncate with tooltip, never overflow layout).

---

## 14. Security checklist (enforced from Sprint 1)

- Authorization on every REST endpoint and WS event; deny by default; tests assert 403/404 for cross-channel and cross-user access (including object-key guessing for attachments — presigned URLs scoped to the requester, short TTL).
- Input validation via Pydantic; output encoding; Markdown rendered through a sanitizer allowlist; CSP with no inline scripts (nonce-based), `frame-ancestors 'none'`, HSTS, secure cookies (`httpOnly`, `SameSite=Lax`, `Secure`), CSRF protection for cookie-authenticated mutating requests.
- Secrets only from environment/secret store; `.env.example` committed, real `.env` ignored; no secrets in logs; PII redacted in logs and Sentry (scrubbing rules).
- Rate limits per IP and per user on auth, search, uploads, report creation.
- File uploads: extension + MIME + magic-byte check, size limits, ClamAV scan before availability, randomised object keys, no direct public bucket access.
- Audit log for privileged actions (role changes, bans, imports, data exports, deletions).
- Dependency scanning (pip-audit, npm audit, Dependabot) in CI; container images pinned and minimal.
- Staff/admin 2FA; session revocation; refresh-token rotation with reuse detection.
- Personal data: consent records, export, deletion with purge job, data-minimising API payloads (no e-mail/phone/grades unless the endpoint's purpose requires it).

---

## 15. Authorship hygiene (the code base must read as human-maintained engineering work)

- No comments such as "generated by", "as an AI", "TODO: implement", or narrative comments restating the code. Comments explain **why**, in concise English.
- Descriptive, domain-accurate names (`MentorRequestService.accept`, not `handle_action_1`). No placeholder identifiers (`foo`, `test123`) outside tests.
- Commit messages in Conventional Commits style, English, imperative, scoped (`feat(chat): add exam-mode read-only enforcement`); no emoji; small focused commits per task; PR descriptions list what changed, how it was tested, and screenshots for UI.
- No dead code, no commented-out blocks, no unused dependencies or files; formatting enforced by pre-commit (ruff, mypy, eslint, prettier).
- README and docs written for a new engineer: setup in ≤ 5 commands, architecture overview, how to run tests, how to add a module.
- Seed data and screenshots use realistic Azerbaijani data (see §12.8), never obvious placeholders.

---

## 16. Test strategy matrix

| Layer | Tooling | What must be covered |
|---|---|---|
| Unit (backend) | pytest | Services, permission checks, state machines (§5.2), `normalize_az`, eligibility, rate limiters, parity calculation |
| Integration (backend) | pytest + httpx + real Postgres/Redis (testcontainers/compose) | REST contracts, migrations up/down, partition creation job, search permission filtering, import idempotency |
| WebSocket | pytest-asyncio + test client | Auth ticket, authorization per event, persist-before-publish, reconnect backfill, membership revocation, exam-mode flip |
| Frontend unit | Vitest + Testing Library | Components, i18n formatting, optimistic message reconciliation, store logic |
| E2E | Playwright | Login → channel → send → reconnect; opt-in as guide → request → accept → resolve; exam mode; mobile viewport; keyboard-only flows |
| Visual regression | Playwright screenshots on `/design-system` + key screens (light/dark, 320/1440) | Prevent drift from §12 |
| Accessibility | axe-core in Playwright | No serious/critical violations on key screens |
| Load | k6 | Targets in §5.9 and Phase 4 |
| Security | Dependency audit, ZAP baseline in CI, external pen-test (Phase 4) | §14 items |

CI gate: lint + types + unit + integration + OpenAPI drift check + a11y smoke must pass for merge; E2E and visual regression run on PRs touching `apps/web`.

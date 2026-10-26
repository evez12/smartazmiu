# Pilot runbook

The SmartAzMİU pilot starts on **2027-02-22** with one faculty (milestone M2: at least 300 people signed in). This
runbook says what has to be true before the pilot opens, how the pilot is run day to day, how people get help and
give feedback, and what to do when something breaks. Roles are named, not people: fill in the contact table
before the pilot week and keep it current.

## 1. Contacts and roles

| Role | Responsibility during the pilot | Contact |
|---|---|---|
| Product owner | Scope, priorities, go/no-go, communication to the faculty | _to be filled_ |
| On-call developer | Incidents, deployments, data fixes, weekly triage | _to be filled_ |
| Dean's office (pilot faculty) | Registry data (groups, subjects, enrollments), first-line answers to students | _to be filled_ |
| University IT | Server, network, backups, Keycloak accounts | _to be filled_ |
| Support staff (`staff` role) | Answer the support channel, read the feedback list and reports | _to be filled_ |

On-call hours in the pilot: weekdays 08:30–18:00 Baku time. Outside them, only P1 incidents (section 6) are
handled.

## 2. Before the pilot opens (T-7 to T-1 days)

Work through the list in order and tick it in the pilot ticket.

1. **Infrastructure:** the stack runs with `make up` on the pilot server (4 vCPU, 8 GB, two API workers, §8);
   HTTPS certificate valid; `GET /readyz` returns 200; the worker container is healthy
   (`arq --check`); ClamAV has loaded its signatures (an upload in chat turns "Yoxlanılıb").
2. **Secrets:** `.env` on the server has production values for every secret (session secret, database, Redis,
   Keycloak admin, S3 keys, VAPID keys, SMTP); none is the development default. Sentry DSN set.
3. **Keycloak:** realm imported; every staff and admin account has two-step sign-in enrolled (D-018); test
   accounts (`e2e-…`, `load-…`) do not exist (`make load-down` if in doubt).
4. **Registry import** (staff, `/admin/imports`), in this order: faculties, specialties, subjects, semesters,
   teachers, groups, students, offerings, enrollments, rooms and buildings, schedule, schedule changes, week
   parity. Each file is checked row by row before it is applied. After the last import, the worker provisions
   channels within a minute; check that a student of the faculty sees their course, community, group and faculty
   channels.
5. **Support channel:** "SmartAzMİU dəstəyi" exists and every active person in the registry is a member
   (section 4); staff and admins appear as moderators.
6. **Backup:** take a manual database dump and copy it off the server (section 7); the automated job and the
   restore drill follow in a later sprint.
7. **Smoke test** with one real student, one teacher and one staff member: sign in, today's classes, a message in
   a course channel, a material upload by the teacher and its download by the student, an announcement to the
   group, the feedback form.
8. **Load check:** `make load` against the pilot server outside working hours (README, D-073) and record the
   result in the pilot ticket.
9. **Communication:** the dean's office sends the faculty an announcement with the sign-in address, what the pilot
   includes, where to ask (support channel) and how to give feedback (form).

**Go/no-go** on T-1 with the product owner: all items done, no open P1/P2 incidents.

## 3. Daily operation

- **Morning check (09:00):** `/readyz`, worker health, disk space on the database and object-storage volumes,
  Sentry for new errors, the open feedback list and the report list (`/admin/feedback`, `/admin/reports`).
- **Imports:** registry changes go through the import pipeline only; never edit academic data in the database.
  The worker re-syncs channel memberships after every import.
- **Deployments:** only after `make lint test` and the E2E suite are green on `main`; outside lecture hours
  (after 18:00 or before 08:00); announce in the support channel ten minutes before. The API keeps working
  through a worker restart; open sockets reconnect by themselves.
- **Accounts:** a person who cannot sign in is checked in Keycloak (exists, enabled, e-mail verified) and in the
  registry (imported, `active`). Grades, e-mail addresses and phone numbers are never sent in chat or in the
  support channel (§5.4).

## 4. Support channel

"SmartAzMİU dəstəyi" is a chat channel for questions about the platform. The provisioning job keeps every active
person of the registry (students and teachers) and every staff and admin account in it; staff and admins are its
moderators (D-074). It is for how-to questions and problem reports that others may share; personal matters go
through the feedback form, which only staff see.

- **Answer times:** within four working hours; a question that needs a developer gets an acknowledgement first
  ("Problemi qeydə aldıq, düzəliş üzərində işləyirik").
- **Tone:** formal-friendly "siz", short answers, no internal codes (§12.8).
- **Recurring questions** are collected weekly and turned into tour text, empty-state text or a help article.
- **Moderation:** deleting other people's posts and muting arrive with the moderator console in Sprint 10; until
  then off-topic or harmful posts are reported ("Şikayət edin") and handled on `/admin/reports`.

## 5. Feedback form

Everyone can open "Rəy bildirin" from the profile menu: a category (problem, suggestion, question, other), the
text, and optionally permission to be contacted. The page the person was on is attached automatically. Staff
read and close feedback on `/admin/feedback`.

- **Weekly triage** (Friday, product owner + on-call developer): every open item is closed with one of: fixed,
  planned (linked to a roadmap task), answered, not planned. Problems become issues on GitHub with steps to
  reproduce; personal data stays out of the issue.
- **Pilot metrics** reported weekly: active users (signed in in the last 7 days), messages per day, materials
  uploaded, feedback items opened/closed, incidents.

## 6. Incidents

| Severity | Examples | First response | Communication |
|---|---|---|---|
| P1 | Nobody can sign in; data shown to the wrong people; data loss | 30 minutes, any time | Announcement to the faculty, update every hour |
| P2 | Chat or uploads down for everyone; schedule wrong for a group | 2 working hours | Support channel post, update twice a day |
| P3 | A feature broken for some people; a visual defect | Next working day | Reply to the reporter |

Steps: confirm and record (time, scope, request ids from the error messages), contain (roll back the last
deployment if it is the cause), fix, verify, write a short post-incident note in the pilot ticket.

Known degraded modes (§13.5), which are not outages: if Redis B is down, chat keeps working through REST and
polling (no typing or presence); if object storage is down, text chat works and uploads are refused with a
message; if ClamAV is down, files wait in "Yoxlanılır" and are checked when it is back.

A suspected data leak (grades, contact details, a channel visible to non-members) is always P1 and is reported to
the product owner and university IT immediately.

## 7. Backups and rollback

- **Manual dump before the pilot and before each deployment:**
  `docker compose exec postgres pg_dump -U smartazmiu -Fc smartazmiu > smartazmiu-YYYYMMDD-HHMM.dump`, copied to
  the university backup store. Object storage is mirrored by university IT.
- **Rollback:** redeploy the previous image tag; migrations are reversible (`alembic downgrade -1`) but a
  downgrade that drops a table is only run after a fresh dump and with the product owner's agreement.

## 8. After the pilot

At the end of Sprint 7, a pilot review: metrics against M2, top feedback themes, incidents, and the decisions
for the university-wide launch. The findings go into `docs/DECISIONS.md` and the roadmap.

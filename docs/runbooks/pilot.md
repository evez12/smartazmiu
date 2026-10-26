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
6. **Backup:** take a manual database dump, copy it off the server and run the restore drill once (section 8).
7. **Smoke test** with one real student, one teacher and one staff member: sign in, today's classes, a message in
   a course channel, a material upload by the teacher and its download by the student, an announcement to the
   group, the feedback form.
8. **Load check:** `make load` against the pilot server outside working hours (README, D-073, D-082) and record
   the result in the pilot ticket. It creates `load-…` test accounts in the real Keycloak and database for the
   length of the run, so it needs the product owner's agreement first, or runs on a staging copy (D-077).
9. **Monitoring:** `make monitoring` runs; the Grafana dashboard shows data and Prometheus shows no firing alert
   (section 10).
10. **Communication:** the dean's office sends the faculty an announcement with the sign-in address, what the
    pilot includes, where to ask (the "Dəstək" page and the support channel) and how to give feedback (form).

**Go/no-go** on T-1 with the product owner: all items done, no open P1/P2 incidents.

## 3. Daily operation

- **Morning check (09:00):** the on-call checklist (section 9): dashboard and alerts, `/readyz`, worker health,
  disk space, Sentry, the open feedback and report lists (`/admin/feedback`, `/admin/reports`), the last dump.
- **Imports:** registry changes go through the import pipeline only; never edit academic data in the database.
  The worker re-syncs channel memberships after every import.
- **Deployments:** as in section 7. The API keeps working through a worker restart; open sockets reconnect by
  themselves.
- **Accounts:** a person who cannot sign in is checked in Keycloak (exists, enabled, e-mail verified) and in the
  registry (imported, `active`). Grades, e-mail addresses and phone numbers are never sent in chat or in the
  support channel (§5.4).

## 4. Support channel

"SmartAzMİU dəstəyi" is a chat channel for questions about the platform. The provisioning job keeps every active
person of the registry (students and teachers) and every staff and admin account in it; staff and admins are its
moderators (D-074). The "Dəstək" page (`/support`, in the profile menu, D-081) leads to it and to the feedback
form. It is for how-to questions and problem reports that others may share; personal matters go through the
feedback form, which only staff see.

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

## 7. Deploying

1. **Check the calendar.** No production release during the January and June exam sessions (D-047): work is
   released to staging only, and hotfixes for P1/P2 incidents are the one exception (product owner agrees in the
   pilot ticket first).
2. **Check `main`.** The CI run of the commit is green (lint, tests, E2E, `make up` on a fresh checkout).
3. **Announce** in the support channel ten minutes before; deploy outside lecture hours (after 18:00 or before
   08:00).
4. **Back up** (section 8) and note the current image tags (`docker compose images`) in the pilot ticket.
5. **Release:** `git pull --ff-only` on the server, then `make up`. The `migrate` service applies migrations before
   the API starts; `make up` waits until every service is healthy.
6. **Verify:** `curl -fsS https://<host>/nginx-health`, `docker compose exec api python -c "import
   urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/readyz').read())"`, the worker is healthy
   (`docker compose ps worker`), and the smoke test of section 2, step 7, takes two minutes with one test account.
   On Grafana (section 10) the WebSocket connections return to their previous level within five minutes.

## 8. Backups, restore drill and rollback

- **Manual dump before the pilot and before each deployment:**
  `docker compose exec postgres pg_dump -U smartazmiu -Fc smartazmiu > smartazmiu-YYYYMMDD-HHMM.dump`, copied to
  the university backup store. Object storage is mirrored by university IT.
- **Restore drill** (once before the pilot, on a separate machine, never on the pilot server): `make reset && make
  infra`, then `docker compose exec -T postgres pg_restore -U smartazmiu -d smartazmiu --clean --if-exists <
  smartazmiu-….dump`, then `make up` and sign in with a test account. Record how long it took in the pilot
  ticket. The automated nightly backup and the scheduled drill are a later sprint (§8); until then this is manual.
- **Rollback:** check out the previous release commit and run `make up`. Migrations are reversible
  (`docker compose run --rm migrate alembic downgrade -1`), but a downgrade that drops a table or column runs only
  after a fresh dump and with the product owner's agreement: it removes data.

## 9. On-call checklist

At the start of an on-call shift:

- [ ] Grafana "SmartAzMİU pilot" dashboard open; no alert firing in Prometheus (`/alerts`).
- [ ] `/readyz` returns 200; `docker compose ps` shows every service healthy.
- [ ] Disk use of the `postgres-data` and `s3-data` volumes below 80 %.
- [ ] Sentry: no new error group since the last shift, or each new one has an owner.
- [ ] `/admin/feedback` and `/admin/reports`: nothing open older than one working day.
- [ ] The last dump is less than 24 hours old.

When an alert fires, open its section below, follow it, and record what you saw and did in the pilot ticket.

### Re-running provisioning and imports

- A corrected registry file is imported again on `/admin/imports`; imports are idempotent, so the same file twice
  changes nothing. Never edit academic data in the database.
- Channel memberships and announcement audiences follow the registry by themselves: every import wakes both jobs
  at once, and the worker also runs `provision_channels` every minute and `sync_audiences` every five minutes
  (D-048, D-061). Nothing has to be started by hand; if memberships are still wrong after five minutes, the
  worker is unhealthy (see "Job queue lagging") or the registry data is wrong (check the import report).

### Revoking a session

For a lost device or a compromised account (P1 if someone else may be signed in):

1. Keycloak admin console → realm `smartazmiu` → Users → the person → Sessions → **Sign out** (all sessions).
   Their refresh token stops working: the web session ends at the next refresh, at the latest when the access
   token expires (15 minutes), and open chat sockets are closed at the same moment (the ticket carries the token's
   expiry, D-062).
2. If the account itself is compromised, also switch **Enabled** off and reset the password and the second factor
   with the person present; switch it on again afterwards.
3. Record the time and the request ids involved in the pilot ticket; check the audit log (`/admin/audit`) for what
   the account did.

## 10. Monitoring and alerts

`make monitoring` starts Prometheus (127.0.0.1:9090) and Grafana (127.0.0.1:3001, user `admin`, password
`GRAFANA_ADMIN_PASSWORD` in `.env`) next to the stack; reach them through an SSH tunnel, never publicly. Prometheus
scrapes the API's internal `/metrics` every 15 s; the dashboard "SmartAzMİU pilot" shows open WebSocket
connections, messages per second, send errors by code, the job queue (depth and lag), the scan queue and rejected
uploads. Metric labels carry transports, error codes and job kinds only, never a person, channel or file (D-080).
The rules live in `infra/prometheus/alerts.yml`.

### API down

`up{job="api"} == 0` for two minutes. Check `docker compose ps api` and `docker compose logs --tail=200 api`. A
failed migration keeps the API from starting (`docker compose logs migrate`): roll back (section 8). If Postgres is
down, everything is down: P1.

### Chat send failures

More than 1 % of sends fail on the server (`internal`, `chat.unavailable`, `chat.realtime_unavailable`,
`chat.attachments_unavailable`). The "Send errors" panel shows which code. `chat.realtime_unavailable` means Redis
B is unreachable: clients fall back to REST by themselves (§13.5); restart `redis-cache`. `chat.unavailable` and
`internal` point at Postgres or a bug: Sentry has the stack trace with the request id. P2.

### WebSocket connections dropped

Open connections fell by more than half in five minutes. Expected right after a deployment (clients reconnect within
a minute); otherwise check nginx (`docker compose logs nginx`) and the API logs for `socket_closed` bursts. If
clients cannot reconnect, chat still works through REST; P2 if it lasts more than 15 minutes.

### Job queue lagging

The oldest due job has waited more than two minutes, or the queue cannot be read (Redis A down). Notifications,
scans and channel provisioning are late; nothing is lost, because work is stored before it is queued. Check
`docker compose ps worker redis` and `docker compose logs --tail=200 worker`; restart the worker. Redis A down also
stops sign-in sessions and WebSocket tickets: P1.

### Scan backlog

More than 50 uploads waiting, or any scan postponed, for 15 minutes. ClamAV is usually still loading its
signatures (after a restart, one to three minutes) or storage is unreachable. Check `docker compose ps clamav s3`;
files stay in "Yoxlanılır" and are checked once both are back. Text chat is unaffected (§13.5). P3, or P2 after an
hour.

### Infected upload

ClamAV rejected a file. Nothing to undo: the file was never downloadable, the uploader has an in-app notice, and
the purge job deletes the object within 30 minutes (D-068, D-071). Do: find the upload in the worker log
(`attachment_rejected` or `material_infected`, with the id); if the same account uploads infected files
repeatedly, or the signature is not a test file (EICAR), tell university IT the account and time so the person's
device can be checked, and consider revoking the session (above). Never download or forward the file.

## 11. After the pilot

At the end of Sprint 7, a pilot review: metrics against M2, top feedback themes, incidents, and the decisions
for the university-wide launch. The findings go into `docs/DECISIONS.md` and the roadmap.

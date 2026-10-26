# SmartAzMİU

Web platform (responsive + PWA) for AzMİU students, teachers and staff: schedule, materials, events and the
subject chat with cross-cohort mentorship. The product spec is [docs/ROADMAP.md](docs/ROADMAP.md); decisions
that refine it are logged in [docs/DECISIONS.md](docs/DECISIONS.md).

## Quick start

Requirements: Docker, GNU make, Git Bash (on Windows), [uv](https://docs.astral.sh/uv/) and pnpm 12.

```bash
git clone https://github.com/evez12/smartazmiu.git && cd smartazmiu
make install   # creates .env with local secrets, installs dependencies and git hooks
make up        # builds and starts the full stack at http://localhost
```

For day-to-day work run the infrastructure in Docker and the apps natively:

```bash
make infra     # postgres, two redis instances, s3, clamav, keycloak, mailpit
make migrate && make seed      # schema, sample groups 764a1/765a1/765a2, campus and timetable
make dev-api                   # http://localhost:8000
make dev-web                   # http://localhost:3000 (second terminal)
make dev-worker                # notifications, audience sync, chat channels (third terminal)
```

`make help` lists every target.

### Test users

Keycloak seeds seven made-up users that share the password in `.env` (`KEYCLOAK_TEST_USER_PASSWORD`):

| Username | Role |
|---|---|
| `aysel.mammadova`, `ramin.aliyev` | student |
| `nigar.ismayilova` | student + moderator |
| `leyla.hasanova` | teacher |
| `elvin.quliyev` | staff (asks for an authenticator app on first sign-in) |
| `tural.babayev` | admin (asks for an authenticator app on first sign-in) |
| `kanan.babayev` | student + moderator, plus Keycloak's default roles (sign-in regression test) |

Aysel, Ramin (765a2), Nigar (765a1) and Leyla (teacher) are also part of the sample roster in
`infra/seed/academics/`; after `make seed`, or after importing those files, their dashboards show their group and
subjects, **Cədvəl** (`/schedule`) their 2026 Payız timetable (try the week of 26 October 2026 for changes and
9 November for holiday cancellations) and **Kampus xəritəsi** (`/map`) the rooms.

### Administration

Administrators manage users at **İstifadəçilər** (`/admin/users`): role changes go to Keycloak through the
`smartazmiu-api-admin` service account and are written to the **Audit jurnalı** (`/admin/audit`). If your local
Keycloak was created before this client existed, run `make reset` (or import the client), because Keycloak only
imports the realm file into an empty database. The same applies to the `smartazmiu-web` role scope and the
`kanan.babayev` user (D-037).

### Academic data import

Staff and administrators import academic data at **Məlumat idxalı** (`/admin/imports`): one CSV or XLSX file per
kind, in the order faculties, specialties, subjects, semesters, teachers, groups, students, offerings, enrollments,
then buildings, floors, rooms, week parity, schedule and schedule changes. Each kind has a downloadable template; a
file is validated first and applied only after confirmation. The sample files in `infra/seed/academics/` show the
expected format. Rules: [docs/DECISIONS.md](docs/DECISIONS.md) D-029–D-031 (registry), D-041 (timetable: a schedule
file replaces the timetable of the offerings it lists, from the day it is applied) and D-042 (campus).

### Announcements, events and notifications

Staff publish **Elanlar** (`/announcements`) and **Tədbirlər** (`/events`) to the whole university, a faculty, a
specialty, a group or a course offering. People who join the audience later (a transfer, a late enrollment) receive
announcements that are still active and events that have not ended (D-050, D-051). Students register for events
and show the QR ticket from **Biletlərim** (`/events/tickets`); staff admit them at **Giriş qeydiyyatı** on the
event page by scanner, camera (where the browser can read QR codes) or name.

Notifications appear in the bell and at **Bildirişlər**; **Bildiriş ayarları** switches push and e-mail per topic
and sets quiet hours (23:00–08:00 Baku time by default, D-049). The `worker` service sends them: e-mail goes to
Mailpit locally (`http://localhost:8025`); Web Push needs a desktop Chrome, Edge or Firefox with notifications
allowed for the site (headless test browsers refuse them). Timetable changes for today or later notify the people
who have the class (D-052).

### Chat

**Çat** (`/chat`) lists the channels the registry gives each person (D-061): a course channel per offering
(students of its groups and its teachers), a community per subject (current students, no teachers), the group (with
its curator) and the faculty. The worker creates and syncs them after every import and once a minute; `make seed`
provisions the sample data directly. Course channels become read-only archives after their semester. Direct
messages start from a channel's member list and follow each person's `dm_policy` and blocks (D-063).

The browser keeps one WebSocket per tab (`/ws` behind nginx, `ws://localhost:8000/ws` natively), opened with a
one-use ticket from `POST /api/v1/ws/ticket` (ADR 0003). It carries messages, typing, presence, read markers,
membership changes and bell updates; without it the app sends through REST and polls (D-062, D-064). Message ids are
snowflakes and `messages` is partitioned by month (ADR 0002); who may post is decided by one function with reason
codes (ADR 0004). Try it with Aysel and Ramin in two browsers.

Messages can be edited or deleted for 15 minutes, answered in a thread (the third pane, `?thread=<id>`), reacted to
with eight fixed reactions and can mention members (`@` suggests them) or, for teachers and staff, `@channel`; the
bell header menu sets each channel's notification level and snooze (D-067). Files (images, PDF, DOCX, PPTX, ZIP up
to 25 MB) upload straight to object storage and become visible to others only after the worker has checked their
type and ClamAV has scanned them (D-068); ClamAV needs a minute or two and about 1.5 GB of memory to start.

### Pilot support

Everyone in the registry and every staff account is in the chat channel "SmartAzMİU dəstəyi", which staff
moderate; "Rəy bildirin" in the profile menu sends feedback that only staff see on `/admin/feedback` (D-074). How
the pilot is prepared and run is in [docs/runbooks/pilot.md](docs/runbooks/pilot.md).

### Materials

**Materiallar** (`/materials`) holds a catalogue per subject with a semester filter (D-071). Students of a subject
(also past ones) and its teachers read it; teachers upload for the semesters they teach, staff everywhere. Every
upload needs a copyright confirmation, becomes a new version and is downloadable only after the same scan as chat
files. Reports reach staff under "Şikayətlər → Materiallar", who can hide a material without deleting it. Try it
as Leyla Həsənova (upload to Statistika) and Aysel Məmmədova (read it).

## Architecture

A modular monolith: one FastAPI app and one Next.js app.

| Path | Contents |
|---|---|
| `apps/api` | FastAPI, SQLAlchemy 2 (async), Alembic. Domain code lives in `app/modules/<module>/`. |
| `apps/api/app/workers` | ARQ worker (same image as the API): notification delivery, audience sync, chat channel provisioning, message partitions, attachment scans and purges. |
| `apps/api/app/modules/chat` | Chat: provisioning, the authorisation policy, messages, the WebSocket gateway (`ws.py`, `hub.py`). |
| `apps/api/app/modules/materials` | Materials: catalogue access, versioned uploads, scanning, reports and hiding. |
| `apps/api/app/modules/feedback` | The pilot feedback form and the staff list. |
| `apps/web` | Next.js (App Router), TypeScript, Tailwind. Design tokens in `src/styles/tokens.css`. |
| `infra/` | nginx, Keycloak realm and login theme, Postgres init scripts, object-storage entrypoint. |
| `docs/` | Spec, decision log, ADRs, pilot runbook. |

Local services: Keycloak `http://localhost:8080`, Mailpit `http://localhost:8025`, S3 API `http://localhost:8333`,
ClamAV `localhost:3310`,
Postgres `localhost:5433`, Redis A (sessions, job queue, snowflake leases, WebSocket tickets) `localhost:6379`, Redis B
(cache, rate limits, presence, chat pub/sub) `localhost:6380` (D-053).

## Testing

```bash
make lint test     # linters, type checks, backend (pytest) and frontend (Vitest) tests
make e2e           # Playwright: user flows, accessibility, keyboard and mobile checks (needs the stack running)
make visual        # screenshot comparison in the pinned Linux Playwright image (Docker)
```

Backend tests run against the `smartazmiu_test` database in the Docker Postgres; `make test` starts the containers
it needs. After changing an API schema, run `make openapi` to regenerate the typed web client.

`make e2e` loads the sample data first and fails if a run leaves any seed table with a different row count: tests
remove what they import, using throwaway `e2e-…` accounts and `E2E-…` codes (D-040, D-045).

### Load test

The chat load test (D-073) signs throwaway accounts in through the real login flow and holds WebSockets open while
they send messages; k6 runs in Docker. With the stack running (API ideally as in production, two workers without
reload):

```bash
make load-up       # 500 Keycloak accounts load-NNNN and 20 private channels "Yük testi NN" (25 people each)
make load          # 1 000 sockets (two per account), 50 messages/s, 2 min ramp + 5 min hold; thresholds p95 < 300 ms
make load-down     # removes the accounts, channels and their messages
```

`LOAD_USERS`, `LOAD_CHANNELS`, `LOAD_SOCKETS`, `LOAD_RATE`, `LOAD_RAMP` and `LOAD_HOLD` change the shape. k6 fails
the run if delivery or acknowledgement p95 exceed 300 ms, fewer than 99 % of sockets connect, or the server
refuses ten or more events; `infra/load/summary.json` holds the numbers.

**Windows and Docker Desktop.** The k6 container runs with `--network host` and reaches the app, the API and Keycloak
on `localhost` (the sign-in redirects to Keycloak's public address `http://localhost:8080`). Docker Desktop only
shares the host's `localhost` with such containers when host networking is switched on (Settings > Resources >
Network > "Enable host networking", Docker Desktop 4.34 or later; apply and restart). With it off, setup fails with
`no login form for load-0001 (status 0)`. Check first, from the repository root:

```bash
docker run --rm --network host --entrypoint sh grafana/k6:1.3.0 -c "wget -q -T 5 -O /dev/null http://localhost:8080/realms/smartazmiu && echo reachable"
```

The native `make dev-api` and `make dev-web` servers must be running (or the API started with two workers, as in
production), because the defaults point at `localhost:3000` and `localhost:8000`.

**Against another server** (the pilot server, D-077): run `make load-up` and `make load-down` on a machine that can
reach that server's database and Keycloak admin API, and pass its public addresses to the run:

```bash
make load APP_URL=https://pilot.example.az WS_URL=wss://pilot.example.az/ws
```

`load-down` removes only e-mail addresses `load-…@smartazmiu.test`, Keycloak users whose name starts with `load-`
and private groups named "Yük testi …". Count them before and after (`select count(*) from users where email like
'load-%'`) and only run `load-up` on a shared database with the product owner's agreement.

## Adding a backend module

1. Create `apps/api/app/modules/<name>/` with `models.py`, `schemas.py`, `service.py`, `router.py` and `tests/`.
2. Register the router in `app/main.py`; models are discovered automatically for Alembic.
3. `make migration m="add <name>"`, review the generated file and make sure `downgrade()` reverses it.
4. Cover the module with tests (≥ 80 %) and check it against the edge-case catalogue (§13).

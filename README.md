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
make infra     # postgres, redis, s3, keycloak, mailpit
make migrate && make seed      # schema, sample groups 764a1/765a1/765a2, campus and timetable
make dev-api                   # http://localhost:8000
make dev-web                   # http://localhost:3000 (second terminal)
make dev-worker                # notification delivery and audience sync (third terminal)
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

## Architecture

A modular monolith: one FastAPI app and one Next.js app.

| Path | Contents |
|---|---|
| `apps/api` | FastAPI, SQLAlchemy 2 (async), Alembic. Domain code lives in `app/modules/<module>/`. |
| `apps/api/app/workers` | ARQ worker (same image as the API): notification delivery, audience sync. |
| `apps/web` | Next.js (App Router), TypeScript, Tailwind. Design tokens in `src/styles/tokens.css`. |
| `infra/` | nginx, Keycloak realm and login theme, Postgres init scripts, object-storage entrypoint. |
| `docs/` | Spec, decision log, ADRs. |

Local services: Keycloak `http://localhost:8080`, Mailpit `http://localhost:8025`, S3 API `http://localhost:8333`,
Postgres `localhost:5433`.

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

## Adding a backend module

1. Create `apps/api/app/modules/<name>/` with `models.py`, `schemas.py`, `service.py`, `router.py` and `tests/`.
2. Register the router in `app/main.py`; models are discovered automatically for Alembic.
3. `make migration m="add <name>"`, review the generated file and make sure `downgrade()` reverses it.
4. Cover the module with tests (≥ 80 %) and check it against the edge-case catalogue (§13).

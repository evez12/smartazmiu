# Decision log

Format per entry: date · context · options considered · decision · consequences.
Newest entries at the bottom. Spec references point to `docs/ROADMAP.md`.

---

## D-001 · 2026-10-24 · Example typo in Azerbaijani normalization spec

- **Context:** §5.7.1 illustrated diacritic-insensitive matching with `Ekonomik riyaziyyat ↔ Ekonomik riyaziyyat` (identical strings).
- **Options:** keep as is; replace with an example that actually differs in diacritics.
- **Decision:** example changed to `İqtisadi riyaziyyat ↔ Iqtisadi riyaziyyat` in the spec; `normalize_az` tests use it.
- **Consequences:** none beyond the test case.

## D-002 · 2026-10-24 · Primary key for `channel_reads`

- **Context:** §5.7 defines `channel_reads(channel_id, user_id, last_read_message_id, updated_at)` without a key.
- **Options:** surrogate id + unique index; composite primary key.
- **Decision:** `PRIMARY KEY (channel_id, user_id)`; read-marker writes are upserts that only move the marker forward.
- **Consequences:** one row per member per channel; concurrent tabs cannot move the marker backwards.

## D-003 · 2026-10-24 · Exam mode for subject communities

- **Context:** `exam_slots` belong to a `course_offering`, but a `subject_community` spans every offering (all groups) of the subject.
- **Options:** never lock communities; lock during any offering's exam slot (union of intervals); lock per group.
- **Decision:** the community is read-only (no attachments) during the union of all exam windows
  (`starts_at − 15 min → ends_at`) of every offering of that subject in the current semester. Overlaps merge, per §13.4.
- **Consequences:** communities may be locked for several separate windows in an exam session; the banner shows the
  current window's end time. Staff can still configure exam mode per subject (§5.2).

## D-004 · 2026-10-24 · Mentor requests without a named mentor

- **Context:** §5.2 allows `mentor_id = NULL` ("any eligible guide"), but the create guard checks the mentor's
  availability and `max_open_requests`, which cannot be evaluated without a mentor.
- **Options:** forbid NULL mentor; evaluate the guard at create time against all guides; defer the guard.
- **Decision:** when `mentor_id` is NULL the availability/capacity guard is skipped at creation and applied at
  `accept` to the accepting guide (inside the same row-locked transaction). The other create guards still apply.
- **Consequences:** an unaddressed request can be accepted only by an eligible, available guide below capacity.

## D-005 · 2026-10-24 · Authentication architecture (Keycloak + Next.js + FastAPI)

- **Context:** §4 requires Keycloak OIDC, a 15-minute JWT access token and a refresh token in an httpOnly cookie;
  §5.9 requires single-use WebSocket tickets; §14 requires CSRF protection for cookie-authenticated mutations.
- **Options:** browser-side OIDC (tokens in JS); backend-for-frontend (BFF) where the Next.js server runs the
  authorization-code + PKCE flow.
- **Decision:** BFF. The Next.js server performs the OIDC flow, keeps the refresh token in an encrypted httpOnly,
  `Secure`, `SameSite=Lax` cookie, and forwards the short-lived access token to FastAPI. FastAPI validates JWTs against
  Keycloak's JWKS (issuer, audience, expiry). WebSockets authenticate with a 60-second single-use ticket from
  `POST /api/v1/ws/ticket`. Mutating requests that rely on the session cookie carry a CSRF token.
- **Consequences:** no long-lived tokens are reachable from page JavaScript; FastAPI stays stateless for REST auth.

## D-006 · 2026-10-24 · Snowflake worker IDs with multiple API workers

- **Context:** `messages.id` is a snowflake BIGINT; several uvicorn workers and ARQ workers generate IDs.
- **Options:** static worker IDs from config; random IDs; leased IDs from Redis.
- **Decision:** each process leases a worker ID from Redis (`SET NX` with TTL, renewed periodically) at startup.
  The generator is monotonic within a process and refuses to issue IDs while the clock moves backwards.
- **Consequences:** Redis is required at API startup; ID-uniqueness and clock-regression behaviour is unit-tested (§13.2).

## D-007 · 2026-10-24 · Where visual regression tests run

- **Context:** §16 requires Playwright screenshot tests; font rendering differs between Windows and Linux, so
  baselines produced on the Windows dev box would fail in CI.
- **Options:** per-OS baselines; run screenshot tests only in the official Linux Playwright Docker image.
- **Decision:** visual regression runs only inside the pinned Linux Playwright image (locally via `make` and in CI).
  Functional E2E tests may run natively.
- **Consequences:** one set of baselines; updating baselines requires Docker.

## D-008 · 2026-10-24 · Phase 0 (discovery & design)

- **Context:** Phase 0 consists mostly of human activities (interviews, surveys, Figma, stakeholder sign-off).
- **Options:** block engineering on Phase 0; proceed with engineering and record technical ADRs.
- **Decision:** engineering starts at Sprint 1. The technical ADRs listed in Phase 0 are written in `docs/adr/` as
  the relevant code lands. Non-engineering Phase 0 items remain unticked for the product owner.
- **Consequences:** UI follows §12 directly instead of a Figma design system until one exists.

## D-009 · 2026-10-24 · Local development environment

- **Context:** Windows 11 dev box; the original folder name contained a non-ASCII `İ`, which breaks some Python,
  Node and Docker tooling. `make` and `pnpm` were not installed.
- **Options:** everything in Docker; everything native; infra in Docker with native app processes.
- **Decision:** repo lives at the ASCII path `C:\Users\User\Projects\smartazmiu`. Infra services (postgres, redis,
  minio, keycloak, mailpit) run in Docker Compose; `api` and `web` run natively during development. `make up` still
  starts the full stack (including `api`, `web`, `nginx`) in Docker. A single GNU `Makefile` (winget
  `ezwinports.make` 4.4.1) is the only task runner. JavaScript package manager: pnpm 12.15.0.
- **Consequences:** Makefile recipes must work in both Git Bash on Windows and Linux CI.

## D-010 · 2026-10-24 · Data sources not yet available

- **Context:** no roster file, schedule source format or information about an existing AzMİU identity provider.
- **Options:** wait; build against realistic synthetic data and local identity.
- **Decision:** use realistic made-up Azerbaijani seed data (groups like `765a2`, real-looking names, subjects,
  rooms) and local Keycloak test users. Import formats are designed as documented CSV/XLSX templates and adapted
  once real files arrive.
- **Consequences:** import adapters may need changes when real source formats are provided.

## D-011 · 2026-10-24 · Commit trailers

- **Context:** product owner instruction.
- **Decision:** commits and PR descriptions never include `Co-Authored-By` or "Generated with" trailers.
- **Consequences:** none.

## D-012 · 2026-10-24 · GitHub remote and branch workflow

- **Context:** the product owner created `github.com/evez12/smartazmiu` and asked for all code to be pushed there,
  split over several branches. Previously no remote existed.
- **Options:** commit on `main`; one long-lived sprint branch; several scoped feature branches.
- **Decision:** each group of related Sprint 1 tasks gets its own branch (`feat/scaffold`, `feat/api-auth-rbac`,
  `feat/design-system`, `feat/app-shell`, `ci/github-actions`). A branch is merged into `main` with `--no-ff` once
  `make lint test` passes, and both the branch and `main` are pushed. CI runs on GitHub from now on.
- **Consequences:** history shows one merge per task group; PRs can be opened later from the pushed branches.

## D-013 · 2026-10-24 · S3-compatible object storage instead of the MinIO image

- **Context:** §4 names MinIO. Official MinIO container images are no longer publicly available (Docker Hub
  repository removed; `quay.io/minio/minio` requires authentication), so a fresh clone could not run `make up`.
- **Options:** build MinIO from source in our Dockerfile; pin an unofficial mirror; use another S3-compatible
  server (SeaweedFS, Garage, RustFS).
- **Decision:** SeaweedFS `4.48` (`weed server -s3`), the most mature of the alternatives, as the compose service
  `s3`. Application code only uses the S3 API (presigned URLs), so the server can be swapped without code changes.
  Credentials are rendered from environment variables at container start.
- **Consequences:** documentation says "S3-compatible storage" where the spec says MinIO. The production object store
  (MinIO, Ceph or another S3 service) remains an infrastructure choice for Phase 4.

## D-014 · 2026-10-24 · Pinned toolchain and dependency versions

- **Context:** §4 requires exact versions at scaffold time, recorded here. Lockfiles (`apps/api/uv.lock`,
  `apps/web/pnpm-lock.yaml`) pin transitive dependencies.
- **Decision:** latest stable releases on 2026-10-24, with two deliberate exceptions:
  TypeScript `6.0.3` (not 7.x — `typescript-eslint` 8.72 supports `<6.1`) and ESLint `9.39.5` (not 10.x —
  `eslint-plugin-react`, used by `eslint-config-next`, supports `^9.7` at most).

  | Area | Versions |
  |---|---|
  | Runtimes | Python 3.12 (image `python:3.12.15-slim-bookworm`), Node 24 (image `node:24.22.1-alpine3.24`), uv 0.11.16, pnpm 12.15.0 |
  | Images | `postgres:16.15-alpine3.24`, `redis:7.4.11-alpine`, `quay.io/keycloak/keycloak:26.8.1`, `chrislusf/seaweedfs:4.48`, `axllent/mailpit:v1.32.0`, `nginx:1.30.6-alpine` |
  | API | fastapi 0.162.0, uvicorn 0.54.0, sqlalchemy 2.1.6, asyncpg 0.32.0, alembic 1.20.1, pydantic 2.14.1, pydantic-settings 2.16.1, pyjwt 2.15.1, redis 8.1.0, structlog 26.1.0, sentry-sdk 2.73.0, httpx 0.28.1 |
  | API dev | pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0, ruff 0.17.2, mypy 2.4.0, pre-commit 4.7.0, asgi-lifespan 2.1.0 |
  | Web | next 16.4.3, react / react-dom 19.3.1, tailwindcss + @tailwindcss/postcss 4.3.3, radix-ui 1.8.1, class-variance-authority 0.7.1, clsx 2.1.1, tailwind-merge 3.7.0, lucide-react 1.61.0, next-intl 4.14.9, next-themes 0.4.6, @fontsource/ibm-plex-sans + ibm-plex-mono 5.3.0, openid-client 6.8.8, jose 6.2.13, openapi-fetch 0.17.0, server-only 0.0.1, @sentry/nextjs 11.9.0 |
  | Web dev | typescript 6.0.3, eslint 9.39.5, eslint-config-next 16.4.3, prettier 3.9.10, prettier-plugin-tailwindcss 0.8.1, vitest 5.0.5, @vitejs/plugin-react 6.1.2, jsdom 30.1.3, @testing-library/react 16.3.3, @testing-library/jest-dom 7.0.1, @testing-library/user-event 14.6.8, @playwright/test 1.64.1 (image `mcr.microsoft.com/playwright:v1.64.1-noble`), @axe-core/playwright 4.14.0, openapi-typescript 7.13.0 |
  | Hooks / CI | pre-commit-hooks v6.0.0, ruff-pre-commit v0.17.2 |
  | Added in Sprint 2 | API: openpyxl 3.1.5, python-multipart 0.0.32, tzdata 2026.5, boto3 1.43.118, pillow 13.0.0; API dev: types-openpyxl 3.1.5.20261017, boto3-stubs[s3] 1.43.118; web: @tanstack/react-query 5.104.5 |

- **Consequences:** later sprints add dependencies to this table when they introduce them.

## D-015 · 2026-10-24 · Host ports for local infrastructure

- **Context:** the dev box runs a native PostgreSQL service on port 5432.
- **Decision:** the Docker Postgres is published on host port `5433`. Every published port is overridable in `.env`.
- **Consequences:** native processes connect to `localhost:5433`; containers still use `postgres:5432`.

## D-016 · 2026-10-24 · Source of truth for global roles

- **Context:** §2 needs `users`, `roles`, `permissions` tables and Keycloak test users with roles; §14 needs 2FA for
  staff/admin, which Keycloak can only enforce if it knows who is staff. The spec does not say which side owns
  role membership.
- **Options:** database owns roles (Keycloak only authenticates); Keycloak owns role membership and the API mirrors it.
- **Decision:** Keycloak realm roles are authoritative for global role membership. On every authenticated request
  the API provisions the user by `sub` and mirrors `realm_access.roles` (only catalogue roles; never `guest`) into
  `user_roles`, writing only when something changed. The database owns role → permission bundles, and
  `require_permission(code)` checks the union over the user's roles.
- **Consequences:** the Sprint 2 admin "role assignment" screen must write through the Keycloak admin API, not only
  the database. A role change takes effect at the next access token (≤ 15 min).

## D-017 · 2026-10-24 · Permission catalogue grows with features

- **Context:** Sprint 1 introduces RBAC but no endpoint that needs a specific permission yet.
- **Options:** seed a speculative permission list now; seed permissions in the migration of the feature that uses them.
- **Decision:** migration `0001` seeds the six global roles only. Each later feature migration adds its permissions
  and role grants. `require_permission` is covered by tests that create their own permission rows.
- **Consequences:** `/api/v1/me` returns an empty `permissions` list in Sprint 1.

## D-018 · 2026-10-24 · Two-factor sign-in for staff and administrators

- **Context:** §14 requires 2FA for staff/admin from Sprint 1; the product owner chose to enforce it now.
- **Decision:** a custom browser flow (`smartazmiu browser`) runs password authentication followed by a conditional
  TOTP step. The condition checks the realm role `mfa_required`, which the `staff` and `admin` roles include as
  composites, so anyone granted those roles later is covered automatically. Users without TOTP are sent to enrolment.
  Refresh tokens rotate with reuse detection (`revokeRefreshToken`, max reuse 0); brute-force protection is on.
- **Consequences:** testing as `elvin.quliyev` (staff) or `tural.babayev` (admin) needs an authenticator app.
  `/readyz` does not check Keycloak: the API keeps serving with cached signing keys during a short IdP outage.

## D-019 · 2026-10-24 · Keycloak login theme

- **Context:** the login pages are served by Keycloak; the stock theme violates §12. The product owner chose a
  minimal custom theme.
- **Decision:** theme `smartazmiu` extends the unstyled `base` theme with our own `template.ftl`, a §12 stylesheet
  (tokens mirrored from `tokens.css`, light/dark via `prefers-color-scheme`), self-hosted IBM Plex Sans (Latin +
  Latin Ext, which together cover every Azerbaijani letter), Lucide icons as CSS masks, and Azerbaijani overrides of
  the keys these screens show. The only supported login locale is `az` for now.
- **Consequences:** if AzMİU provides its own SSO, these pages are replaced. New Keycloak screens (e.g. password
  reset, once enabled) need their message keys reviewed.

## D-020 · 2026-10-24 · Local test users

- **Context:** no real identities exist yet (D-010).
- **Decision:** the realm seeds six made-up users sharing one password from `.env` (`KEYCLOAK_TEST_USER_PASSWORD`,
  generated by `make env`): `aysel.mammadova`, `ramin.aliyev` (student), `nigar.ismayilova` (student + moderator),
  `leyla.hasanova` (teacher), `elvin.quliyev` (staff), `tural.babayev` (admin). E-mails use the reserved `.test` TLD.
- **Consequences:** the realm file contains no secrets; Keycloak substitutes `${...}` placeholders from the
  container environment at import.

## D-021 · 2026-10-25 · Contrast of control borders and the modal backdrop

- **Context:** §12.2 requires 3:1 for UI borders, but the specified `--border-strong` reaches only 1.85:1 (light)
  and 1.77:1 (dark) against the surfaces, so inputs drawn with it would fail WCAG 1.4.11. The spec also gives no
  backdrop colour for dialogs.
- **Options:** darken `--border-strong` (changes every divider); add a dedicated control-border token.
- **Decision:** the §12.2 values stay unchanged. A new token `--border-control` (`#858E9B` light, `#5E6A79` dark —
  the lightest blends of `--border-strong` toward `--text-muted` that reach 3:1 on every surface) outlines inputs,
  selects, checkboxes, radios, switches and secondary buttons. `--backdrop` dims the page behind dialogs in both
  themes. The contrast unit test covers both.
- **Consequences:** `--border` and `--border-strong` remain decorative dividers only.

## D-022 · 2026-10-25 · Shapes that the 6 px radius rule does not cover

- **Context:** §12.2 allows nothing rounder than 6 px except avatars.
- **Decision:** radio buttons and their dots are circular, because the shape is how users tell them from checkboxes.
  Switches are rectangular (4 px), which keeps them consistent with the other controls. The design-rules test
  allows `rounded-full` and fails on any other radius above 6 px.
- **Consequences:** presence dots (Sprint 5) follow the same circular exception.

## D-023 · 2026-10-25 · Font delivery and internal design-system page

- **Context:** §12.3 requires self-hosted IBM Plex with Latin, Latin Extended and Cyrillic; Azerbaijani needs both
  the Latin (`ı`, `ç`, `ö`, `ü`) and Latin Extended (`ə`, `İ`, `ş`, `ğ`) subsets.
- **Decision:** fonts come from the pinned `@fontsource` packages and are bundled by Next.js (no runtime request to
  Google). Sans ships 400/500/600 for Latin, Latin Extended and Cyrillic; Mono ships 400. `/design-system` returns
  404 unless `DESIGN_SYSTEM_ENABLED=true` (enabled in local `.env`, off by default elsewhere).
- **Consequences:** the glyph specimen and an e2e check verify every weight; visual baselines cover each section.

## D-024 · 2026-10-25 · App shell slots for features that do not exist yet

- **Context:** §12.4 puts global search and a notifications bell in the top bar, and §12.6 lists five bottom tabs
  (Ana səhifə, Cədvəl, Çat, Bildirişlər, Profil). In Sprint 1 only the dashboard exists.
- **Options:** render all entries as dead links or "coming soon" pages; show only what works.
- **Decision:** navigation is data-driven (`features/shell/nav.ts`); only implemented sections are listed, in both
  the sidebar and the tab bar. Search, the bell and the remaining tabs are added by the sprints that build them
  (search: Sprint 10, notifications: Sprint 4, schedule: Sprint 3, chat: Sprint 5, profile: Sprint 2). The profile
  menu holds the theme choice and sign-out.
- **Consequences:** in Sprint 1 the tab bar has a single entry. No placeholder pages exist.

## D-025 · 2026-10-25 · Browser-side API calls and browser error reporting

- **Context:** D-005 describes the Next.js server forwarding access tokens to the API. Sprint 1 pages fetch all
  data during server rendering; nothing in the browser calls the API yet. §7 asks for Sentry on the frontend too.
- **Decision:** the typed client (`lib/api/server.ts`, generated from OpenAPI by `make openapi`) is used on the
  server only. The same-origin `/api/v1/*` proxy for browser requests, with CSRF checks, is added with the first
  feature that needs client-side mutations (Sprint 2 profile). Server-side errors go to Sentry when `SENTRY_DSN` is
  set; browser reporting needs a public DSN and a CSP `connect-src` entry and is scheduled with pilot hardening
  (Sprint 6).
- **Consequences:** no unused proxy code ships in Sprint 1. Sign-out is the only cookie-authenticated mutation; it
  checks the per-session CSRF token embedded in the form and the `Origin` header.

## D-026 · 2026-10-25 · Session cookies and token refresh in the web server

- **Context:** tokens must not be readable by page JavaScript (D-005); Keycloak access tokens are ~1.2 KB, refresh
  tokens ~0.8 KB, and refresh tokens rotate with reuse detection (D-018).
- **Decision:** two encrypted httpOnly cookies: `sa_session` (refresh token, subject, CSRF token; lifetime = Keycloak
  session idle timeout) and `sa_access` (access token; lifetime = token lifetime). `proxy.ts` refreshes the access
  token when it has under 60 s left and passes the new cookie both to the page render and the browser. Concurrent
  refreshes of the same refresh token share one grant inside the process, so parallel requests do not trip reuse
  detection. Sign-out ends the Keycloak session through the back-channel logout endpoint (no confirmation page).
- **Consequences:** with several web replicas a rare parallel refresh across replicas can sign a user out; sticky
  sessions or a shared refresh lock is revisited before multi-replica deployment (Phase 4).

## D-027 · 2026-10-25 · Continuous integration

- **Context:** Sprint 1 requires CI for lint, type checks, tests, image builds and an OpenAPI client drift check;
  §14 adds dependency scanning and §16 an accessibility smoke test and visual regression.
- **Decision:** one workflow (`.github/workflows/ci.yml`) with parallel jobs that call the same `make` targets
  developers use: `api` (ruff, mypy, pytest with the 80 % coverage gate against compose Postgres/Redis), `web`
  (eslint, prettier, tsc, Vitest incl. contrast and design-rule guards, production build), `openapi`
  (`make openapi-check`), `audit` (pip-audit 2.10.1 and `pnpm audit --audit-level high`), `images` (Buildx with
  GitHub cache), `e2e` (`make up` from a fresh `.env`, then the Playwright suite through nginx, i.e. the Sprint 1
  acceptance path) and `visual` (`make visual` in the pinned Playwright image). Dependabot opens weekly grouped
  updates for uv, npm, GitHub Actions, Dockerfiles and compose images. Actions are pinned to exact release tags.
- **Consequences:** E2E and visual jobs run on every push and pull request rather than only for `apps/web`
  changes, because Sprint 1 auth spans the API, Keycloak and the web app; this can be narrowed with path filters
  once the suite grows.

## D-028 · 2026-10-25 · Sprint 1 review outcome

- **Context:** the product owner reviewed Sprint 1.
- **Decision:** D-013, D-016, D-018, D-021, D-024 and D-025 are approved. D-016 is approved with an addition:
  the `permissions` table stays in our database, and **every role change is written to `audit_logs`**, both
  changes mirrored from the identity provider (`user.roles_synced`, actor = system) and changes made by an
  administrator (`user.roles_changed`, Sprint 2 admin).
- **Consequences:** a user's first sign-in writes one `user.roles_synced` entry (roles added from nothing).

## D-029 · 2026-10-25 · Linking imported people to sign-in accounts (product owner decision)

- **Context:** academic imports create students and teachers before they ever sign in; Keycloak only knows them
  once they do. The spec does not say how the two records meet. Touches authentication, so the product owner
  was asked.
- **Options:** match by verified e-mail; match by a university-ID claim provided by the identity provider.
- **Decision:** by **verified e-mail**. On a first sign-in whose token has `email_verified = true` and an
  e-mail equal to an imported person without a subject, that record gets the token's subject
  (`user.account_linked` in the audit log). Unverified e-mails and records already linked to another subject are
  never claimed (`auth.identity_conflict`). The other direction works the same: an import row whose e-mail
  belongs to someone who signed in before the import attaches the registry record to that account; an e-mail
  owned by a person with a *different* university ID is rejected (§13.1). Field ownership: the registry
  (import) owns names, university ID, group, person type and status; after linking, the identity provider owns
  the e-mail.
- **Consequences:** `users.idp_subject` is nullable. If the real AzMİU SSO cannot guarantee verified,
  institution-managed e-mails, switch to a university-ID claim.

## D-030 · 2026-10-25 · Academic data model details

- **Context:** §5.7 lists `course_offerings(…, academic_group_id, teacher_id)`, but §13.1 requires one offering
  for several groups (joint lectures, electives) and several or replaced teachers.
- **Decision:** `course_offering_groups` and `course_offering_teachers` link tables replace the two columns. An
  offering's natural key is `(subject, semester, code)`; the code defaults to the group code, or the sorted group
  codes joined with `+` for joint offerings. Semesters store calendar dates (`starts_on`, `ends_on`) and `year`
  is the calendar year the term starts in (2026 Payız, 2027 Yaz). Enrollments carry a result only when
  completed (database check), so `passed`/`grade` cannot exist for active or dropped enrollments. Users gain
  `university_id` (stable registry key), `person_type` (`student`/`teacher`, independent of RBAC roles),
  `academic_group_id` and a `normalize_az`-folded `search_key`.
- **Consequences:** the chat provisioning job (Sprint 5) computes channel membership as the union of an
  offering's groups and teachers.

## D-031 · 2026-10-25 · Academic import pipeline

- **Context:** §6.1 requires a dry-run preview, per-row errors, a transactional idempotent apply keyed by natural
  keys, encoding detection with override and downloadable error reports; §13.5 forbids silent guessing.
- **Decision:**
  - One CSV/XLSX template per entity kind with English `snake_case` headers, imported in a fixed order
    (faculties → specialties → subjects → semesters → teachers → groups → students → offerings → enrollments).
    Term values accept Azerbaijani and English, case- and diacritic-insensitively (`Payız`, `payiz`, `fall`).
  - Upload validates without writing and stores the file's cells for at most 24 hours. Apply re-runs the same
    code path with writes inside one transaction and a global advisory lock; any problem at apply time (data
    changed since the preview) rolls everything back and marks the import `failed`. Files with any error cannot be
    applied at all: imports are all-or-nothing per file. Applying twice returns the first result.
  - Rows missing from a file are never deleted or changed; dropping an enrollment is an explicit
    `status = dropped`. An offering row's group and teacher lists replace the stored ones.
  - Errors are stored as `(row, column, code)` without cell values (no personal data in error records); the
    first 1 000 are kept. The web app renders the codes in Azerbaijani and builds the CSV report in the browser.
  - CSV encoding: UTF-8 (with or without BOM) is detected exactly; otherwise Windows-1251 vs Windows-1254 by
    the share of high bytes. A non-UTF-8 result is shown as a warning and can be overridden. Because cp1254 has
    no `ə`, a `?` inside a word is reported as `invalid_characters`. Excel serial dates and merged cells are row
    errors. Files are limited to 5 MB and 20 000 rows and processed in the request; ARQ is introduced with the
    first job that needs it.
  - Sample data for groups 764a1, 765a1 and 765a2 (İqtisadiyyat, made-up people) lives in
    `infra/seed/academics/` and loads through the same pipeline with `make seed`.
- **Consequences:** real roster files will need column mapping or conversion to the templates (D-010).

## D-032 · 2026-10-25 · Browser calls and client state

- **Context:** D-025 scheduled the same-origin proxy for the first client-side mutation; §4 lists TanStack Query.
- **Decision:** `app/api/v1/[...path]` forwards browser calls to the API with the access token from the
  httpOnly cookie. Mutations need the session's CSRF token in `X-CSRF-Token` and, when present, a same-origin
  `Origin`. Path segments are re-encoded and dot segments refused. Pages read data in server components;
  TanStack Query handles client mutations (no automatic retries) followed by `router.refresh()`.
- **Consequences:** page JavaScript never holds a token; client caching of reads is added when chat needs it.

## D-033 · 2026-10-25 · Profile photos

- **Context:** §5 Sprint 2 asks for photo upload; §14 requires content checks, size limits, virus scanning before
  availability, randomised keys and no public bucket access. ClamAV is scheduled with attachments (Sprint 6).
- **Options:** presigned upload and serve after a later scan; upload through the API and re-encode.
- **Decision:** the API accepts JPEG, PNG or WebP up to 5 MB (format read from the content, not the name), refuses
  images over 40 megapixels before decoding, applies the EXIF rotation, crops to a centred 512 px square and
  re-encodes as WebP. Only pixels survive, so EXIF/GPS data and anything hidden in the file are dropped, which makes
  the stored image safe without a virus scan. Objects use random keys (`avatars/<user>/<random>.webp`) in the
  private bucket and are served by `GET /users/{id}/photo` to signed-in users only, through the same-origin proxy,
  with a URL versioned by the key (`?v=`) so browsers may cache it. Uploading a photo is the consent to show it
  (`profile_photo` consent record); removing it withdraws the consent and deletes the object. 10 uploads per hour.
- **Consequences:** documents and attachments still need ClamAV (Sprint 6). SeaweedFS needed `-volume.max=0`
  (D-013): its default slot count allowed only one bucket.

## D-034 · 2026-10-25 · Privacy settings and consent records

- **Context:** Sprint 2 asks for `dm_policy` and contact visibility settings and for consent records (§5.4); DMs
  and other users' profile views arrive with chat (Sprint 5).
- **Decision:** `dm_policy` uses the four §5.4 values with default `shared_context`; contact visibility is
  `hidden` (default) | `shared_context` | `everyone` and covers the e-mail address. No phone number is collected:
  nothing needs it yet (data minimisation, §14). The settings are stored now and enforced by the screens that show
  other users or create DMs (Sprint 5). `consent_records` is an append-only history (purpose, granted, policy
  version, time); the current state of a purpose is its latest record. Making the e-mail visible records a
  `contact_sharing` grant, hiding it a withdrawal. Profile edits use optimistic concurrency (`version`; stale writes
  get `409 profile.version_conflict`); photo changes do not bump the version.
- **Consequences:** the privacy-notice acknowledgement and the data export build on the same table.

## D-035 · 2026-10-25 · Role assignment and the admin screens

- **Context:** D-016 makes Keycloak authoritative for global roles, so the admin "role assignment" screen must write
  through the Keycloak admin API; D-028 requires every role change in `audit_logs`. The API mirrors roles from each
  access token, and a token stays valid for up to 15 minutes after a change.
- **Decision:**
  - A confidential client `smartazmiu-api-admin` with a service account holding only `manage-users`,
    `view-users` and `view-realm` (realm-management) lets the API read and change realm role mappings. Its
    secret comes from `KEYCLOAK_ADMIN_CLIENT_SECRET`.
  - Assigning roles: read the user's current Keycloak roles, apply the difference there, then mirror the result in
    `user_roles`, set `users.roles_synced_at` and write `user.roles_changed` with the administrator as actor. If
    Keycloak cannot be reached nothing changes (`503 identity.unavailable`). Only `student`, `teacher`, `staff`,
    `moderator` and `admin` are assignable; administrators cannot remove their own `admin` role (no lock-out);
    people who never signed in cannot receive roles because they have no Keycloak account yet.
  - Tokens issued before `roles_synced_at` are no longer mirrored, so a change or revocation takes effect at the
    next request instead of after the old token expires. Mirroring from a token stores that token's issue time,
    so another token from the same second is not treated as older.
  - `admin.users.read`, `admin.roles.assign` and `admin.audit.read` are granted to `admin` only. The user list uses
    offset pagination (admin table, §4.2) and diacritic-insensitive search over `normalize_az`-folded names,
    e-mails and university IDs. The audit viewer filters by action, actor, target and Baku calendar days and shows
    actions and details as Azerbaijani text.
- **Consequences:** an existing local Keycloak needs the new client (`make reset`, or a partial import); a fresh
  `make up` imports it from the realm file.

## D-036 · 2026-10-25 · Data export and privacy notice (export contents: product owner decision)

- **Context:** §5.4 asks for consent records and `GET /me/export` (Law "On Personal Data"); whether the export
  includes the user's own grades touches grade exposure, so the product owner was asked and chose to include them.
- **Decision:**
  - `GET /me/export` returns a JSON file (`smartazmiu-melumatlarim-<date>.json`) with the requester's account and
    registry record, roles, profile including the photo (base64), privacy settings, group, all enrollments with
    status, result and **their own grade**, teaching assignments, consent history, and audit entries about or by
    them (other actors are not named, only whether it was the user). Every query is filtered by the requester's id;
    classmates and teachers never appear. The export is audited (`user.data_exported`), not cached, and limited to
    5 per hour.
  - A versioned privacy notice (`PRIVACY_NOTICE_VERSION`, currently `2026-10`) is shown at `/privacy`. Acknowledging
    it records a `privacy_notice` consent for that version (idempotent; an outdated version gets
    `409 privacy.notice_outdated`). Until the current version is acknowledged, the dashboard shows a prompt; it does
    not block using the platform. Bumping the version asks everyone again.
  - The notice text is a draft for the university's legal office (§12.8) and says so on the page.
- **Consequences:** account deletion (the remaining §5.4 right) is not part of Sprint 2.

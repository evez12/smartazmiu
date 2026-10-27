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
  | Added in Sprint 5 | web: zustand 5.0.15 (chat client state, §4), @tanstack/react-virtual 3.14.19 (message list); the newest releases at least ten days old on 2026-10-26 (D-064). The API imports asyncpg 0.32.0 directly for `LISTEN` (already pinned). |
  | Added in Sprint 6 | image `clamav/clamav:1.4.3` (attachment scanning, D-068); web: react-markdown 10.1.0, remark-gfm 4.0.1, remark-math 6.0.0, rehype-sanitize 6.0.0, rehype-katex 7.0.1, katex 0.18.11 (also forced on rehype-katex and remark-math through a pnpm override: releases before 0.18.2 let prototype pollution bypass `trust`, GHSA-238p-pmpm-9mq7; 0.19.1 was three days old), web dev: @types/hast 3.0.5, @types/mdast 4.0.4 (D-069); image `grafana/k6:1.3.0` (chat load test, D-073); API: prometheus-client 0.26.0, images `prom/prometheus:v3.15.0`, `grafana/grafana:13.2.4` (metrics and dashboard, D-080). |

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
- **Superseded in part by D-037:** tokens now live in a server-side session; `sa_access` no longer exists.
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

## D-037 · 2026-10-25 · Server-side web sessions and slim access tokens (fix for the sign-in 502)

- **Context:** sign-in through nginx failed with `502` at `/auth/callback` for a user with
  `default-roles-smartazmiu` plus extra roles. Measured on the callback response (bypassing nginx): `sa_access`
  (sealed access token) 2201 B, `sa_session` (sealed refresh token, subject, CSRF) 1442 B, `sa_oidc` deletion 55 B,
  i.e. 3698 B of Set-Cookie plus ~620 B of other headers, above nginx's default 4 KB `proxy_buffer_size`. The access
  token was 1438 B because `fullScopeAllowed` copied every realm role (`offline_access`, `uma_authorization`,
  `default-roles-smartazmiu`) and the `account` client roles into it; a plain student had ~150 B of headroom.
  Options: raise proxy buffers only; split cookies into chunks; keep tokens server-side.
- **Decision:**
  - Tokens leave the browser. `sa_session` carries a random 256-bit id (43 characters); the session (tokens, access
    expiry, subject, CSRF token) is stored in Redis database 1 under `web:session:<sha256(id)>`, with a TTL equal to
    the Keycloak session lifetime. `sa_access` is removed; `sa_oidc` (PKCE state, ~0.5 KB) stays sealed. The callback
    answers `302`. Refresh rewrites the stored session under the same id; sign-out deletes it. Pages without a
    session cookie never connect to Redis. If Redis is unreachable, pages show their "unavailable" state and the
    proxy route answers `503`; users are not signed out.
  - All Set-Cookie headers of a response must stay within `SET_COOKIE_BUDGET_BYTES = 1024` (unit test on the real
    callback handler with an oversized token set; E2E through nginx). Measured through nginx on 2026-10-25 for
    `kanan.babayev`: 203 B in 2 Set-Cookie headers (`sa_session` set, `sa_oidc` deleted); the E2E test prints
    the value on every run.
  - `smartazmiu-web` has `fullScopeAllowed: false` and a realm scope mapping for `student`, `teacher`, `staff`,
    `moderator`, `admin` only, so Keycloak's default and helper roles and the `account` client roles are not put
    into access tokens. The API already maps only catalogue roles; its test now covers `uma_authorization`,
    `mfa_required`, `offline_access` and `default-roles-smartazmiu`.
  - Safety net in nginx: `proxy_buffer_size 16k`, `proxy_buffers 8 16k`, `proxy_busy_buffers_size 32k`,
    `large_client_header_buffers 4 16k`.
  - Regression user `kanan.babayev` (default roles + student + moderator) is seeded in the realm.
  - Dependency: `redis` 6.3.0 (node client) in the web app.
- **Consequences:** amends D-005 and D-026. Sessions survive web restarts but not a Redis flush of database 1; the
  API cache uses database 0. An existing local realm gets the scope mapping and the new user through the admin API
  (or `make reset`); a fresh `make up` imports them.

## D-038 · 2026-10-25 · Cleared import files, seed grade and audit entries of deleted accounts

- **Context:** the Sprint 2 verification found import rows whose cleared file contents were stored as JSON `null`
  while the purge query looked for SQL `NULL`; check 4c (own grade in the export) had no seeded grade; four kept
  `audit_logs` entries came from a throwaway administrator that was deleted afterwards.
- **Decision:** `academic_imports.payload` uses `JSONB(none_as_null=True)`, so clearing stores SQL `NULL`;
  migration 0005 converts existing JSON `null` values (its downgrade does nothing, both meant "removed"). Aysel
  Məmmədova's completed `SOS-1101` (2025, Payız) enrollment is seeded with grade 87. The four audit entries are kept
  unchanged; their actor shows as "system" because the actor account no longer exists (`actor_id` is `NULL`).
- **Consequences:** none for users; the export of the seed student now includes a grade.

## D-039 · 2026-10-25 · Redis persistence for web sessions (product owner request)

- **Context:** web sessions live in Redis database 1 of the shared instance (D-037). Eviction under memory pressure
  or a restart without persistence would sign everyone out. Options: one shared instance with `noeviction` and
  AOF; a separate instance for sessions.
- **Decision:** keep one instance, configured explicitly in `docker-compose.yml`: `--maxmemory-policy noeviction`
  (no key is ever evicted; at a memory limit writes fail visibly instead of dropping sessions) and
  `--appendonly yes --appendfsync everysec` (at most one second of writes lost on a crash). These were already
  the effective values (image defaults plus `--appendonly yes`); stating them keeps them from drifting. Verified:
  `CONFIG GET` returns `noeviction`/`everysec`, and all 42 session keys were present after `docker compose restart
  redis`. Database 0 (API rate limits) and the coming ARQ queue need `noeviction` too, so a shared policy fits.
- **Consequences:** Redis memory must be sized for sessions plus queues (sessions are ~2 KB each and expire with
  their TTL). A separate session instance remains an option for production if memory isolation is needed.

## D-040 · 2026-10-25 · Session lifecycle and throwaway E2E accounts (product owner request)

- **Context:** the product owner accepted the server-side session change (D-037) retroactively and asked for
  verified session handling and for tests that never change real accounts. Future authentication changes need
  owner approval first (§0.3).
- **Decision:**
  - Every sign-in creates a new random session id; a session cookie the browser already had is destroyed in the
    callback, and an unknown id is never adopted (no fixation). Sign-out deletes the Redis key even when Keycloak
    cannot be reached.
  - Each stored session has an absolute end, `expiresAt` = sign-in + 12 h (`SESSION_MAX_LIFETIME`, equal to the
    realm's `ssoSessionMaxLifespan`). A refresh keeps it and sets the Redis TTL and cookie max-age to
    `min(refresh_expires_in, expiresAt - now)`; at the end the refresh fails and the user signs in again. Sessions
    read past `expiresAt`, or stored before this field existed, are deleted. Unit tests cover rotation, sign-out
    deletion, the 12-hour cap under refreshes every 14 minutes, and legacy entries; the E2E test replays a signed-out
    cookie and gets `401`.
  - E2E tests that change accounts (staff 2FA enrolment, imports, role assignment, profile edits) create throwaway
    Keycloak users (`e2e-<role>-<random>`, random password) through the admin API and delete them when the test
    ends. The application keeps their mirrored rows (as for any account removed from the identity provider; there is
    no account deletion yet) and the audit entries about them. Seeded users are only signed in to, never changed.
    The invalid-import test runs after the roster import in a serial group, because it refers to imported data.
- **Consequences:** a fresh database can run the full suite in parallel; repeated runs leave inactive `e2e-` rows in
  the user list until account deletion (§5.4) exists.

## D-041 · 2026-10-25 · Timetable model, week parity and timetable imports

- **Context:** Sprint 3 asks for a schedule with upper/lower weeks, changes and an import "from the source format".
  AzMİU's timetable format is unknown (§6 of `AZMIU_ACADEMIC_DATA.md`); §6.1 fixes the entry fields and the parity
  rule only loosely.
- **Options:** a staff editor; a parser for an assumed export; CSV/XLSX templates in the existing import wizard.
- **Decision:**
  - Three new import kinds in the existing wizard (preview → apply, row errors, idempotent): `week_parity`,
    `schedule`, `schedule_changes`. A parser for the university's own export can feed the same specs later.
  - `schedule_entries`: offering, ISO weekday, wall-clock start/end, `every|upper|lower`, class type
    (lecture/seminar/laboratory), room, optional teacher (default: all teachers of the offering) and an optional
    group subset (`schedule_entry_groups`) for joint offerings (§13.1). Natural key: offering, weekday, start,
    parity and group set; naming every group of the offering equals naming none.
  - A timetable file is the complete timetable of the offerings it mentions: their entries missing from the file
    are removed. While the semester runs, an edited or removed entry ends the day before the import
    (`active_until`) and its replacement starts that day, so past weeks keep showing what actually happened. An
    offering's first timetable, and edits before the semester starts or after it ends, cover the whole semester.
  - Parity: the week containing the semester's first day is an upper week; weeks alternate from Monday to Monday.
    A `week_parity_overrides` row restarts the alternation from its week (a holiday week that "does not count" is
    one override). Days outside every semester have no parity.
  - `schedule_changes`: one row per occurrence (entry + date) that cancels it or changes date, time, room or
    teacher, with a note. Holidays are cancellations; there is no separate holiday table. A changed past day is
    stored like any other change; notifications arrive in Sprint 4 and will not be sent for past days (§13.4).
  - Reading: `GET /me/schedule?start&end` (default this week, at most 42 days) expands entries per day in SQL-
    filtered visibility: active (not dropped) enrollment and, for group-restricted entries, the user's group;
    teaching the entry; or substituting on that date (only those days). Moved classes appear on the original day
    as "moved" and on the new day; the payload never contains grades or contact details.
  - `GET /me/schedule.ics`: the current (or next) semester as one event per occurrence with `TZID=Asia/Baku` and a
    VTIMEZONE; cancelled classes keep their UID with `STATUS:CANCELLED`, moved classes keep the UID of their
    original occurrence, so a re-import updates calendars instead of duplicating events.
- **Consequences:** imports compare against today's Baku date, so a preview and its apply on different days can
  differ by one day of history. Timetable conflicts (two classes in one room at once) are not checked; the spec
  does not ask for it.

## D-042 · 2026-10-25 · Campus map data and floor plans

- **Context:** §6 asks for buildings, floors, rooms with coordinates and SVG floor plans; no plans of AzMİU exist.
  Uploaded SVG files are active content and would need sanitising (§14).
- **Decision:** buildings, floors and rooms are imported like the academic registry (`buildings`, `floors`,
  `rooms`). A floor has a frame in decimetres (`width × height`); each room is a rectangle inside it (checked on
  import). The web app draws the plan as SVG from this data, so no uploaded markup is ever rendered. Room codes are
  unique across the campus (`1-305`: building 1, room 305) and match the timetable's `room_code`. Room search
  folds Azerbaijani letters like the user search. Campus endpoints require sign-in for now; the guest map belongs
  to the public pages, which no sprint has scheduled yet. Seed: two made-up teaching buildings with three floors
  each at the university's public address.
- **Consequences:** plans are schematic (rectangles, no walls or doors); real plans can replace the seed data
  through the same import.

## D-043 · 2026-10-25 · Homepage widgets before announcements and chat exist

- **Context:** Sprint 3 asks for homepage widgets for today's classes, announcements and (placeholder) unread chat.
  Announcements are built in Sprint 4 and chat in Sprint 5.
- **Options:** pull a minimal announcements model forward; show both widgets as explained empty states.
- **Decision:** today's classes are live (`GET /me/schedule` for today's Baku date, rooms link to the map). The
  announcements and unread-chat widgets are in place with an empty state that says what will appear there; they
  read real data from the sprints that create it. No announcements model is built early (§0.3: no scope pulled
  forward). The dashboard keeps the group and subjects below the widgets.
- **Consequences:** Sprint 4 replaces the announcements empty state with the user's announcements.

## D-044 · 2026-10-25 · Root cause of the first-sign-in E2E failures

- **Context:** after Sprint 3, the profile and mobile-shell tests failed now and then on the first sign-ins of a
  fresh stack, and one web unit-test run had failed during the pre-flight. Suspects named by the product owner:
  TOTP window reuse, Keycloak cold start, shared session state.
- **Findings:** reproduced on a fresh `make reset && make up`: the profile test waited for "Şəkil yeniləndi" and
  the API log contained no `PUT /me/photo` at all. The file had been set on server-rendered markup before React
  attached its `onChange`, so the upload was silently lost; the mobile-shell test clicks a React-only button the
  same way. On the first sign-in the browser cache is cold, so hydration takes longest exactly there. Ruled out:
  TOTP (every 2FA test enrols a new account with its own secret; the realm accepts one window of look-ahead),
  Keycloak readiness (`make up --wait` waits for `/health/ready`; every sign-in page appeared in time), shared
  sessions (sign-out ends only that browser's Keycloak session). The unit-test failure was not a flake: it was a
  wrong expectation in the session-lifetime test while it was being written (the last refresh in the loop leaves
  3720 s, the assertion said ≤ 3600), corrected minutes later in the same commit; 20 shuffled runs pass.
- **Decision:** `PageHeader` renders a `HydrationMark` that sets `data-hydrated` on `<html>` once the page
  segment has hydrated (pages stream inside Suspense boundaries that hydrate after the shell, so the root layout
  is too early). `signIn`, `signInWithSecondFactor` and the import helper wait for it. No retries were added.
- **Consequences:** tests that navigate with `page.goto` and then use client-side controls call `openPage`.

## D-045 · 2026-10-25 · E2E data hygiene

- **Context:** the timetable acceptance test left an `E2E-…` offering with an enrollment and a timetable entry in
  group 765a2 on every run, and its throwaway student stayed in the registry and in the group; the profile test
  left an uploaded photo in object storage.
- **Options:** a separate database or tenant for E2E; tests that remove what they create.
- **Decision:** tests clean up after themselves, and a check proves it.
  - `make e2e` runs `make seed` first, so every run starts on the sample data (the Sprint 2 roster import then
    applies as a no-op, which the test already accepts).
  - A `records` fixture removes offerings coded `E2E-…` (with enrollments; groups, teachers and timetable cascade)
    and takes `e2e-…` accounts out of the registry and their group, also when a test fails or times out. It
    uses direct SQL from the test process because the product has no delete for imported records and the spec
    does not ask for one. The profile test removes its photo through the UI and checks that it is gone.
  - Playwright's global setup counts the rows of every seed table (registry people, structure, offerings,
    enrollments, campus, timetable); its teardown fails the run if any count changed. Account rows of `e2e-`
    users, import records, audit entries and consent records are not seed data and are not counted.
  - Dependency: `pg` 8.23.1 and `@types/pg` 8.23.1 (dev only). The CI E2E job installs uv for the seed step.
  - The screenshot comparison (`make visual`) runs in a container without the database and sets
    `E2E_DATA_CHECK=off`; every other run requires the check.
- **Consequences:** a separate E2E database would also isolate parallel developers; not needed for one dev box.

## D-046 · 2026-10-25 · Leftover e2e- account rows (product owner decision)

- **Context:** throwaway E2E accounts are deleted in Keycloak after each test, but their mirrored `users` rows stay
  (D-040), because the product has no account deletion yet.
- **Decision:** the leftover `e2e-…` rows are purged when account deletion (§5.4) is implemented, through that
  feature's purge path, not by an ad-hoc script.
- **Consequences:** until then the admin user list shows inactive `e2e-` accounts on development stacks.

## D-047 · 2026-10-25 · Releases during exam sessions (product owner decision)

- **Context:** §7 forbids planned maintenance during the January and June exam sessions; Sprints 4 and 14 fall in
  them.
- **Decision:** production releases are frozen during the January and June exam sessions; work continues and is
  released to staging only. Hotfixes are the only exception, as the roadmap already states for June (§8).
- **Consequences:** Sprint 4 (January) and the end of Sprint 14 (June) ship to staging; production receives them
  after the session.

## D-048 · 2026-10-25 · Background worker and the redis-py version

- **Context:** §4 names ARQ for background jobs. Its latest release (0.28.0, April 2026) requires `redis<6`; the API
  pinned redis-py 8.1.0.
- **Options:** force ARQ onto redis-py 8 with a resolver override (a combination ARQ does not test); move the API
  to redis-py 5.3.1, the newest release ARQ supports; write our own queue (against §4).
- **Decision:** redis-py `5.3.1` (with `hiredis` 3.5.0, which ARQ's requirement pulls in) and `arq` `0.28.0`. The
  API uses only basic asyncio commands (get/set, pipelines, ping), all unchanged in 5.x. One worker process
  (`worker` service in `make up`, `make dev-worker` natively) runs `app.workers.main.WorkerSettings`, on Redis
  database 0 (D-039: `noeviction`).
  - Work is persisted before the worker is woken: the API writes pending rows, then enqueues a job; a failed
    enqueue (Redis outage, §13.5) is logged and the per-minute cron job picks the rows up. Jobs keep no results
    and have no fixed ids, so a wake-up is never refused because an earlier one is still recorded.
  - Dev dependency `http-ece` 1.2.1 (reference implementation of RFC 8188, used only by tests).
- **Consequences:** revisit when ARQ supports redis-py 6+.
- **Addendum 2026-10-26 (product owner request):** both stay pinned exactly (`arq==0.28.0`,
  `redis[hiredis]==5.3.1`, `hiredis` 3.5.0 in the lock file). `pip-audit` 2.10.1 and `pnpm audit` report no known
  vulnerabilities. The ARQ/redis-py pairing must be revisited before Phase 4 (launch readiness): either a newer
  ARQ that supports redis-py 6+, or a decision to keep 5.x with its security support confirmed.

## D-049 · 2026-10-25 · Notification service

- **Context:** Sprint 4 asks for in-app, Web Push and e-mail notifications with preferences and quiet hours;
  §5.6 requires de-duplication and checks of membership and preferences at delivery time. It lists defaults only
  for chat and mentorship events, which come later.
- **Decision:**
  - `notifications` holds the in-app row (always created; the bell is the record). `UNIQUE (user_id,
    dedupe_key)` with `ON CONFLICT DO NOTHING` makes an event notify a user once, however often a job or sync
    runs. Fan-out is one `INSERT … SELECT` per recipient query, so ids come from a SQL `uuid7()` function
    (PostgreSQL 16 has none) and stay time-ordered for cursor pagination.
  - Push and e-mail are `notification_deliveries` rows, created only for channels the user has on. The worker
    takes one due row at a time (`FOR UPDATE SKIP LOCKED`) and checks again: account active, still in the
    audience (a check per subject type), channel still on, push outside quiet hours, device or address present.
    Otherwise the row is `suppressed` with a reason. Temporary failures retry 5 times with backoff 2, 4, 8, 16
    minutes, then `failed`.
  - Categories now: `announcements` (push and e-mail on by default), `events` and `schedule` (push on, e-mail
    off). Quiet hours default to 23:00–08:00 Baku time and may span midnight. Inside them push is **suppressed,
    not postponed** (§5.6 says "push suppressed"); e-mail and in-app are not affected.
  - Web Push: message encryption (RFC 8291, `aes128gcm`) and VAPID (RFC 8292) are implemented on the existing
    `cryptography`, `pyjwt` and `httpx` instead of `pywebpush`, which would add `requests` and `aiohttp`. The test
    decrypts with the reference `http_ece` and verifies the VAPID token. The key pair is derived from
    `VAPID_SECRET` (one generated value like the other secrets), so it is stable across restarts.
  - Push endpoints come from browsers and the worker posts to them, so only HTTPS URLs on known push services
    (FCM, Mozilla, Windows, Apple) are accepted; other endpoints are rejected at registration and again before
    sending (§14 SSRF). An endpoint registered again moves to the user signed in on that browser; at most 10
    devices per user. 400/403/404/410 from the push service delete the subscription.
  - E-mail is plain text in Azerbaijani with a link to the item and to the settings page; push and e-mail
    carry the same text the bell shows (no more on a lock screen than in the app).
- **Consequences:** a worker crash between sending and committing can send one message twice (ARQ is
  at-least-once). Real-time bell updates wait for the WebSocket gateway (Sprint 5); until then the bell polls.

## D-050 · 2026-10-26 · Announcements and their audiences

- **Context:** Sprint 4: announcements for the university, a faculty, a specialty, a group or a course offering;
  §6.1: the audience is resolved at publication and re-evaluated for people who join it while the
  announcement is still active. The spec does not say who is "in" a faculty, whether announcements can be
  edited, or when one stops being active.
- **Decision:**
  - One audience per announcement, stored as a type plus one typed foreign key (a CHECK keeps exactly the
    right one set). Members, resolved in SQL: university = every active account; faculty, specialty, group =
    the registry students of its groups and those groups' curators; course offering = its students (not
    dropped) and its teachers. Events use the same audiences.
  - Publishing is immediate (scheduled announcements are Sprint 20) and accepts `Idempotency-Key`; a repeated
    key returns the first announcement. Recipients are materialised in `announcement_recipients` at
    publication; everyone added is notified (category `announcements`).
  - Re-evaluation: after an import that can move people (groups, students, offerings, enrollments) the API
    wakes `sync_audiences`, and the worker also runs it every 5 minutes. It adds audience members who are not
    recipients yet to every **active** announcement (published, not past its optional `expires_at`) and
    notifies exactly them; notification de-duplication makes reruns harmless.
  - People who leave an audience keep the announcements they already received (like a letter already
    delivered), but pending push and e-mail for them are suppressed because the worker re-checks membership.
  - Staff may correct title, text and end time (optimistic `version`, nobody is notified again) and archive an
    announcement, which hides it from recipients. The audience never changes; a wrong audience means archiving
    and publishing again. Publishing, edits and archiving are audited.
  - Permission `announcements.publish` for `staff` and `admin`; the audience picker searches names and codes
    without Azerbaijani letters and offers only offerings of running or coming semesters.
  - Text is plain (line breaks kept); Markdown arrives with chat in Sprint 6.
- **Consequences:** a university-wide announcement writes one recipient row per active account.

## D-051 · 2026-10-26 · Events, RSVP, tickets and check-in

- **Context:** Sprint 4: events with list, filters, detail, RSVP, a QR ticket and a check-in screen for staff;
  acceptance: an event for faculty X reaches the students of X by push and in-app, and RSVP produces a QR
  ticket. The spec says nothing about capacity, cancellations, changes or who checks people in.
- **Decision:**
  - Events use the announcement audiences (D-050): materialised recipients, sync for people who join later
    while the event has not ended, permission-filtered lists. People who registered keep seeing the event
    after leaving the audience. Staff with `events.manage` see every event.
  - Filters: coming (not ended, soonest first) or past (most recent first), and "only mine"; cursor paging
    on `(starts_at, id)`. Event categories are not in the spec and are not added.
  - Place: a campus room code (links to the map) or free text for places outside the room registry; one of
    them is required. Capacity is optional; registrations lock the event row, so simultaneous RSVPs cannot
    overbook it. RSVP opens at publication and closes when the event starts; it can be withdrawn until then.
  - Ticket = the registration. Its QR code is `SA1.<registration id>.<HMAC-SHA256 under TICKET_SECRET of the
    event id and the registration id, 16 bytes>`: unguessable, bound to one registration of one event, and
    nothing secret is stored per ticket. (Amended 2026-10-26: the signature first covered the registration id
    only and the event binding came from the database row.) Production
    refuses to start without `TICKET_SECRET`. A withdrawn RSVP or a cancelled event voids the ticket.
  - Check-in (`events.check_in`, staff and admin) by scanning or typing the code, or manually from the
    attendee list (audited). It opens 2 hours before the start and closes at the end; a second scan is refused
    with the time and name of the first. A checked-in attendee cannot withdraw.
  - Notifications (category `events`): publication to the audience; a change of time or place, and a
    cancellation, to registered attendees only. Title-only corrections notify nobody. The delivery-time check
    lets a cancellation through to registered people even though the event is no longer active.
  - Permissions `events.manage` and `events.check_in` for `staff` and `admin`; publishing, edits, cancellation
    and manual check-ins are audited.
- **Consequences:** no waiting list; a full event refuses further RSVPs until someone withdraws.

## D-052 · 2026-10-26 · Notifications for timetable changes

- **Context:** D-041 deferred change notifications to Sprint 4; §13.4 requires that a change on a day already
  past is stored but not notified. §8 lists no separate task for it, so it is part of the notification service.
- **Decision:** applying a `schedule_changes` import notifies (category `schedule`, push on by default) every
  active account that attends or teaches the class (the timetable view's rule, plus a substitute teacher) about
  each created or edited change whose original or new date is today or later in Baku time. The de-duplication
  key includes a fingerprint of the change, so re-importing the same file notifies nobody and an edited change
  notifies again. The title is "<subject>, <day month>", linking to that day in the timetable. At delivery time
  the worker checks that the change still exists, is not past, and the person still has the class. The
  notifications are written in the import's transaction, so a failed apply notifies nobody.
- **Consequences:** a timetable import that removes or edits base entries (not changes) does not notify; the
  spec only asks for changes to be marked.

## D-053 · 2026-10-26 · Two Redis instances (product owner request)

- **Context:** one Redis instance held web sessions (database 1), the ARQ queue and API rate limits (database 0),
  all under `noeviction` (D-039). Chat will add presence, typing and pub/sub traffic, which is disposable but
  large; under memory pressure it must not be able to push sessions or queued jobs out, and the queue must not
  stall because a cache is full.
- **Decision:**
  - Instance A, service `redis` (port 6379): web sessions (database 1) and the ARQ queue (database 0).
    `noeviction`, AOF with `appendfsync everysec`, persistent volume. Settings: `SESSION_REDIS_URL` (web),
    `QUEUE_REDIS_URL` (API and worker).
  - Instance B, service `redis-cache` (port 6380): API rate limits now; presence, typing and chat pub/sub from
    Sprint 5. `maxmemory 256mb` (`REDIS_CACHE_MAXMEMORY`), `allkeys-lru`, no RDB snapshots, no AOF, no volume.
    Setting: `REDIS_URL`. Rate limits already degrade gracefully when Redis fails (they only guard).
  - Both have health checks; the API waits for both, the worker for A. Tests use database 15 of B.
  - Verified on 2026-10-26: with 47 web sessions in A, 2.5 million 256-byte writes to B filled it to 255 MB and
    evicted 1,256,631 keys. A afterwards: the same 47 session keys, the same 17 queue keys, `evicted_keys:0`,
    worker health check passing; with B still full, the event and announcement E2E flows (sign-in, publishing,
    e-mail sent by the worker) passed 3/3.
- **Consequences:** a lost cache costs at most rate-limit counters (and later presence), never a session or a
  job. Production may give B more memory; A must be sized for sessions plus queue.

## D-054 · 2026-10-26 · People who join an audience late (product owner request)

- **Context:** after a group transfer or a late enrollment, the audience sync (D-050) notified the newcomer about
  every active announcement and coming event on every channel: a burst of push and e-mail at once.
- **Decision:** late joiners are notified in-app only (no push or e-mail deliveries are created), and at most five
  per person per sync run across announcements and events (`LATE_JOIN_CAP`), newest announcements first, then
  the soonest events. Everything they joined still appears in their lists; only the notification is capped.
  Publication itself is unchanged: everyone in the audience then is notified on all their channels.
- **Consequences:** the sync no longer wakes the dispatcher, since it queues nothing to send.

## D-055 · 2026-10-26 · Throttled e-mail for mass announcements (product owner request)

- **Context:** a university-wide announcement creates one e-mail per active account; sending them as fast as the
  worker can would overload the SMTP relay and look like spam.
- **Decision:** the dispatcher sends at most `MAIL_BATCH_SIZE` (200) e-mails per `MAIL_BATCH_INTERVAL_SECONDS`
  (60) across all workers. Before each send it takes a transaction-level advisory lock and counts e-mails sent in
  the window (partial index `ix_notification_deliveries_mail_sent`, migration 0010). When the budget is spent, the
  run carries on with push only and the worker schedules one continuation job after the interval under a fixed
  job id, so repeated runs never queue more than one. Each delivery is still claimed and sent in its own
  transaction (`FOR UPDATE SKIP LOCKED`), so retried or parallel jobs never send one twice.
- **Test:** 1,200 recipients with two workers in parallel and an extra retried run: 500 per window, 1,200 e-mails
  in total, 1,200 distinct addresses, nothing left pending.
- **Consequences:** 200 per minute delivers 12,000 e-mails an hour; raise the setting with the relay's limits.

## D-056 · 2026-10-26 · Chat ADRs accepted (product owner approval)

- **Context:** ADRs 0002 (messages partitioning and snowflake ids), 0003 (WebSocket tickets) and 0004 (chat
  authorisation) were proposed before any chat code was written.
- **Decision:** all three are accepted with these changes:
  - 0002: the worker-id lease TTL is 60 s and it is renewed every 20 s, so a short Redis A outage (two missed
    renewals) does not stop id generation; an unconfirmed lease after 50 s, or a lease found lost or taken, still
    stops generation with a typed error (`chat.unavailable`).
  - 0003: the ticket hash is stored only in Redis instance A (`noeviction`), never in the cache instance B. The
    new `POST /api/v1/ws/ticket` endpoint is approved; sign-in, sessions and token handling are unchanged.
  - 0004: exam windows come through an injected provider interface (D-059).
- **Consequences:** Sprint 5 is built against the accepted ADRs; any later change to them needs a new decision.

## D-057 · 2026-10-26 · Exam mode blocks everyone (product owner decision)

- **Context:** ADR 0004 asked whether the offering's teachers keep posting in the course channel during their own
  exam window.
- **Decision:** no. Exam mode refuses writes (send, react, edit, attachments) from every member, teachers
  included. Teachers reach the class through announcements during an exam. Reading stays allowed.
- **Consequences:** the authorisation table test covers a teacher in exam mode; no exemption exists in code.

## D-058 · 2026-10-26 · Moderator mute and duplicate-send protection (product owner decisions)

- **Context:** §5.7 defines `channel_members.muted_until` as the member's own notification snooze, but §5.5 also
  needs a moderator mute; and §5.7's `UNIQUE (channel_id, client_msg_id)` cannot exist on the partitioned
  `messages` table (ADR 0002).
- **Decision:**
  - `channel_members.posting_muted_until` holds the moderator mute (§5.5, 1 h / 24 h / 7 d), separate from
    `muted_until`. Only moderation actions set it (console in Sprint 10); the authorisation function reads it
    (`chat.muted`).
  - Duplicate sends are prevented by the unpartitioned lookup table `message_client_ids` (`channel_id`,
    `client_msg_id`) → `message_id`, `UNIQUE` through its primary key, inserted in the same transaction as the
    message with `INSERT … ON CONFLICT`. Rows are kept seven days and purged by an idempotent daily ARQ job. The
    reconnect backfill window is three days, below the retention, so a client never retries a send the table has
    forgotten.
  - A test sends the same `client_msg_id` twice concurrently and expects exactly one message and the same ack.
- **Consequences:** a send that is retried more than seven days later would create a second message; the client
  never does this (the offline queue asks before resending anything that old).

## D-059 · 2026-10-26 · Exam windows through a provider, enforcement in Sprint 10 (product owner decision)

- **Context:** exam slots (§5.2) arrive in Sprint 10, but the chat authorisation function needs the exam-mode
  reason from Sprint 5 (ADR 0004, §13.4).
- **Decision:** the chat module depends on an `ExamWindowProvider` interface (`windows(channel_ids, at)`). Sprint 5
  ships the interface and a stub that returns no windows, plus the `chat.exam_mode` reason code, its precedence
  and tests with a fake provider. Sprint 10 plugs in an implementation backed by `exam_slots`. Exam mode is always
  computed at read time from persisted data, never only from scheduled jobs.
- **Consequences:** until Sprint 10 no channel is ever in exam mode in a running system; this is intended.

## D-060 · 2026-10-26 · Chat schema details for Sprint 5

- **Context:** the Sprint 5 brief asks for `body_tsv` and its GIN index now (ADR 0002 had placed them in Sprint 10),
  default topics "per channel", and either the §5.7 consistency job or a date for it. Migration 0011 (chat core)
  was already merged.
- **Options:** rewrite migration 0011; add a follow-up migration. Topics on every channel type; topics only where
  §5.1 lists them. Ship the consistency job empty; ship it with the first writer.
- **Decision:**
  - Migration 0012 adds `messages.body_tsv` (`tsvector`) with a GIN index on the partitioned parent. The message
    service writes `to_tsvector('simple', <exact form> <ASCII-folded form>)` from `normalize_az` with every insert,
    so a query typed with or without Azerbaijani letters matches (§5.7.1). Search endpoints stay in Sprint 10.
  - Default topics (`umumi/ümumi`, `suallar`, `materiallar`, `imtahan-hazirligi/imtahan-hazırlığı`) exist only in
    course and community channels; communities also get `meslehet/məsləhət` (§5.1). Group, faculty and DM channels
    have no topics, and their messages have `topic_id` NULL.
  - Reactions, mentions and attachments are schema only in Sprint 5, so nothing can be orphaned yet. The weekly
    consistency job (§5.7) ships in Sprint 6 with the first code that writes those rows.
  - Only processes that issue message ids hold a snowflake lease: every API process. The ARQ worker writes no
    messages in Sprint 5 and leases nothing.
  - Partition upkeep (`ensure_message_partitions`) and the client-id purge (`purge_message_client_ids`) are daily
    ARQ cron jobs at 02:10 and 02:20 Baku time; the worker also creates missing partitions when it starts.
- **Consequences:** ADR 0002 is amended in place (the index list, the consistency job and the lease holders).

## D-061 · 2026-10-26 · Channel provisioning from the registry

- **Context:** Sprint 5 asks for an idempotent job that creates `course_offering`, `subject_community`,
  `academic_group` and `faculty` channels with their members and default topics, handles removals (dropped
  enrollment, group transfer, teacher replacement, inactive accounts), archives ended course channels and is woken
  like the audience sync (D-050). The spec does not say how members of archived channels change, which channel
  role teachers hold, or what the channels are called.
- **Options:** recompute everything per run vs. only the difference; keep archived channels in sync vs. freeze
  them; give teachers a moderator role vs. a plain membership.
- **Decision:**
  - `ChannelProvisioner.run` (module `chat/provisioning.py`) compares the registry with the stored state in
    set-based statements and writes only the difference: upsert channels (renaming them when the subject, group
    or faculty is renamed), insert missing default topics, insert missing members, delete revoked members,
    archive or reopen course channels. A transaction-level advisory lock serialises runs; a second run with
    unchanged data writes nothing.
  - Members (active accounts only, §13.1): course channel = students *of the offering's groups* whose enrollment
    is not dropped, plus the offering's teachers (D-030), so a group transfer also leaves the old group's course
    channels; subject community = active enrollees of the subject in any group, never teachers; academic group =
    its students and its curator; faculty = the students of its groups. Everyone joins with channel role
    `member`; teachers are recognised through `course_offering_teachers`, not through a channel role, so the
    moderator role stays for moderation (Sprint 10).
  - A course channel is archived and read-only from the day after its semester's `ends_on` (Baku calendar) and
    reopened if the dates are corrected. **Archived channels keep their membership as it was**: history stays
    readable for the people who took part, even after a transfer or deactivation. Channels created for a semester
    that has already ended get their members once, in the same run, and are then archived.
  - Names: course channel and community = the subject's Azerbaijani name; group = the group code; faculty = the
    faculty's name. The UI groups them by type (§12.7), and the channel payload carries the offering's group codes
    and semester for course channels.
  - Wake-ups: applying an import of faculties, specialties, subjects, semesters, teachers, groups, students,
    offerings or enrollments enqueues `provision_channels` after the commit; the worker also runs it every minute
    (lost wake-ups, §13.5). `make seed` runs the provisioner directly, so the sample data and its channels are
    deterministic for the E2E data check (D-045), which now also counts registry channels, topics and members.
  - After committing, the job publishes `membership.added` / `membership.revoked` on each person's control channel
    and `channel.changed` for archived or reopened channels (Redis B, §5.9); messages and their authors stay.
- **Consequences:** guides (Sprint 7) and moderator-assigned roles (Sprint 10) must be added to the desired-member
  query, or the job would remove them. A per-minute run costs a few set-based queries; at the pilot's size this is
  milliseconds.

## D-062 · 2026-10-26 · WebSocket gateway details

- **Context:** §5.9 and ADRs 0003/0004 fix the protocol's shape, tickets and authorisation; they leave open how
  events fan out across API processes, how presence is scoped, how backfill and backpressure behave, what happens
  when Redis is down, and how the bell learns about new notifications (D-049 deferred real-time updates here).
- **Decision:**
  - **Fan-out:** each API process runs one hub that pattern-subscribes to `chat:*` on Redis B and delivers to its
    local sockets: `chat:channel:<id>` (messages, typing, channel changes), `chat:user:<id>` (the per-user
    control channel: membership changes, read markers) and `chat:presence`. Events are published only after
    the commit. One subscription per process is simpler than per-channel subscriptions at the pilot's scale.
  - **Protocol additions:** `subscribe {channel_ids, after?, presence?}`; channels the user is not in are dropped
    silently. With `after`, missed messages are replayed as `message.created` before the `ack`, paced to the
    client. A channel with more than 1,000 missed messages, or an `after` older than the three-day window
    (D-058), is listed in `ack.truncated` instead, and the client reloads its latest page. Acks carry the event's
    `id` plus `message_id`/`client_msg_id`/`duplicate` for sends. Revoked or added access arrives as
    `channel.updated {channel_id, removed|added: true}`. Edit, delete and reaction events answer
    `request.not_supported` until Sprint 6.
  - **Heartbeat:** the client sends `ping` every 25 s and the server acks it; after 75 s without any frame the
    server closes the socket. On its own 25 s tick the server re-checks the account and every subscribed
    membership, so a lost control event delays a revocation by 25 s at most. A minute before the token ends,
    `auth.refresh_needed` asks for `auth.refresh {ticket}`; at the end, `error auth.expired` and close 4401.
  - **Presence** is visible only for people who share a channel with the asker (at most 200 per `subscribe`),
    `online` while any socket lives, `offline` 30 s after the last one closed. **Typing** is throttled with a
    3-second Redis key per user and channel and needs the right to post.
  - **Backpressure and abuse:** at most 256 frames wait per socket; beyond that the socket is closed with 4408
    (`chat.slow_consumer`) and the client reconnects with backfill. More than 60 client frames in 10 s closes it
    with 4429.
  - **Redis outage (§13.5):** when the hub loses Redis B, every socket gets `error chat.realtime_unavailable` and
    close 1013, and new sockets are refused with 1013 until it is back; a `message.send` that slips in is refused
    with the same code. Clients send through `POST /chat/channels/{id}/messages` and poll meanwhile. Messages are
    unaffected because they are stored before anything is published. Without Redis A, tickets cannot be issued
    (`503 chat.unavailable`) or redeemed (1013), and sends stop once the snowflake lease is unconfirmed (ADR 0002).
  - **Real-time bell:** migration 0013 adds a statement-level trigger on `notifications` that runs
    `pg_notify('notification_created', user_id)` for each recipient. NOTIFY is delivered only on commit, from the
    API and the worker alike, so no notification path had to change. Each hub `LISTEN`s on one dedicated
    connection and sends `notification {}` to the recipient's sockets; the client then refreshes the bell. The
    bell keeps polling while no socket is open.
  - **Tickets:** issuing needs the access token's `exp`, so `TokenClaims` now carries it (no change to sign-in,
    sessions or token validation). Origins allowed to open sockets: the origin of `APP_PUBLIC_URL`, plus
    `WS_ALLOWED_ORIGINS` (the native dev server, set by the Makefile).
  - **No ticket in logs:** uvicorn logs WebSocket handshakes with the query string, so the API's log handler
    rewrites any `ticket=…` to `ticket=[redacted]`; the structlog key `ticket` is redacted; Sentry events lose the
    query string and the query part of `request.url`; nginx logs `$uri` only and proxies `/ws` with the upgrade
    headers and a 90 s read timeout.
  - **DM refusals:** a sender who blocked the other person gets `chat.user_blocked`; a sender who is blocked, or
    writes to someone whose `dm_policy` is `nobody` (teachers and staff excepted), gets `chat.dm_unavailable`.
    One code for both keeps a block from being inferred (§5.4).
- **Consequences:** every API process receives every chat event; at the Phase 4 load target (200 msg/s) that is
  cheap, and per-channel subscriptions can replace the pattern later without changing the protocol.

## D-063 · 2026-10-26 · Chat REST details: unread counts, members, DMs and blocks

- **Context:** Sprint 5 needs the chat subset of §5.8. The spec does not say from when messages count as unread
  for a new member, how "shared context" is measured, how a DM screen reaches people, or how the client learns
  whom the user blocked.
- **Decision:**
  - `GET /chat/channels` returns the user's channels in sidebar order (courses, communities, group, faculty,
    then DMs; open before archived; by name) with `unread_count` from one query: messages by others after the
    later of the read marker and the time the user joined, capped at 100 (the UI shows "99+"). The id bound is
    turned into a `created_at` bound, so only recent partitions are read. Each channel carries `posting`, the
    ADR 0004 decision for sending, which the composer banner shows. Course channels carry `context`
    (`765a2 · 2026 Payız`); DMs carry the other person as `peer` and as `name`.
  - The response also lists `blocked_user_ids`, so the client can collapse those people's messages in shared
    channels (§13.2) without a separate endpoint.
  - `GET /chat/channels/{id}/members` (first 500 by name: id, name, photo, `teacher`/`curator` badge, no contact
    data) is added for the DM start flow from a member list; §5.8 has no member endpoint. Message authors carry
    the same badge.
  - Read markers clamp to the newest message of the channel and only move forward (D-002).
  - `POST /chat/dm` returns the existing DM (200) whatever the current policy or blocks, because a policy
    changed later never closes a DM (§13.2); sending into it is then decided per message. Creating one (201) is
    refused for blocks (`chat.user_blocked` for the blocker, `chat.dm_unavailable` for the blocked person) and
    by `dm_policy`: `shared_context` means a common open group, course or community channel; until guides exist
    (Sprint 7) `guides_and_teachers` admits teachers and staff only, who are always admitted (§5.4). The daily
    limit of 30 new DMs (§5.5) arrives with the other new-account limits in Sprint 10.
  - `PATCH /chat/channels/{id}/members/me` changes `notify_level` and the member's own snooze `muted_until`
    (sending `null` ends it); the moderator mute is not reachable here (D-058).
  - `POST /chat/channels/{id}/messages` answers 201 for a new message and 200 with `duplicate: true` for a
    repeated `client_msg_id`. `POST`/`DELETE /users/{id}/block` are idempotent (204).
- **Consequences:** non-members get the same 404 as for a channel that does not exist on every chat endpoint.

## D-064 · 2026-10-26 · Chat in the browser

- **Context:** Sprint 5's frontend: sidebar, virtualized messages, composer with an offline queue, a WebSocket
  client with reconnect, backfill and `auth.expired` handling, the Çat tab, DM start, and real-time bell
  updates. The spec leaves open where the socket lives, how long unsent messages are kept, how the composer
  reads its state, and how the screens get visual baselines without a database.
- **Decision:**
  - **One socket per tab for the whole signed-in app** (`ChatRuntimeProvider` in the app layout), so unread
    badges, the dashboard widget and the bell are live everywhere. It subscribes to every channel of the user,
    with `after = newest id seen` on reconnect. The ticket is fetched through the same-origin proxy (CSRF-checked,
    D-032), which also refreshes the session, so a 4401 close or `auth.refresh_needed` simply gets a new ticket; a
    401 there sends the user to sign in. The socket URL is `WS_PUBLIC_URL`, or `/ws` on `APP_URL` (nginx); the
    native dev server uses `ws://localhost:8000/ws` and the API admits that origin (`WS_ALLOWED_ORIGINS`). The CSP
    lists the socket origin in `connect-src`.
  - **Connection states:** `connecting`, `online`, `offline` (browser offline: the socket is closed at once),
    `fallback` (close 1013 or no ticket: sends go through REST, the open channel is polled every 5 s, the channel
    list every 30 s, the bell every 60 s as before). Reconnects back off 1–30 s with jitter.
  - **Unsent messages** wait in memory in the order written and are sent one at a time after the reconnect with
    their original `client_msg_id`, so a resend can never duplicate (D-058). They are not persisted: closing the
    tab drops them, and anything older than three days is not resent without the user pressing "Yenidən
    göndərin". Refusals (rate limit, read-only, …) show the reason from the policy and the retry button.
  - **History:** Zustand holds per-channel windows of messages ordered by snowflake id (compared as BigInt); live
    messages are appended only to a window that reaches the newest message. A truncated backfill drops the
    window, shows the latest page and offers "Oxunmamış mesajlara keçin", which loads the page after the read
    marker. The "new messages" divider stays where the marker was when the channel was opened. The read marker is
    sent (debounced) while the newest message is visible and the tab is in front.
  - **Sidebar:** Fənlər, Fənn icmaları, Qrup (group and faculty channels), Şəxsi; archived course channels sit in a
    collapsed "Arxiv (n)" list. Presence dots appear for DM peers and in the member list, and are requested only
    for those people.
  - **People:** the channel header opens the member list (D-063) in a side sheet; a member opens a card with
    "Mesaj yazın" and "Bloklayın" / "Bloku götürün". Messages of blocked people collapse to one line with
    "Göstərin".
  - **Dashboard:** the unread-chat widget (D-043) shows up to five channels with unread messages.
  - **Visual baselines:** the chat parts (sidebar entries, message rows, divider, blocked and unsent messages, the
    posting banner, the composer) are a section of `/design-system` with fixed sample data, so `make visual`
    records them in both themes without a database. Whole screens are covered by the functional E2E suite with
    axe checks in light and dark, at 320 px and on desktop.
  - **Dependencies:** zustand 5.0.15 and @tanstack/react-virtual 3.14.19, the newest releases that were at least
    ten days old, rather than ones published days before (D-014).
- **Consequences:** every signed-in tab holds one WebSocket even outside chat. Offline queues do not survive a
  reload until the PWA offline work (Sprint 15).

## D-065 · 2026-10-26 · Chat end-to-end tests and the §13 checklist for Sprint 5

- **Context:** the acceptance scenario needs two seeded 765a2 students in two browsers; D-040 allows seeded
  accounts to be signed in to but never changed, and D-045 requires every run to leave the sample data as it was.
- **Decision:**
  - `e2e/chat.spec.ts` signs in as Aysel and Ramin, who only write messages. Each message carries a random marker;
    the `records` fixture (`chatMessages`) deletes the marked messages, their duplicate-send keys, the DMs between
    the listed people and their read markers, also when a test fails. The data check now counts registry channels,
    topics and members (D-061). The file runs serially because its tests share the seeded students.
  - The network drop is Playwright's offline mode: the client closes its socket on the browser's `offline` event,
    queues what is written meanwhile and reconnects on `online` (D-064). The test checks that every message
    arrives exactly once on both sides.
  - Live revocation uses a throwaway student imported into 765a2 and then moved to 765a1 by a second students file;
    the open page must show the neutral notice and swap the group channel without a reload.
  - The map test at 320 px measured the room before the page had hydrated, which the larger client bundle made
    visible; it now waits with `openPage` like every test that depends on client code (D-044).
- **§13 coverage in Sprint 5:** tested: duplicate send (concurrent and retried), offline compose then reconnect,
  events for revoked channels, blocked user in shared channels (collapsed) and for DMs, `dm_policy` changed after a
  DM exists, slow mode + exam mode + mute precedence (policy table), huge bodies (4,000-character limit), many tabs
  (read markers, presence), snowflake restart and clock regression, backfill gap over 1,000 messages, group transfer,
  dropped enrollment, teacher replaced, inactive accounts, job retried (provisioning idempotency), Redis outage
  (REST fallback, persistence first). Not applicable yet: edit/delete windows, deleted parent messages, mentions and
  `@channel`, attachments and virus scans, malicious Markdown, link previews (Sprint 6 and 10); exam slots (Sprint 10,
  provider stub tested); account deletion (no deletion feature yet; messages already keep a NULL author).
- **Consequences:** `make up` could not be run from scratch in the Sprint 5 build container (its network allows no
  image builds); CI's E2E job runs the suite through `make up` and nginx on every push.

## D-066 · 2026-10-26 · CLAUDE.md for Sprint 6

- **Context:** CLAUDE.md still said "Sprint 1 only" and did not mention the chat rules agreed since (ADRs 0002–0004,
  D-056–D-065), so they would not survive a context reset.
- **Decision:** CLAUDE.md states the current sprint, the product owner's ask-first list for Sprint 6 (auth, hard
  deletes, grade exposure, CSP relaxations) and a short "Chat rules" section; it stays under 120 lines. Merged
  before any Sprint 6 code (`docs/claude-md-refresh`).
- **Consequences:** CLAUDE.md is updated whenever a sprint starts or a rule is added.

## D-067 · 2026-10-26 · Edit, delete, threads, reactions, mentions and notification levels

- **Context:** Sprint 6 group A (`feat/chat-messages-v2`). §5.3 and §13.2 fix the 15-minute window, the soft delete,
  the "silinmiş mesaja cavab" placeholder, a fixed set of eight reactions and `@channel` for privileged members; they
  leave open the reaction set, how a mention names a person, where replies appear, what counts in badges, and how
  chat notifications are categorised.
- **Decision:**
  - **Edit and delete** go through `MessageService.edit/delete`, used by `PATCH`/`DELETE /chat/messages/{id}` and the
    `message.edit`/`message.delete` socket events. Order of checks: the message exists and is not deleted, then
    the policy (`Action.EDIT`/`DELETE`, so archived, exam-mode and read-only channels refuse edits as before),
    then authorship (`chat.not_author`, 403), then the window (`chat.change_window_expired`, 403, also for
    deletes, §13.2). Non-members get `chat.message_not_found` (404). An edit clears `is_verified_answer` and
    `verified_by`, keeps reactions, re-indexes `body_tsv` and replaces the recorded mentions. A delete sets
    `deleted_at`, clears `body_tsv` and keeps the text in the database for moderation (Sprint 10); payloads of a
    deleted message have an empty body and no reactions or mentions. Events: `message.updated` (the full payload)
    and `message.deleted` (`id`, `channel_id`, `parent_id`, `deleted_at`).
  - **Threads** are one level deep: a reply to a reply is stored under the root, and a reply inherits the root's
    topic. A reply to a deleted root or to a message of another channel is refused (`chat.parent_not_found`).
    Replies are not part of the channel history (`parent_id IS NULL` in `GET …/messages`) and do not raise the
    unread badge; the root carries `reply_count` and `last_reply_at`, and the parent's author is notified.
    `GET /chat/messages/{id}/thread` returns the root (also when deleted) and the replies oldest first, paged with
    `after`. The reconnect backfill still replays replies, so open thread panels stay current. The panel opens
    with `?thread=<id>` in the third pane from 1280 px and as a sheet below.
  - **Reactions:** 👍 ❤️ 😂 😮 😢 🙏 🎉 ✅ (thumbs up, heart, laughter, surprise, sadness, thanks, celebration,
    done), stored as the emoji itself, so `DELETE …/reactions/{emoji}` takes it URL-encoded. Adding and removing
    are idempotent (`ON CONFLICT DO NOTHING` / delete by key) and publish `reaction.updated` only when something
    changed. They need `Action.REACT` and are limited to 60 changes per minute per person. Payloads list counts in
    the set's order; `my_reactions` is filled for the reader in REST responses and left `null` in broadcasts,
    where the client keeps its own. The web code writes the emoji as escapes, because the source check allows
    emoji only in user content.
  - **Mentions** are written as `<@user-id>` tokens; the composer shows "@Name", suggests channel members after
    "@" and encodes the picked people when sending (and decodes them for editing). The server records only
    channel members other than the author (at most 50, code spans ignored); other tokens stay plain text, are
    rendered as "@istifadəçi" without a name and trigger nothing (§13.2). `@channel` is honoured for the
    offering's teachers, channel owners and moderators, and the global teacher and staff roles; from anyone else
    it is ignored and the send result carries the notice `chat.channel_mention_not_allowed`, which the composer
    shows. A used `@channel` sets `messages.mentions_channel` (migration 0014), which stays set after edits.
  - **Notifications:** new category `chat` (§5.6 lists push for mentions and replies, so a category is needed for
    the push switch), kinds `chat.mention` and `chat.reply`. One notification per message and person
    (`dedupe_key = chat.message:<id>`), mention first, so a reply that also mentions someone notifies once and a
    re-edit never notifies again. Recipients are members with level `all` or `mentions` who have not blocked the
    author. The notification's subject id is the message id as a UUID (`UUID(int=id)`), so the delivery check
    can find the message and re-check membership, level, snooze, blocks and deletion when push is sent (§5.6).
    Title: "author · channel", link `/chat/<channel>` (with `?thread=` for replies), no message text. Chat e-mail
    is a digest in §5.6 (Phase 3): until then e-mail cannot be switched on for `chat` and the settings page shows
    push only.
  - **Notification level and snooze:** the channel payload adds `mention_count` (unread messages by others that
    mention the reader or use `@channel`, capped at 100). Badges: level `all` shows unread and mention counts,
    `mentions` only the mention count, `none` or an active `muted_until` nothing but a muted icon. A snooze also
    suppresses push at delivery; history and the bell are unchanged. The header menu sets the level and snoozes
    for 1 h, 8 h, 24 h or 7 days.
  - **Consistency job** (§5.7; Sprint 5 had only the schema, D-060): `remove_chat_orphans`, weekly on Monday
    03:40 Baku time, deletes reactions, mentions and attachments whose message no longer exists, in batches of
    5,000, logs the counts and is idempotent.
  - **E2E:** the chat test now covers a picked mention, a thread reply, a reaction, an edit and a delete between
    two seeded students; cleanup removes replies with their root, reactions, mentions and chat notifications of
    marked messages, and the data check also counts `message_reactions`, `message_mentions` and chat
    notifications, which must be unchanged after a run.
- **§13.2 in this group:** tested: edit/delete after 15 minutes and by non-authors, editing a verified message with
  reactions, deleting a parent with replies, mention of a non-member, `@channel` by a non-privileged user, blocked
  users and mute levels at delivery. Moderator deletes wait for Sprint 10.
- **Consequences:** composing a mention to someone outside the suggestion list (typing the token by hand) works
  but shows the token while editing. Unread counts no longer include replies.

## D-068 · 2026-10-26 · Chat attachments, ClamAV and same-origin storage

- **Context:** Sprint 6 group A (`feat/chat-attachments`): presigned uploads to the S3 store (D-013), images, PDF,
  DOCX, PPTX and ZIP up to 25 MB, extension + MIME + magic-byte checks, 20 per hour, ClamAV before anyone can
  download, purging of infected and abandoned files, short-lived downloads with safe headers, no SVG, new
  accounts kept out of community attachments, and text chat unaffected by a storage outage. The spec does not
  say where the browser reaches the store, how the CSP allows it, or what the uploader sees meanwhile.
- **Options:** stream every upload and download through the API (simple CSP, but the API carries every byte);
  presigned URLs on the store's own origin (needs `connect-src`, `img-src` and `frame-src` for that origin in
  production, plus CORS); presigned URLs on the app's origin through nginx.
- **Decision:**
  - **Same origin.** nginx proxies `/smartazmiu/` (the bucket path) to the store and keeps the `Host` header,
    which is part of the SigV4 signature, so presigned URLs signed for `APP_PUBLIC_URL` (`S3_PUBLIC_URL`) work
    unchanged and the production CSP stays as it was except an explicit `frame-src 'self'` for PDF previews.
    Verified against SeaweedFS 4.48: a PUT through the proxied host succeeds, a PUT with another content type is
    refused (403), and `response-content-type` / `response-content-disposition` are honoured. nginx adds
    `X-Content-Type-Options: nosniff` and `Cross-Origin-Resource-Policy: same-origin`. Only for the native dev
    server (another origin than the store) does the web app add `STORAGE_PUBLIC_URL` to `img-src`,
    `connect-src` and `frame-src`; SeaweedFS answers its CORS preflight. This development-only addition is
    flagged for the product owner; the Docker stack and production use none.
  - **Flow.** `POST /chat/attachments/presign {channel_id, filename, mime, size}` checks `Action.SEND_ATTACHMENT`
    (exam mode, archive, read-only, and the new reason `chat.attachments_not_allowed` for accounts younger than
    24 hours in subject communities, §5.5), the type (the extension decides, the reported MIME must agree;
    `application/x-zip-compressed` and `image/jpg` are accepted aliases), 1 byte–25 MB and 20 per hour, then
    stores a `message_attachments` row (uploader, channel, file name, no message yet) and returns a five-minute
    PUT URL for `chat/<channel>/<random hex>`. The key names neither person nor file. `message.send` /
    `POST …/messages` take `attachment_ids` (at most 10; the body may then be empty): each must be the
    sender's own, for this channel and unsent, and the object's size (HEAD) must equal the announced size;
    every failure gives the same `chat.attachment_not_found` so other people's ids reveal nothing. Binding
    happens in the message's transaction.
  - **Scanning** is the ARQ job `scan_attachments` (woken after each send, plus every minute): it locks one
    pending row at a time (`SKIP LOCKED`), downloads the object, checks the magic bytes (JPEG, PNG, GIF, WebP,
    `%PDF-`, ZIP; DOCX and PPTX must contain `word/document.xml` or `ppt/presentation.xml`), reads image
    dimensions from the header only, and streams the bytes to clamd (`INSTREAM`, a small client in
    `app/core/antivirus.py` rather than an unmaintained library). Results: `clean`; `infected`; `failed` (type
    mismatch or missing object). ClamAV or storage unavailable leaves the file `pending` ("Fayl yoxlanılır…")
    and retries with back-off up to five minutes. Rejected files notify the uploader in-app
    (`chat.attachment_rejected`, no push) and their objects are deleted by `purge_attachments` (twice an hour),
    which also removes uploads not sent within 24 hours; the rows of sent files stay with `purged_at`.
  - **Visibility.** Payloads list clean files to everyone; the uploader also sees their own pending or rejected
    files. Broadcasts carry clean files only, so the server sends the uploader's own view to their per-user
    topic after the send and after a rejection, and the channel gets `message.updated` once a file is clean.
  - **Downloads.** `GET /chat/attachments/{id}/download?inline=` checks membership of the message's channel
    (deleted messages: 404) and `clean` (else 409), and returns a one-minute URL whose response has the stored
    type, `Content-Disposition: attachment` (inline only for images and PDFs, RFC 6266 file name with UTF-8) and
    `Cache-Control: private, no-store`.
  - **ClamAV** `clamav/clamav:1.4.3` (signature database included, ~1.5 GB memory, ready after one to three
    minutes) runs in compose (infra and `make up`), in `make test-api` (CI sets `CLAMAV_REQUIRED=1`, so its test
    cannot skip) and in the E2E stack. The worker waits for it only to have started; scans retry until it is
    healthy.
  - **Outage (§13.5):** presign and attachment sends answer `503 chat.attachments_unavailable`; text messages
    never touch the store. Tested with the storage double switched off.
  - **E2E:** a clean PDF appears for the other student only after the scan and opens in the preview; a ZIP with
    the EICAR test file (built in memory, nothing committed) shows "virus aşkarlandı" to the uploader and
    nothing to the other student. Cleanup turns the test's files into abandoned uploads, which the purge job
    removes with their objects; the data check counts sent attachments.
- **§13.2 in this group:** tested: infected and abandoned uploads, malicious types (SVG, renamed ZIP), safe
  content types and dispositions, object-key guessing (§14), storage outage.
- **Consequences:** a file is not visible to others for the seconds the scan takes. The pilot needs ~1.5 GB extra
  memory for clamd. No new dependencies (Pillow, boto3 and httpx were already pinned).

## D-069 · 2026-10-26 · Markdown, KaTeX and code in messages; the dev-mode CSP errors

- **Context:** Sprint 6 group A (`feat/chat-render`): sanitized Markdown with an allowlist, KaTeX for `$…$` and
  `$$…$$`, fenced code in IBM Plex Mono, raw text stored and rendered on the client, XSS vectors in Vitest,
  KaTeX self-hosted, nonce-based CSP kept. The product owner asked to be consulted first if the sanitizer or the
  KaTeX delivery needed a CSP relaxation, and to check the inline-style CSP errors seen in development.
- **CSP check (done before writing the renderer):** a Playwright probe signed in as Aysel and opened
  `/design-system`, `/login`, `/chat`, a channel, `/`, `/schedule`, `/notifications` and `/profile`, collecting
  every console CSP report. Against `next dev`: 28 distinct "Applying inline style violates … style-src" reports;
  they come from the dev server injecting `<style>` elements for hot reloading without the nonce. Against the
  production build (`next build`, `next start`): none. After the renderer was added, the same probe on the
  production build also posted a message with display math, bold and code: KaTeX rendered, its three fonts
  loaded from the app's origin, zero reports. Nothing to fix; the dev noise is accepted (the dev CSP already
  differs by `'unsafe-eval'`).
- **Options:** sanitizing HTML (DOMPurify on a Markdown-to-HTML string, rendered with `dangerouslySetInnerHTML`);
  a syntax tree rendered as React elements (`react-markdown`), sanitized with `rehype-sanitize`.
- **Decision:**
  - **Pipeline** (`features/chat/markdown.tsx`): `remark-parse` with GFM (autolinks, strikethrough) and
    `remark-math`; raw HTML becomes literal text before anything else, so `<script>` is shown as typed and never
    parsed; `rehype-sanitize` with an allowlist (`p br strong em del code pre blockquote ul ol li a hr`; `href`
    with `http`, `https`, `mailto` only; code classes for languages and math; `script style svg math iframe
    object embed template` removed with their content, anything else replaced by its text); then
    `rehype-katex` with `trust: false` (no `\href`, `\url`, `\htmlClass`), `maxSize` 20, `maxExpand` 200,
    `throwOnError: false`; then mention tokens become name chips (D-067). React renders the tree; nothing goes
    through `innerHTML`, so no new CSP source is needed. Images in Markdown are dropped (no tracking pixels);
    files go through attachments (D-068). A line that is only `$$…$$` is display math; elsewhere `$$x$$` stays
    inline, as remark-math reads it.
  - **Links:** external links (another host) open in a new tab with `rel="noopener noreferrer nofollow"`, an
    external-link icon and the screen-reader text "(xarici keçid, yeni pəncərədə açılır)"; links within the app
    stay in the tab.
  - **Huge input:** a message nesting quotes or lists deeper than 40 levels is shown as plain text before
    parsing (the parser and tree transforms recurse; 2,000 nested quotes overflowed the stack in a test). The
    4,000-character limit bounds everything else.
  - **KaTeX delivery:** the package's CSS is imported by the renderer and bundled by Next.js with its fonts, so
    both are served from `/_next/static` under `style-src 'self'` and `font-src 'self'`. KaTeX's inline
    `style` attributes fall under the existing `style-src-attr 'unsafe-inline'` (kept since Sprint 1 for Radix);
    no relaxation was added. Its error colour uses the `--danger` token.
  - **Vitest vectors:** script, event handlers, SVG, iframe, style, comment tricks, forms, `javascript:` /
    encoded / `data:` / `vbscript:` links, Markdown images, KaTeX `\href` / `\url` / `\htmlClass` /
    `\htmlStyle`, a macro bomb, 2,000 nested quotes and 1,500 nested list items; each asserts no executable
    element or attribute survives.
  - The DM badge E2E failure first blamed on the client here was a test bug; see D-070, which also reverts the
    refetch added for it.
- **Consequences:** `$` pairs in prose render as math (prices use ₼ here, so this is rare). Code blocks have no
  syntax highlighting (not in the spec).

## D-070 · 2026-10-26 · Reports and their staff list; E2E fixes

- **Context:** Sprint 6 group A (`feat/chat-reports`): `POST /reports` for a message or a person with the §5.4
  reasons, one report per reporter and target counted once, rate limited and audited; an admin list with the
  statuses open / actioned / dismissed for staff and admins. No moderator console, auto-hide or SLA (Sprint 10).
  §5.7's `reports` also names `tip` targets, which do not exist before Sprint 8.
- **Decision:**
  - Migration 0016 adds `reports` (`target_type` message | user only; `tip` joins with tips), `UNIQUE (reporter,
    target_type, target_id)`, the message's `channel_id` for scoping moderators later, and the permissions
    `admin.reports.read` and `admin.reports.handle` for `staff` and `admin` (the catalogue grows with features,
    D-017).
  - `POST /reports`: the target must exist and be visible to the reporter (a message in a channel they are in, or
    an existing account); anything else, also an out-of-range id, is `404 reports.target_not_found`, so reports
    cannot probe channels or accounts. Own messages and oneself: `422 reports.own_content`. A repeated report
    returns the first one with `200` and `duplicate: true` and spends no rate-limit unit; a concurrent double
    submit resolves through the unique key. Ten new reports per hour per person (§14). Each report writes
    `report.created` to the audit log with target type and reason, without the note (the reporter's words, D-034).
  - `GET /moderation/reports?status=` (newest first, default view: open) and `PATCH /moderation/reports/{id}`
    (open / actioned / dismissed, setting or clearing `handled_by` and `handled_at`, audited as
    `report.handled`). Staff need the text to judge a report, so the list shows the reported message's channel,
    author and up to 1,000 characters of its text, also when the author deleted it afterwards, as plain text (not
    rendered). It shows names and photos only, never e-mail, phone or grades, and how many people reported the
    same target.
  - Web: "Şikayət edin" in the message's "more" menu (others' messages) and on a member's card; a dialog with the
    six reasons (`exam_leak` explained) and an optional note of up to 500 characters; `/admin/reports` in the admin
    navigation with a status filter, stacked rows on phones, and "Tədbir görülüb" / "Rədd edin" / "Yenidən açın"
    for holders of `admin.reports.handle`.
- **E2E fixes found while running the chat suite repeatedly:**
  - The DM step waited for a heading "Ramin Əliyev", which the profile dialog's own title also is, so the test
    sometimes typed into the course channel before navigation finished; it now waits for the dialog to close and
    the URL to change. The client refetches added for this in D-069 are removed again: a refetch started just
    before a message was stored could overwrite the live increment.
  - A message sent right after opening a channel could vanish when its live event arrived before the first page
    of history, which had been read just before the message was stored. Live messages for channels without a
    loaded window are now kept (at most 20 per channel) and merged into the first page if they are newer than it.
  - The seeded students hit the hourly upload (20) and report (10) limits after a few runs; the records fixture
    now resets those counters in Redis B for the people a test names (`records.rateLimit(rule, emails)`), and
    cleanup removes reports of the test's messages. The data check also counts `reports`.
- **Consequences:** reports of tips, moderator actions and auto-hiding remain for Sprints 8 and 10.

## D-071 · 2026-10-26 · Materials v1: access, versions, consent, scanning, reports

- **Context:** Sprint 6 asks for a materials catalogue per subject and semester with upload, copyright consent,
  preview and download; §6.1 adds versions, reports and ClamAV before download. The spec does not say who reads or
  uploads, what a report leads to, or how scans run.
- **Options:** per-offering catalogues (each group sees only its own offering) or per-subject catalogues with a
  semester filter; a separate scan job and queue or the chat attachment job (D-068); deleting reported materials
  or hiding them.
- **Decision:**
  - One catalogue per subject, filtered by the semesters with an offering of it. **Readers:** anyone with a
    not-dropped enrollment in any offering of the subject (past students too) and its teachers, for every
    semester; staff (new permission `materials.manage` for `staff` and `admin`, migration 0017) read every
    subject that has materials. **Uploaders:** teachers for the semesters in which they teach the subject; staff
    everywhere. Unreadable and unknown subjects are the same `404 materials.subject_not_found` (§14). Editors of a
    material (staff, its creator, teachers of its semester) add versions.
  - Uploads reuse the presigned flow of D-068 with the same file types (the type table moved to
    `app/core/uploads.py`), 50 MB per file (nginx body limit raised to 60 MB for the proxied PUT), 30 uploads per
    hour per person. A presigned upload is a `material_versions` row without a material until the form is saved;
    saving needs `copyright_confirmed: true`, and each version stores when consent was given and which consent
    text (`CONSENT_TEXT_VERSION`) was shown. A new upload is always the next version; old ones stay.
  - Versions are pending until the worker checks type and size and ClamAV scans them; the existing
    `scan_attachments` job (wake-up after each save, minute cron) also scans material versions, and
    `purge_attachments` also deletes the objects of rejected versions and of uploads never saved after a day.
    Others see clean versions only; uploaders and editors also see pending and rejected ones. Materials show the
    result on the next page load; no live event or notification in v1.
  - Reports: once per person and material (reasons copyright, wrong content, inappropriate, other; optional note),
    10 per hour, audited as `material.reported` without the note. Staff see them on `/admin/reports` under a
    "Materiallar" tab (permissions `admin.reports.read` / `.handle`) and can hide a material
    (`material.hidden` / `material.shown`): hidden materials disappear from catalogues and detail pages for
    everyone except `materials.manage` holders; nothing is deleted (no hard delete without the product owner).
  - Web: "Materiallar" in the main navigation (`/materials`, subject list), `/materials/[subject]` with semester
    tabs and the table, detail page with versions, preview (PDF in a frame, images) and download through one-minute
    links, upload and new-version forms with inline validation and the consent checkbox.
- **Consequences:** materials are not linked from course channels or `#materiallar` yet (Sprint 7 community UX).
  Every E2E run uploads and removes its own material; the data check counts `materials` and `material_reports`.

## D-072 · 2026-10-26 · Onboarding tour, empty states and copy review

- **Context:** Sprint 6 asks for an onboarding tour, empty states and an Azerbaijani copy review (§12.8). The spec
  gives no shape for the tour; §13.1 requires an explanatory state for users without imported data.
- **Options:** a modal step-by-step overlay on first sign-in, coach marks pointing at navigation items, or an
  inline panel on the dashboard; remembering it in the browser or on the account.
- **Decision:**
  - An inline panel on the dashboard ("SmartAzMİU ilə tanışlıq"), never a modal: it does not stand between the
    user and the page they came for, needs no positioning against the shell at 320 px and stays usable with a
    keyboard and screen reader. Four or five steps, each a short paragraph with a link to the section; the steps
    follow the main capacity: students (schedule, channels, materials, notifications, profile), teachers (the
    same with teaching wording), staff and admins (imports, announcements and events, reports, profile).
  - Finishing or closing it sets `users.onboarded_at` (migration 0018) through `PUT /me/onboarding {done}`;
    `GET /me` returns `onboarding_done`. Stored on the account so it does not return on every device; the profile
    page offers "Tanışlıq turunu yenidən göstərin" (`done: false`). The timestamp is in the data export.
  - Empty states: every list screen already has an empty and a forbidden state; the materials detail page no
    longer shows an empty version table. The dashboard keeps the explanatory state for accounts without imported
    data (§13.1), checked in the new E2E test with a throwaway account.
  - Copy review: no exclamation marks, informal forms, English words or codes in `messages/az.json` (1,187
    strings) or the API error catalogue. Terminology fixed to the glossary (§1.2): "bələdçi" is reserved for
    guides, so the tour is a "tanışlıq turu"; course channels are "fənn kanalları"; audiences are "fənn
    təyinatı"; the refused-file message reads the same ("qəbul olunmur") in chat and materials.
- **Consequences:** the tour content is plain text in `messages/az.json`; EN/RU follow with i18n (Phase 3).

## D-073 · 2026-10-26 · Chat load test, the bottlenecks it found, and the chat E2E suite

- **Context:** Sprint 6 asks for a k6 load test with 1,000 sockets and 50 messages per second, and an E2E suite
  for chat happy paths. The target is chat delivery p95 < 300 ms (§8, §9). Keycloak's clients have direct
  grants disabled, and enabling them would be an authentication change (to be asked first).
- **Options:** tokens through a password grant (realm change), a test-only key the API trusts (an auth bypass that
  must never ship), or signing in through the real browser flow; one large channel or course-sized ones.
- **Decision:**
  - `infra/load/prepare.py` creates `load-NNNN` Keycloak accounts (one generated password), mirrors them as
    application users and puts them into private channels "Yük testi NN"; `down` removes exactly these, their
    channels and messages (synthetic data only). `infra/load/chat.js` (k6 1.3.0 in Docker) signs every account
    in through the app's own OIDC flow (`/auth/signin` → Keycloak form → callback), with cookies handled by hand
    because the app and Keycloak mark them Secure. Each socket gets a ticket through the web proxy (session
    cookie + CSRF header) and connects with the app's Origin. Default shape: 500 accounts with two sockets each
    (laptop and phone) in 20 channels of 25 (a course group), every socket sending every 20 s, so 50 messages
    per second in the hold and 1,250 deliveries per second. Thresholds: delivery and ack p95 < 300 ms, ≥ 99 %
    sockets connected, fewer than ten refused events. `make load-up`, `make load`, `make load-down`.
  - Measured on the 4-vCPU development box, with the whole stack, Keycloak, the web dev server and k6 on the
    same machine and the API run as in production (two workers, no reload): the first run failed with delivery
    p95 1.16 s (median 167 ms). A py-spy profile showed about a fifth of a worker's time spent building the
    policy-state query (`ChannelAccess.states`, aliased statement constructed per call) and another large share
    in the per-socket heartbeat recheck, which loaded roles and permissions for every socket every 25 s although
    it only needs the account status and memberships. The Postgres session counter showed constant connection
    churn: the default pool (5 + 10 overflow) closed overflow connections after each use, and every new one paid a
    SCRAM handshake.
  - Fixes: the policy-state statement is built once with bind parameters; the heartbeat recheck reads the status
    column and the memberships only; the engine pool is 20 + 10 per process (two API workers stay below
    `max_connections` 100). After them: delivery p95 101 ms, ack p95 103 ms, median 36 ms, max 618 ms; 1,000 of
    1,000 sockets connected (one socket reconnected once during the hold), no refused events; new database
    connections during a run fell from ~1,700 to ~180.
  - The chat E2E suite (`e2e/chat.spec.ts`, built in Sprints 5–6) is the happy-path suite: real-time messages in a
    course channel and a DM across two browsers with a network drop, mentions, threads, reactions, edit and
    delete, attachments and scanning, reports, channel membership by role, membership revoked while connected,
    the phone layout and the dark-mode accessibility check. It runs green (8/8) after these changes, and the full
    functional suite (37 tests) with the seed-data check is green too.
- **Consequences:** the pilot server load test (`make load` against it, runbook) replaces these numbers as the
  reference; the Sprint 14 target (3,000 sockets, 200 msg/s) will need horizontal API workers and likely payload
  caching. A long-lived `next dev` server can stall after many edits and break whole E2E runs: restart it before
  a full run.

## D-074 · 2026-10-26 · Pilot runbook, support channel and feedback form

- **Context:** Sprint 6 closes with "pilot runbook, support channel, feedback form" for the M2 pilot on
  2027-02-22. Helpdesk tickets with a staff inbox and SLA are Sprint 18 (§8); the spec does not define the support
  channel or the form.
- **Options:** support by e-mail only, a per-person private support conversation, or one shared support channel;
  feedback as a chat message, as an e-mail, or stored with a staff list.
- **Decision:**
  - **Support channel:** a new channel type `support` (migration 0019, enum value added outside the transaction,
    a unique partial index keeps it single). The provisioning job creates "SmartAzMİU dəstəyi" and keeps in it every
    active person of the registry (students, teachers) plus every account with the `staff` or `admin` role;
    staff and admins are its moderators (slow-mode exempt, may use `@channel`), others plain members. People who
    only signed in, without registry data or a staff role, are not members. Posting follows the one chat
    policy (ADR 0004); nothing about it is special-cased. The E2E data check leaves its memberships out, because
    they follow accounts (including the e2e ones a run signs in), not seed data.
  - **Feedback form:** "Rəy bildirin" in the profile menu: category (problem, suggestion, question, other), up to
    2,000 characters, optional permission to be contacted; the current app path is attached without query or
    fragment. Ten per hour per person. Stored in `feedback`; staff with `admin.feedback.read` (staff, admin) list it
    on `/admin/feedback` (open first) and holders of `admin.feedback.handle` close or reopen it (audited as
    `feedback.handled`, without the text). The sender's e-mail is shown only when they allowed contact (§5.4).
    A person's own feedback is part of their data export. No replies from the app: answers go by e-mail or in the
    support channel until the helpdesk (Sprint 18).
  - **Runbook:** `docs/PILOT.md`: contacts by role, the pre-launch checklist (infrastructure, secrets, Keycloak
    2FA, import order, support channel, manual backup, smoke test, load check, communication, go/no-go), daily
    operation, the support channel and feedback triage routines, incident severities and degraded modes (§13.5),
    backups and rollback. The automated backup job and restore drill stay in their later sprint.
- **Consequences:** the contacts table must be filled in before the pilot week. A pilot at university scale would
  make one support channel too large; per-faculty support or the helpdesk replaces it then.

## D-075 · 2026-10-26 · Touch targets, the 4 px spacing grid and visual coverage of the Sprint 6 screens

- **Context:** the Sprint 6 audit measured controls below the 44 px touch size at 320 px (menu and bell 32 px, profile
  menu 39 × 35 px, tour buttons, stand-alone links 20–22 px, tabs, selects). The code already tried to reach 44 px
  (`after:-inset-3.5`, `min-h-11`, `pointer-coarse:h-11`), so the intent was there. The cause: `html` is 14 px (the
  type scale needs it) and Tailwind's spacing is rem-based, so every spacing utility rendered at 0.875 of the 4 px
  grid of §12: `h-9` was 31.5 px (spec: 36), `h-14` 49 px (spec: 56), `min-h-11` 38.5 px.
- **Options:** (a) patch each control with pixel values; (b) root font 16 px, which moves the whole type scale; (c) set
  Tailwind's spacing base to 4 px, which makes every existing class mean what its author assumed.
- **Decision:** (c): `--spacing: 4px` in `globals.css`. On top of it: `components/ui/touch-target.ts`, one helper
  that centres a box of at least 44 × 44 px on a control for coarse pointers (an `::after`, sized in pixels, hidden for
  fine pointers; used by `Button`, checkboxes, radios, switches, `TextLink`, breadcrumb links, the wordmark and the
  profile menu); inputs, selects, tabs, map floor links, the archive summary and reaction chips are `pointer-coarse:h-11`.
  `TextLink` gets the touch area unless it is `inline` (a link inside a sentence is exempt in WCAG 2.5.8 and a tap
  area would cover the words around it). Headings now wrap long words like body text (§13.6).
  `e2e/touch-targets.spec.ts` is the guard: on a 320 px touch device it fails when a control, or the tap area it adds,
  is under 44 px, on the dashboard and tour, profile, feedback dialog, schedule, events, chat and a channel, the
  materials catalogue, the upload form and the staff feedback and report lists. It was run against the build without
  the fix first and failed with the audit's findings.
- **Visual coverage:** `make visual` runs without an API, so signed-in screens cannot be baselined there and their
  data (dates, counts, names) is not fixed. The Sprint 6 screens are covered through the design-system page instead,
  with the real components and fixed data: tour, materials catalogue, material reports, feedback list and message
  reports (each in the panel the app puts it in), next to the chat specimen (threads, reactions, attachments,
  Markdown, composer states). The spec now also runs at 320 px (`phone-` baselines), the sticky page header is taken
  out of flow while screenshots are taken (it was captured on top of sections), and the two themes stack below 1536 px
  so wide tables get the width they have in the app. The 22 existing baselines were re-recorded after the spacing change and 42 are new (64 in all);
  they were compared section by section in contact sheets (light and dark, 1440 and 320 px) before and after. Review found
  and fixed: attachment cards whose file name collapsed to one character at phone width (the actions now wrap below
  the name).
- **Consequences:** every screen is about 14 % roomier than before, as §12 specified; all real pages were recaptured
  and the functional suite, including the 320 px overflow and accessibility checks, passes. Signed-in screens still
  have no screenshot baselines; they are checked by the e2e accessibility and overflow tests and by manual review.
  Devices whose primary pointer is fine (touch-screen laptops) get no extra tap area, by design.

## D-076 · 2026-10-26 · §13 edge-case review of Sprint 6 features (D-071 to D-074)

- **Context:** CLAUDE.md asks that every feature is checked against the §13 catalogue, with applicable cases tested and
  skipped ones noted. D-071 to D-074 did not record that review. This one was done afterwards from the code and the
  tests as they are on `main`; "tested" names the test that asserts it, "by design" means the code does it but no test
  asserts it, "open" means neither.
- **Decision (materials, D-071):**
  - Tested: a user without a not-dropped enrollment or teaching assignment gets the same `404` as an unknown subject, in
    the subject list and the catalogue (`test_who_reads_and_who_uploads`, §13.1 and §14); a student cannot upload
    (`403`), a teacher of other subjects neither sees nor learns about the subject; staff upload for any subject and
    semester and read hidden materials (`test_semester_filter_and_staff_upload`, `test_reports_and_hiding`, §13.1 roles
    are a union); type, size and consent are refused with typed errors, an upload belongs to one material only and
    cannot be claimed by another person (`test_upload_checks_type_size_and_storage`, §13.2 duplicate send); a version
    is invisible and not downloadable (`409`) until clean, an infected new version never replaces the clean one, and
    rejected files and uploads never saved (after 24 h) are removed from storage and database
    (`test_versions_scan_download_and_purge`, §13.2 infected or abandoned); ClamAV down or a file that is not what it
    claims to be is retried with backoff or rejected (`test_scan_waits_out_outages_and_rejects_wrong_content`);
    storage down refuses presigning with `503` (§13.5); a repeated report returns the first one
    (`test_reports_and_hiding`, §13.2 duplicate); inline versus attachment disposition and a one-minute link
    (`test_versions_scan_download_and_purge`, `materials.test.tsx`); dates are shown in Asia/Baku (§13.4, the fixed
    08:00 UTC specimen reads 12:00 in the visual baselines).
  - By design, not asserted: SVG and HTML are not on the allow-list (only the `.exe` refusal is tested); object keys
    are random UUIDs and downloads go through a version id whose material passes the same access check as the
    catalogue (a download by an outsider is not tested separately); a dropped enrollment stops reading at once
    because access is computed per request; a teacher replaced mid-semester loses upload rights the same way; two
    people adding a version at once are serialised by a row lock on the material.
  - Open: the upload (30 per hour) and report (10 per hour) rate limits have no test; the scan job's retry safety
    (§13.5, at-least-once) is by design (`SKIP LOCKED`, status check) but untested; the download link for a purged
    file after storage loss is untested; there is no test of two simultaneous `add_version` calls.
- **Decision (onboarding, D-072):**
  - Tested: finishing is stored on the account, repeating it keeps the first timestamp, showing it again resets it and a
    body without `done` is `422` (`test_onboarding_is_finished_once_and_can_be_shown_again`); the tour stays closed
    after a reload and returns from the profile page, an account without registry data gets the explanatory
    empty state instead of an error, and the page passes the accessibility check (`onboarding.spec.ts`, §13.1);
    steps follow the user's main role, closing stores once, and a failed save restores the tour with a message
    (`onboarding.test.tsx`, §13.6); the tour fits 320 px with 44 px targets (`touch-targets.spec.ts`).
  - By design, not asserted: the flag lives on the account, so it holds across devices and tabs (no two-browser test);
    a user with several roles gets the administrative steps if staff or admin, else the teaching steps, else the student steps (`tourSteps`, tested per role in `onboarding.test.tsx` for the main capacity only).
  - Open: `onboarded_at` in the data export has no test (the export code includes it).
- **Decision (load test and chat E2E, D-073):**
  - Tested: the chat happy paths on two browsers including a dropped network (§13.2 offline compose and backfill),
    mentions, threads, reactions, edit and delete, attachments, reports, role-based membership and revoked access
    while connected (`chat.spec.ts`, 8 tests).
  - By design, not asserted: two sockets per account measure many tabs and devices for one user, but the load test
    asserts latency, connection and refusal counts only, not read-state consistency or message order; two API
    workers ran during the measured run, without a monotonic-ID check.
  - Open: the `prepare.py up/down` scripts have no automated test. `down` was checked by hand on 2026-10-26 (500
    accounts and 20 channels created, then removed; the database and Keycloak showed none left) but only with no
    messages in the channels; the removal of messages and reactions was exercised only by the D-073 run. The result
    of D-073 was not reproduced on 2026-10-26 (D-077).
- **Decision (support channel and feedback, D-074):**
  - Tested: registry people become members and staff moderators, a signed-in stranger is not a member, losing the staff
    role demotes, an inactive account leaves the channel and posting follows the normal policy
    (`test_registry_people_and_staff_share_one_support_channel`, §13.1); feedback: trimmed text, only the path is kept,
    blank text and an unknown category are `422`, only staff list and close it (`403`, `404`), closing is idempotent
    and reversible, audit entries carry no text, the sender's e-mail appears only with consent, ten per hour per
    person, own feedback is in the export (`test_feedback.py`); the dialog sends the current page and contact choice,
    and handlers only see actions (`feedback.test.tsx`); a student sends feedback and staff close it
    (`pilot.spec.ts`).
  - By design, not asserted: feedback of a deleted account keeps its text with no sender (`user_id` is nullable and the
    list handles it); the 2,000-character limit is enforced by the schema.
  - Open: there is no idempotency key on `POST /feedback`, so a double submit that bypasses the disabled button creates
    two rows (the rate limit bounds it); the support channel's size at university scale (D-074 consequence).
- **Consequences:** the open items are test gaps, not known defects, and are not scheduled in the roadmap; they can
  be closed in the Sprint 7 hardening time or left to the pilot review. Nothing here changes behaviour.

## D-077 · 2026-10-27 · How the chat load test reaches the stack, and why it did not run on 2026-10-26

- **Context:** the Sprint 6 audit could not reproduce D-073: `make load` stopped in setup with `no login form for
  load-0001 (status 0)`. PILOT.md also asks for `make load` against the pilot server, but the Makefile fixed the
  socket address to `ws://localhost:8000/ws`.
- **Findings:** the repository's model is k6 in Docker with `--network host`, talking to the native dev servers on
  `localhost:3000` (web) and `localhost:8000` (API) and to Keycloak on `localhost:8080`, which is also the issuer the
  sign-in redirects to. On the audit machine (Docker Desktop 4.73.1) the settings file has no host-networking
  entry, and a `--network host` container got "connection refused" for all three ports while the same URLs answered
  200 from the host. So the container could not see the host's `localhost`: an environment setting, not an
  application fault, and not a certificate or authentication problem. The cleanup path was checked separately
  (500 accounts and 20 channels created, then removed; none left in the database or Keycloak).
- **Options:** switch host networking on in Docker Desktop (a machine setting, changed by its owner); run k6 natively
  instead of in Docker (a new tool on the machine, and the pinned image no longer used); add a bridge network with
  `host.docker.internal` (the sign-in redirect to `localhost:8080` and the WebSocket Origin check would break, so it
  needs app and realm changes: an authentication change, not done).
- **Decision:** no change to the networking model, authentication or the realm. `WS_URL` becomes a Makefile variable
  (default unchanged) so a run can point at another server, and the README names the host-networking prerequisite
  with a one-line check and the steps for a remote server. The result of D-073 stays the only measurement; it is
  not reproduced and not claimed as reproduced.
- **Consequences:** the load check on the pilot server is still open (PILOT.md section 2, item 8). The docstring of
  `prepare.py` says "only for local and staging stacks" while the runbook sends it to the pilot server; running it
  there creates 500 synthetic accounts in the real Keycloak and database for the length of the run, so the product
  owner has to agree to it, or the check has to run on a staging copy of the pilot server.

## D-078 · 2026-10-27 · Who uploads course materials (product owner decision)

- **Context:** §6 and §6.1 do not say who may upload materials, and it touches content ownership and copyright.
  D-071 implemented teachers and staff without a recorded approval; the Sprint 6 brief asks the product owner.
- **Options:** (1) teachers of the subject, for the semesters they teach, plus staff and admins everywhere;
  students read only; (2) the same plus enrolled students; (3) staff and admins only.
- **Decision:** the product owner chose **option 1, "Teachers + staff"**, on 2026-10-26 (asked through the question
  tool in the Sprint 6 Part 2 session). The rule stays as D-071 implemented it: `materials.upload` follows teaching
  assignments from the registry, `materials.manage` (staff, admin) uploads and hides everywhere, students only read
  and report.
- **Consequences:** copyright responsibility stays with the people who teach the course, and there is no student
  moderation queue in v1. Student-shared notes are not possible; if wanted later, they need their own decision
  (moderation load, reporting weight) and are not pulled into Sprint 7 by this one.

## D-079 · 2026-10-27 · Materials: consent history, audit of uploads, rejection notices, more access tests

- **Context:** the Sprint 6 brief asks that copyright consent is recorded in `consent_records` (purpose, policy
  version), that uploads and version changes are audited, and that the uploader is told when a file is infected.
  D-071 kept the consent on the version row only, audited reports and hiding but not uploads, and showed scan results
  on the next page load without a notice.
- **Decision:**
  - Every saved version adds a `consent_records` row with the new purpose `material_copyright`, `granted = true` and
    `policy_version = CONSENT_TEXT_VERSION`, in the same transaction as the version (migration 0020 adds the enum
    value and copies the consents of versions saved before it). The version row keeps its own copy for display.
    The record appears in the person's consent history and data export like every other consent.
  - New audit actions `material.created` and `material.version_added` (target the material, details the version id
    and number, never the file name or text). With `material.hidden` / `material.shown` (D-071) this covers
    uploads, version changes, hides and removals: removal *is* hiding, a status change with the files kept; no
    hard delete exists.
  - A version rejected by the type check or by ClamAV gives its uploader an in-app notification of the new kind
    `material.version_rejected` ("Material versiyası qəbul olunmadı", the file name, a link to the material). Like
    rejected chat attachments (D-068) it is in-app only and filed under the existing `chat` category, so the
    notification settings gain no switch that would do nothing. The object is still purged by the existing job.
  - Tests added for the gaps D-076 listed: outsider and guessed-id downloads (404, never 403), the version hidden
    after rejection, a clean later version becoming current for students, the upload and report rate limits,
    concurrent `add_version` calls (distinct numbers, no conflict), and the consent and audit rows. The E2E test
    covers the acceptance path in the browser: a clean second (here third) version becomes current, an EICAR ZIP is
    shown as "Virus aşkarlandı" to the teacher and never to students, a student downloads the current file, and a
    student without an enrollment gets "not found" for the material and does not see the subject.
  - Object keys are never accepted by the API: downloads take a version id and are checked against the reader's
    subjects before a one-minute presigned URL is issued; a guessed object key without a valid signature is refused
    by storage (D-068).
- **Consequences:** the onboarding export check that D-076 listed stays open (onboarding, not materials). Infected
  uploads also feed the `InfectedUpload` alert (D-080).

## D-080 · 2026-10-27 · Metrics, dashboard and alerts for the pilot

- **Context:** Sprint 6 asks for Prometheus metrics (WebSocket connections, messages per second, send errors, queue
  lag, scan queue depth, scan failures), a basic Grafana dashboard in `infra/grafana/`, and alert rules documented
  in the runbook, with no personal data in labels (§7, §14). The API runs two uvicorn workers; scans and other jobs
  run in a separate ARQ worker process.
- **Options:** an exporter in each process (the worker would need its own HTTP port and scrape target), or process
  metrics in the API plus figures read from Redis and Postgres when Prometheus scrapes; Prometheus and Grafana always
  on, or opt-in.
- **Decision:**
  - `prometheus-client` 0.26.0 (newest release older than ten days) in multiprocess mode: compose gives the API
    container a tmpfs at `PROMETHEUS_MULTIPROC_DIR`, so counts from both workers add up and start clean with each
    container; a worker marks itself dead on shutdown. Natively (`make dev-api`) the default registry is used.
  - Counted in the API: `smartazmiu_ws_connections` (gauge, live sum), `smartazmiu_chat_messages_sent_total`
    (new messages only, retried client ids excluded) and `smartazmiu_chat_send_errors_total`, labelled by
    `transport` (`ws`, `rest`) and the error-catalogue `code` (`internal` for an unexpected failure).
  - Read at scrape time: `smartazmiu_job_queue_depth` and `smartazmiu_job_queue_lag_seconds` (age of the oldest due
    job in ARQ's queue in Redis A; both left out, not zero, while Redis A is unreachable),
    `smartazmiu_scan_queue_depth{kind}`, `smartazmiu_scan_deferred{kind}` (postponed because the scanner or storage
    was unavailable) and `smartazmiu_scan_rejected{kind,status}` (failed type check / infected, a running total
    because rejected rows are kept). `kind` is `attachment` or `material`. The worker needs no exporter.
  - Labels are only transports, catalogue codes, job kinds and scan statuses; a test checks that a scrape contains
    no user id or name.
  - `/metrics` is internal: nginx does not route it and the web proxy forwards `/api/v1` only. Prometheus v3.15.0
    and Grafana 13.2.4 run under the compose profile `monitoring` (`make monitoring`), bound to 127.0.0.1, with
    the datasource and the dashboard "SmartAzMİU pilot" provisioned read-only from `infra/grafana/`. Grafana's
    admin password is `GRAFANA_ADMIN_PASSWORD`, generated into `.env` when missing. `make up` is unchanged.
  - Seven alert rules in `infra/prometheus/alerts.yml` (`promtool check` passes): API down, server-side send
    failures above 1 %, WebSocket connections halved in five minutes, job queue lag above two minutes, job queue
    unreadable, scan backlog, infected upload. Each links to its section in `docs/runbooks/pilot.md`.
- **Consequences:** no alert is delivered anywhere yet: Alertmanager and the receiving channel (e-mail or the
  university's chat) need the contacts the runbook still lacks, so on-call checks the Prometheus alert page as part
  of the checklist. Delivery latency is measured by k6 (D-073, D-082), not by the server. Thresholds are revisited
  after the first pilot week.

## D-081 · 2026-10-27 · Support page, runbook location, tour replay from the menu, copy review

- **Context:** the Sprint 6 brief asks for a support entry in the app (a page and a profile-menu link), the pilot
  runbook at `docs/runbooks/pilot.md` with deploy, rollback, backup and restore pointers, an on-call checklist,
  re-running provisioning and imports, revoking a session, the infected-upload alert, the exam-session freeze
  (D-047) and the alerts; the tour replayable from the profile menu; and every copy change listed. D-072 and D-074
  delivered the support channel, the feedback form, the runbook as `docs/PILOT.md` and the replay on the profile
  page only.
- **Decision:**
  - `/support` ("Dəstək"), linked from the profile menu: the support channel (a button to it for members; for people
    outside the registry, who are not members, a sentence that sends them to the form), the feedback form (the same
    dialog as the menu), answer times (weekdays 08:30–18:00, usually within four working hours) and a reminder not
    to post grades, e-mail addresses or phone numbers (§5.4). If the channel list cannot be loaded, a warning
    replaces only that section. No new endpoint: the page reads the user's own channel list.
  - The profile menu also offers "Tanışlıq turunu yenidən göstərin" (the same server call as the profile page,
    `PUT /me/onboarding {done: false}`, then the dashboard).
  - The runbook moved to `docs/runbooks/pilot.md` and gained: deploying (with the D-047 freeze and verification),
    backups with a restore drill on a separate machine, rollback, the on-call checklist, re-running provisioning
    and imports (nothing to start by hand; imports wake the jobs), revoking a session (Keycloak sign-out, effective
    within the 15-minute access-token lifetime, also for open sockets), and one section per alert of D-080,
    including the infected-upload alert.
  - Copy review (§12.8, §1.2) of all 1,252 strings in `messages/az.json` and the 99 API error messages: no
    exclamation marks, emoji, informal "sən" forms or English words; account ("hesab") and profile ("profil")
    are distinct concepts, both used consistently. Changed:
    - `chat.channelsFailed`, `chat.membersFailed`, `chat.historyFailed`, `chat.threadFailed`: "… yükləmək mümkün
      olmadı." → "… yükləmək mümkün olmadı. Yenidən cəhd edin." (what to do next).
    - `chat.attachments.previewFailed` "Önizləmə alınmadı." and `materials.previewFailed` "Önizləməni göstərmək
      mümkün olmadı." → both "Önizləməni göstərmək mümkün olmadı. Faylı endirib açın." (one wording, a next step).
    - `chat.attachments.pdfTitle` "{name} sənədinə baxış" → "{name} faylının önizləməsi" (one term for preview,
      as in materials).
    - `chat.attachments.errors.tooLarge`, `materials.form.errors.fileSize`, API `chat.attachment_too_large`,
      `materials.too_large`: "Fayl ən çox … ola bilər." → "… Daha kiçik fayl seçin."
    - API `chat.attachment_not_available`, `materials.not_available`: "Fayl hələ yoxlanılır və ya yoxlamadan
      keçməyib." → "… Bir neçə dəqiqədən sonra səhifəni yeniləyin."
    - New strings this sprint: `support.*`, `shell.support`, `notifications.kinds.materialVersionRejected`,
      `admin.audit.actions.material_created` / `material_version_added`, `privacy.purposes.material_copyright`.
    The earlier review (D-072) changed one existing string, "Bu fayl növü qəbul edilmir" → "qəbul olunmur" in the
    web file and the API catalogue; everything else in it was new tour text.
- **Consequences:** support remains one shared channel plus the form until the helpdesk (Sprint 18). The contacts
  table in the runbook still has to be filled in before the pilot week.

## D-082 · 2026-10-27 · k6 against the compose stack, the CI smoke profile, and the full 1,000-socket run

- **Context:** the Sprint 6 brief asks for `infra/k6/` scripts, a run of 1,000 sockets at 50 messages per second
  with real WebSocket tickets against the compose stack, the p95 delivery latency, machine specs and profile in a
  decision, a bottleneck and fix plan if the target is missed (without relaxing it), and a small smoke profile in
  CI. D-077 found that `make load` cannot reach the stack on this machine because Docker Desktop host networking is
  off, and that changing it is the owner's machine setting.
- **Decision:**
  - The scripts moved to `infra/k6/` (`chat.js`, `prepare.py`, unchanged behaviour). New target
    `make load-compose`: a forwarder container from the stack's own `nginx:1.30.6-alpine` image
    (`infra/k6/forward.conf`, TCP stream proxy) joins the compose network and listens on `localhost:80` (nginx) and
    `localhost:8080` (Keycloak); k6 runs in that container's network namespace with `APP_URL=http://localhost` and
    `WS_URL=ws://localhost/ws`. Sign-in redirects, cookies and the Origin check see the same addresses as a
    browser, so no host networking, realm or authentication change is needed. The forwarder is removed after the
    run, also on failure. No new dependency.
  - CI runs `make load-up` (10 accounts, 2 channels), `make load-compose` with 20 sockets at 2 messages per second
    (15 s ramp, 30 s hold, same thresholds) after the E2E suite on the same stack, and always `make load-down`.
  - **Full run, 2026-10-27,** stack at `883c4ca` (`make up`: API in Docker with two uvicorn workers, through nginx),
    profile 500 accounts × 2 sockets = 1,000 sockets in 20 channels of 25, every socket sending every 20 s
    (50 messages per second in the hold), 2 min ramp + 5 min hold. Machine: AMD Ryzen 9 8940HX (16 cores, 32
    threads), 15.2 GB RAM, Windows 11 Pro, Docker Desktop with a WSL2 VM of 32 CPUs and 7.4 GB; k6 1.3.0 on the same
    machine. Result: **1,000 of 1,000 sockets connected; delivery p95 301 ms, median 47 ms, p90 184 ms, max 5.6 s;
    ack p95 302 ms, median 49 ms**; 19,252 messages sent and 920,676 deliveries received over the 10.4-minute run
    (setup included); no failed checks. **The p95 < 300 ms target is missed by 1–2 ms**; the 300 ms threshold stays.
    The smoke profile passes (delivery p95 81 ms).
  - **Bottleneck:** the API container ran at a median 118 % and peaked at 186 % CPU, against a ceiling of 200 % for
    two single-threaded uvicorn workers, while Postgres (median 33 %), nginx (32 %), Redis B (3 %) and the forwarder
    (22 %) had room; k6 itself took up to 7.3 cores of the same machine. Fan-out already encodes each event once
    and pushes the same frame to every socket (D-062, D-073), so the time goes to the per-send path (access check,
    insert, publish) and to per-frame WebSocket writes, on two processes while 30 hardware threads stay idle. The
    tail (max 5.6 s) matches event-loop queuing during the ramp.
  - **Fix plan (Sprint 7 hardening, before the M2 pilot):** make the API worker count configurable (`API_WORKERS`,
    default 4 on the pilot server's 4 vCPU) and size the SQLAlchemy pool per process so that workers × (pool +
    overflow) stays below Postgres `max_connections` (for example 4 × (15 + 5) = 80 of 100); rerun this profile and
    record it here; if p95 is still above target, profile the send path with py-spy under load as in D-073 and
    move to two API replicas behind nginx (sockets are already stateless across processes through Redis B).
- **Consequences:** the M1 load criterion is recorded as measured, not met; the comparison with D-073 (101 ms) is
  not like for like, because D-073 ran the API natively without nginx and without the forwarder hop. The pilot
  server check (runbook section 2, item 8) still needs the product owner's agreement (D-077).

## D-083 · 2026-10-27 · Guides, advice requests and the #məsləhət digest (Sprints 7–8)

- **Context:** §5.2 defines guide eligibility, opt-in, the badge, the "Bələdçi tap" ranking, the request state
  machine and feedback; D-004 settles unaddressed requests. Several points are open: there is no chat ban yet
  (Sprint 10), "capacity" is not defined against the request states, the digest has no shape, and grades are
  personal data (§5.4).
- **Decision:**
  - **Eligibility** is one SQL rule (`mentorship/eligibility.py`): a completed, passed enrollment in a semester that
    ended before today (Baku), no active enrollment in the subject now (retake), an active account, and no
    moderator posting mute (`posting_muted_until`) in the subject's community, which stands in for a chat ban until
    bans exist. The qualifying semester is the most recent passed one; its teacher is the offering's first teacher.
    Opt-in, accept and the re-check all use it.
  - **Re-check and invitations:** `sync_guides` runs after every applied enrollments import and nightly. It revokes
    profiles that are no longer eligible (`revoked_at`, row kept), declines their still-open addressed requests,
    and runs provisioning so they leave the community; it invites eligible people without a profile once per
    subject (in-app and e-mail, new notification category `mentorship`, on by default for both).
  - **Profile:** `mentor_profiles` as in §5.7 plus `consented_at` and `revoked_at`. Grade visibility defaults to
    `hidden`; `range` shows 51–70 / 71–90 / 91–100, `exact` the grade; the teacher is shown only with
    `show_teacher`. The badge in community messages and member lists is "Bələdçi · 2025 Payız" with the Lucide
    compass, computed from active profiles; it never carries the grade. Guides stay community members through a
    provisioning arm for active profiles. The `guides_and_teachers` DM policy now lets guides through.
  - **Directory:** readers are people with a non-dropped enrollment in the subject, its active guides, and staff;
    others get the same 404 as an unknown subject. Only `available`, non-revoked guides who have not blocked (or
    been blocked by) the viewer are listed, ranked same teacher → same specialty → most recent semester → helpful
    rate → name; filters by specialty, semester and (shown) teacher.
  - **Capacity:** a guide's load is their `accepted` requests; `max_open_requests` (1–10, default 3) caps it at
    accept. At create, an addressed request also counts the guide's open ones, so a guide is not flooded with
    requests they could never accept. Accept locks the request row, then the guide's profile row: concurrent accepts
    of one request, or by one guide, are serialised and only one can pass the capacity check (tested with two
    parallel accepts and capacity 1).
  - **Requests:** one open request per requester, guide and subject, and one open unaddressed request per requester
    and subject (partial unique indexes). Blocks either way read as "guide unavailable" (D-062). Unaddressed
    requests notify every available guide of the subject and may be accepted by any of them (D-004); they cannot be
    declined, only expire. Accept creates or reuses the pair's DM without the requester's DM policy (they asked)
    and stores it on the request; the DM shows a request card with subject, topic, status, the two people, resolve
    and feedback, and the student-advice label. Expiry runs every ten minutes and is idempotent. 10 requests per
    hour per person.
  - **Feedback:** once, by the requester, after `resolved`, through a conditional update; it adjusts the guide's
    helpful or unhelpful counter, `helped_count` grows at resolve, `avg_response_minutes` is a running mean of
    create→accept. The optional note is private: never in request payloads, listed for holders of
    `admin.reports.read` on the reports page ("Bələdçi rəyləri").
  - **#məsləhət digest:** every 15 minutes, top-level posts of the last six hours in a community's `meslehet` topic
    without replies notify the subject's guides who are not paused, one notification per post (deduplicated), at
    most five such notifications per guide per Baku day.
  - **Topics in the web chat:** course and community channels show a topic bar (all, #ümumi, #suallar,
    #materiallar, #imtahan-hazırlığı, and #məsləhət in communities only, as provisioned since Sprint 5); a selected
    topic filters the loaded messages and new messages are sent into it. #materiallar links to the subject's
    Materials v1 page (channel detail now carries `subject_id`); #məsləhət shows the student-advice label.
  - **Historical enrollments:** the sample data now has 764a1's 2024 Payız and 2025 Yaz results (7 offerings, 56
    enrollments with grades, two failed), imported through the normal enrollments template; real files for the pilot
    faculty use the same template and year/term columns.
- **Consequences:** a chat ban in Sprint 10 replaces the mute in `banned()`. Requests a revoked guide already
  accepted stay open for the two people to resolve. Topic filtering is client-side over loaded pages; a server-side
  topic page (the API already accepts `topic`) can replace it when channels grow. Reputation XP (§5.2 flow 4) is
  not built; it has no spec beyond the word.

## D-084 · 2026-10-27 · Knowledge in channels: guide cards, pins, polls, anonymous questions, verified answers, saved messages (Sprint 9)

- **Context:** Sprint 9 adds §5.2 flow 5 (`course_tips`) and the Phase 2 rows of §5.3. The spec is silent on who sees
  a card's author, whether authors may upvote themselves, who may pin, how anonymous identities are revealed, what
  a verified answer must be attached to, and how saved messages behave after access is lost.
- **Decision:**
  - **Guide cards:** one per author, subject and semester (`UNIQUE`), only for a completed and passed enrollment in
    that subject and semester. Writing again upserts the same row and sends it back to `pending`; staff with
    `admin.reports.read`/`.handle` publish, reject, hide or restore it (published again) on the reports page,
    audited as `tip.reviewed`; nothing is deleted. Fields as §5.7: difficulty 1–5, weekly hours in five bands,
    key topics, resources (title with an http(s) link or a visible material of the same subject, at most ten),
    exam advice, retrospective. People who passed a subject in a semester that ended in the last 90 days get one
    in-app prompt per subject and semester (after results imports and nightly).
  - **Privacy:** students see a card's semester ("2025 Payız tələbəsi"), never the author's name, and no grade
    anywhere; the staff moderation list shows the name. The moderation note never leaves staff views.
  - **Subject page** (`/guides/{subject}/tips`, same readers as the guide directory): published cards only, count,
    average difficulty, cards per workload band, resources ranked by how many cards name them, and the 20 most
    upvoted cards.
  - **Upvotes:** one per person and card (primary key); PUT and DELETE are idempotent and the counter moves only
    when a row was really added or removed, so concurrent clicks keep it exact. Authors cannot upvote their own
    card (the simplest rule that avoids self-promotion; there is no reputation system yet).
  - **Tip reports** use the existing reports flow with the new target `tip` (published cards the reporter can
    read; not one's own), shown in the staff list with the subject and an excerpt.
  - **Pins:** at most 50 per channel, serialised on the channel row. Course teachers, channel owners and moderators
    (the policy's "privileged" flag) and staff pin; in a DM both people may. "Faydalı" lists pinned messages that
    still exist, newest pin first; messages carry `pinned`.
  - **Polls:** a poll is a message (question as body, sent through the normal posting policy, so read-only,
    archive and future exam mode apply) plus 2–10 distinct options, single or multiple choice, optional deadline.
    Voting needs the same posting permission; a vote replaces the person's earlier choice inside the poll's row
    lock; results show counts and voters; anonymous polls are not built.
  - **Anonymous questions:** only new top-level posts in `#suallar` of course and community channels. The author is
    stored as usual and the post is audited (`message.anonymous_posted`); every payload, REST or WebSocket, has
    `author = null` and `is_anonymous = true`. Teachers of the course, channel moderators and staff can look up the
    author on demand (audited as `message.author_revealed`). Mentions in an anonymous question notify nobody, and
    the web client sends no typing events while the toggle is on, so neither can reveal the author. Authors cannot
    edit or delete an anonymous question from the web client (it would have to know whose it is).
  - **Verified answers:** a reply in a thread, verified by a teacher of the offering (course channel) or an active
    guide of the subject (community). The mark names the verifier; an edit removes it (§13.2, already in place);
    the question's author is notified ("chat.answer_verified"), also for anonymous questions, without anyone else
    learning who that is.
  - **Saved messages:** a personal list (owner only). An item whose message was deleted or whose channel the owner
    can no longer read shows neither content nor channel name, only "no longer available" and a remove button.
- **Consequences:** reputation and helpful-answer XP stay in Sprint 17. A moderator console (Sprint 10) can reuse the
  anonymous-author lookup and the pin endpoints. Card prompts are in-app only.

## D-085 · 2026-10-27 · Anonymous-question author controls backlog

- **Context:** D-084 hides authors in all anonymous-question REST and WebSocket payloads. The web client cannot
  safely identify the author's own posts, so their edit and soft-delete controls are unavailable.
- **Options:** retain the limitation for review; add viewer-specific ownership or capabilities with privacy tests.
- **Decision:** record author editing and soft deletion as an unscheduled backlog item. Keep Sprint 9 behaviour;
  do not expose author identities or infer ownership from shared broadcasts or local send history.
- **Consequences:** authors currently cannot edit or delete their anonymous questions through the UI. Any future
  fix needs a privacy review and REST/WS tests for authors, other members and moderators, including reconnects
  and the existing change window. This entry does not start Sprint 10.

## D-086 · 2026-10-27 · Rule-based message holding and three-reporter hiding (Sprint 10)

- **Context:** §5.5 requires admin-configured hold/reject rules and hiding after three distinct reports, while §4.2 retains user content by soft deletion and §5.9 broadcasts common payloads to a channel. The spec does not define visibility or edit behavior for held content.
- **Options:** use `deleted_at` for every moderation state; keep a separate moderation state. The former would erase the distinction between an author's deletion and a reversible review hold.
- **Decision:** `messages.moderation` is `visible`, `held`, or `hidden`. Reject stops a new send or edit before persistence. Hold persists a message without a search vector or notifications, delivers its content to the author only, and shows a marker with redacted content to other channel members. The author and assigned channel owner/moderators can read held and auto-hidden content in REST; shared WebSocket payloads always redact it. Edits re-check the active rules; an auto-hidden message stays hidden on edit pending moderator review. Rules use both `normalize_az` forms; reject wins if rules conflict. Regex configuration excludes groups, backreferences, empty matches and patterns longer than 128 characters. Rule removal sets `disabled_at`, retaining the configuration and audit trail. Admin role alone manages rules; adding or disabling a rule is audited without copying the pattern into the audit record. The third distinct report hides a visible, undeleted message under the message row lock, clears its search vector, writes one audit record, then publishes a redacted update after commit. The original body remains for author and moderator review.
- **Consequences:** the moderator console group will add release/dismiss actions and a review queue for held messages. A clean edit releases a held message; a previously auto-hidden message needs moderator review. §13.2 permission, retry and WebSocket leak paths are covered by focused integration tests; §13.4 exam timing and §13.2 link-preview SSRF cases are assigned to their later Sprint 10 groups. No AI moderation is used.

## D-087 · 2026-10-27 · Moderator queue scope, SLA and reversible chat sanctions (Sprint 10)

- **Context:** Sprint 10 requires a report queue with an SLA, channel-scoped moderators, delete/mute/kick/ban,
  slow-mode and thread-lock actions, and audit records. The spec does not set an SLA duration or distinguish a
  kick from a channel ban.
- **Options:** expose the existing staff-wide queue to every moderator; filter it by assigned channels in SQL.
  Treat kick and ban identically; make kick remove current membership while a ban also survives provisioning.
- **Decision:** the moderation SLA is 12 hours from report creation. Staff and admins retain the global queue;
  users with the moderator role see and act only in channels where they are owner or moderator, with scope
  enforced in the report and action SQL paths. Kick removes the current membership. A channel ban records a
  durable deny before removing membership, and a global chat ban is admin-only. Mutes are exactly 1 hour,
  24 hours or 7 days. Slow mode is off, 10, 30 or 60 seconds. Thread locks apply to one root message. Message
  removal stays a soft delete; releasing held or auto-hidden content rebuilds its search vector. Moderators
  cannot act on themselves or teacher/admin targets; every action stores its reason in the moderation record
  and writes an audit event without copying message or report text.
- **Consequences:** channel bans remain effective if a provisioning sync recreates membership, while a kick may
  be reversed by a later authoritative sync. The console shows the global-ban option only to admins. Sanctions
  emit the existing channel/user WebSocket events after commit; no grade, e-mail or phone data enters payloads.

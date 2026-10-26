# SmartAzMİU — rules for Claude Code

Full spec: `docs/ROADMAP.md` (read it before any work). Decision log: `docs/DECISIONS.md`.
This file condenses §0, §3.2, §12 and §15 of the spec. If it conflicts with the spec, the spec wins.

## Working rules (§0)

- Work sprint by sprint. Do not start a sprint until the previous one's acceptance criteria pass.
- Tick finished tasks in `docs/ROADMAP.md` (`- [x]`).
- Modular monolith: one FastAPI app (`apps/api`), one Next.js app (`apps/web`). No microservices.
- Backend feature = reversible Alembic migration + Pydantic schemas + service + router + pytest (≥ 80 % module coverage).
- Frontend feature = typed API client + loading/empty/error/forbidden states + mobile layout (≥ 320 px)
  + strings in `messages/az.json` (never hard-coded) + §12 compliance.
- Sprint done only when `make lint test` passes, `make up` starts the full stack from scratch, and the sprint demo works end-to-end.
- Check every feature against the §13 edge-case catalogue; test applicable cases, note skipped ones.
- Spec silent/ambiguous → choose the simplest consistent option, implement it, log it in `docs/DECISIONS.md`
  (`date · context · options · decision · consequences`). Ask the product owner only for irreversible decisions or
  anything touching grades/personal data, authentication, data deletion or §3.2.
- Never silently drop a requirement; never add features not in the spec.
- Precedence: §3.2 out of scope > §5.4 privacy + §14 security > §12 UI standard > module specs > sprint scope.

## Out of scope — never build, even partially (§3.2)

- Any AI/LLM feature (assistant, summaries, flashcards, RAG, risk prediction, AI plagiarism, semantic search, NLP moderation).
  No AI/LLM SDKs or API keys anywhere in the repo. Moderation and search are rule-based / Postgres full-text.
- Voice/video calls (WebRTC, LiveKit). Native mobile apps (web + PWA only).
- Online tuition payment, cafeteria ordering, second-hand marketplace.

## Local environment (agreed with product owner, 2026-10-24)

- Windows 11 dev box; repo path must stay ASCII (`C:\Users\User\Projects\smartazmiu`).
- Infra (postgres, redis, S3-compatible store, keycloak, mailpit) runs in Docker; `api` and `web` run natively for development.
  `make up` must still start the full stack (including api, web, nginx) in Docker.
- Single `Makefile` (GNU make via winget `ezwinports.make`); no PowerShell task scripts. Package manager: pnpm.
- No real AzMİU data or SSO info yet: use realistic made-up Azerbaijani seed data and local Keycloak test users.
- Current scope: **Sprint 6** (chat UX, Materials v1, pilot hardening; Sprints 1–5 accepted). Stop and summarize
  for review after each task group the product owner hands over; never pull Sprint 7+ scope forward.
- Ask the product owner first for: auth changes, hard deletion of data, anything that could expose grades, and any
  CSP relaxation (e.g. for the Markdown sanitizer or KaTeX delivery).

## Git

- Commit after each finished task. Conventional Commits, English, imperative, scoped:
  `feat(chat): add exam-mode read-only enforcement`. No emoji.
- **Never add `Co-Authored-By` or "Generated with" trailers to commits or PR text** (product owner's rule).
- Remote: `github.com/evez12/smartazmiu` (`origin`). One branch per task group (`feat/...`, `ci/...`, `docs/...`,
  D-012), merged into `main` with `--no-ff` once `make lint test` is green, then branch and `main` pushed.
- New decisions continue the numbering in `docs/DECISIONS.md`; new dependencies go into the D-014 table, exact pins.
- Run `make` from Git Bash; on this box `make` lives in the winget package dir (not on PATH for agents).

## Chat rules (Sprint 5 onwards; ADRs 0002–0004, D-056–D-065)

- One authorisation function, `chat/policy.py::authorize` (pure, reason codes in fixed precedence), loaded through
  `chat/access.py::ChannelAccess`; REST, every WS event and the composer banner go through it.
  Non-members get 404 / dropped events, never a leak.
- Exam mode blocks every writer, teachers included (D-057); windows come from `ExamWindowProvider`, computed at read
  time (D-059). `muted_until` = member's own snooze; `posting_muted_until` = moderator mute (D-058).
- `messages` is partitioned by month with snowflake ids; `created_at` derives from the id. Tables referring to
  messages store `message_id` without FK: check existence in the service, clean orphans with the consistency job.
- Persist before publish (Redis B `chat:*`); idempotent sends via `message_client_ids` (7-day retention).
- Redis A (`noeviction`): sessions, ARQ queue, snowflake leases, WS tickets. Redis B (`allkeys-lru`): rate limits,
  presence, typing, pub/sub (D-053). Object storage or Redis B outages must never stop text chat (§13.5).
- No grade, e-mail or phone data in any chat REST or WS payload (§5.4). Blocks never become inferable (D-062).
- E2E: wait for `data-hydrated` (D-044); seeded accounts are read-only, use throwaway `e2e-` accounts and clean up
  what a test creates; the seed-count check must stay green (D-040, D-045, D-065).

## UI Design Standard (§12) — official, institutional, not template-looking

- Tokens live only in `apps/web/src/styles/tokens.css` (light + dark values per §12.2). No raw hex in components.
- One accent: deep institutional blue `--primary`; `--accent` (muted gold) only for highlights/badges.
- Flat: 1 px borders, no shadows on surfaces; popovers/menus/dialogs only: `0 4px 16px rgba(15,20,26,.12)`.
- Radius: 4 px controls, 6 px panels/dialogs, avatars circular, **nothing larger**.
- Spacing 4-px scale: 4, 8, 12, 16, 24, 32, 48, 64.
- Contrast ≥ 4.5:1 text (3:1 large text / UI borders), checked in CI. Colour is never the only carrier of meaning.
- Fonts: IBM Plex Sans / Mono, self-hosted, Latin + Latin Ext + Cyrillic. Weights 400/500/600 only.
  Type scale 12/16, 13/20, 14/22, 16/26, 20/28, 24/32, 30/38. Sentence-case headings. Tabular numerals for numbers.
- `<html lang="az">`; Azerbaijani glyphs `Ə ə İ ı Ş ş Ğ ğ Ç ç Ö ö Ü ü` must render in every weight.
- App shell: 56 px top bar, 240 px collapsible left nav, 1200 px max content, breadcrumb + page header
  (title, description, max one primary action). Mobile: bottom tab bar, nav as sheet, touch targets ≥ 44 px.
- Buttons 36 px (32 dense): primary / secondary / tertiary / destructive. Labels are verbs. One primary per view.
- Forms: label above, helper below, inline validation in plain Azerbaijani, never placeholder-as-label.
- Tables: 40 px rows, sticky header, no zebra, right-aligned numerics; stacked rows on mobile.
- Status tags: rectangular (4 px), text label always. Toasts ≤ 4 s for transient confirmations only.
- Empty state: one sentence + next action. Loading: layout-matching skeletons, no full-page spinners.
- Icons: Lucide only, 1.5 px stroke, 16/20 px. **No emoji in UI chrome** (only in user chat content and reactions).
- Motion: 120–160 ms opacity/position only; respect `prefers-reduced-motion`.
- Dark mode is first-class, tested on every screen.
- shadcn/ui: re-theme fully, wrap in `components/ui/*`; feature code never imports raw library defaults.
- Copy: formal-friendly "siz", short sentences, no slang, no marketing superlatives, glossary terms (§1.2).
  Errors say what happened + what to do; never show internal codes.
- Brand: neutral text wordmark "SmartAzMİU" placeholder; never imitate the AzMİU logo/coat of arms.
- **Forbidden:** gradients, glassmorphism/backdrop-blur, glow, blobs, hero with gradient headline, big rounded cards
  with soft shadows, emoji bullets/headings, three-column icon-circle feature cards, stock illustrations, default
  shadcn look, mixed icon sets, hover scale/bounce, all-caps tracked labels, centered body text,
  "Welcome back 👋", lorem ipsum, "John Doe", "Acme".
- Before a sprint is done, pass the §12.9 visual QA checklist (light + dark, 320 px + 1440 px, keyboard-only).

## Authorship hygiene (§15)

- Comments explain *why*, in concise English. No "generated by", "as an AI", "TODO: implement", or comments restating code.
- Domain-accurate names (`MentorRequestService.accept`); no `foo`/`test123` outside tests.
- No dead code, commented-out blocks, unused deps or files. Formatting via pre-commit (ruff, mypy, eslint, prettier).
- README: setup in ≤ 5 commands, architecture overview, how to test, how to add a module.
- Seed data and screenshots: realistic Azerbaijani data (names, subjects, groups like `765a2`, rooms, dates).

## Conventions to remember

- All code, comments, docs and commits in English; UI in Azerbaijani (EN/RU later).
- Time zone Asia/Baku (UTC+4, no DST); store UTC `timestamptz`; week starts Monday; Azerbaijani collation (ICU `az-AZ`).
- API: `/api/v1`, error envelope `{error:{code,message,details,request_id}}`, cursor pagination, idempotency keys,
  IDs as strings in JSON, permission filtering inside SQL queries.
- Pin exact dependency versions; commit lockfiles; record versions in `docs/DECISIONS.md`.

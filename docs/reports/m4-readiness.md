# M4 readiness report: Phase 3 (Sprints 12 to 15)

Written 2026-11-03 for the product owner. It states what is built, what was run and what is open. It makes no promise
about dates. "Decision" means an entry in `docs/DECISIONS.md`.

## 1. Phase 3 roadmap items

| Item | Status | Proof |
|---|---|---|
| Sprint 11, video lessons | **Deferred by the product owner, excluded from M4.** Not started; nothing depends on video | D-088, D-102 |
| Sprint 12, feed (posts, tags, "faydalı", comments, report) | Done | D-090, D-091 (§13 review), `community.test.tsx`, `community.spec.ts` |
| Sprint 12, Q&A forum (answers, votes, accepted, teacher-verified, tags) | Done | D-090, D-091, `community.spec.ts` |
| Sprint 12, promote a chat thread to a forum question | Done | D-090 |
| Sprint 13, assignments (deadline, files, late policy, grading) | Done | D-092, D-093 (§13 review), `coursework.spec.ts` incl. the infected file (D-110) |
| Sprint 13, quizzes (MCQ, multi, short answer, timer, auto-grading, stats) | Done | D-092, D-093, `coursework.spec.ts` |
| Sprint 14, QR attendance | Done; **geofence not built, by decision** | D-094, D-095, D-101, `attendance.spec.ts` |
| Sprint 14, exam center (timetable, countdown, room to map, past papers) | Done | D-097, D-098, D-099, D-104, D-105, `exam-center.spec.ts` |
| Sprint 14, GPA calculator with what-if | Done | D-100, D-106, D-107, `gpa.spec.ts`, `uomg.test.ts` |
| Sprint 15, personal cabinet adapter | Done against the **fake provider**; the real provider waits for the cabinet's API | D-126, D-127, `cabinet/tests` (contract, sync, API), `cabinet.spec.ts` |
| Sprint 15, PWA (manifest, worker, offline schedule and channels, install) | Done, opt-in per device, no direct messages | D-117, D-118, D-119, D-120, D-122, `pwa.spec.ts` |
| Sprint 15, i18n EN + RU, locale switcher | Done; texts are first drafts awaiting a native speaker | D-113 to D-116, `i18n.spec.ts` |
| Feature freeze | Ticked in the roadmap | D-128 |

## 2. Gate results

Everything below was run from a stack built from scratch (`make reset`, `make up`, `make seed`) unless it says
otherwise. Nothing was retried; a failure was either explained and fixed, or recorded as open.

### Final gate (2026-11-03, `main` after the merge of `chore/local-tls`)

| Check | Result |
|---|---|
| `make lint test` on `main` | Green. API 573 tests, 95 % coverage, 99 % in the cabinet module; web 574 tests (58 files) |
| GitHub Actions for the pushed `main` | All 8 jobs green: API, web, OpenAPI drift, dependency audit, image builds, visual regression, full-stack E2E and accessibility. The run of the merge commit itself was cancelled by the next push a minute later, not failed |
| Http stack, functional E2E, production build, `--workers=2 --retries=0`, seed check on | **91 of 91, twice in a row** (two runs, each after `make reset`) |
| Http stack, `pwa.spec.ts` in Chromium | **9 of 9, twice in a row** |
| Https stack (`make up-tls`), `pwa.spec.ts` in WebKit | **8 passed, 1 skipped** (the installability check uses Chrome's DevTools protocol) |
| Https stack, `pwa.spec.ts` in Firefox | **8 passed, 1 skipped** (same). Offline is driven by stopping the TLS front, with a cookie shim for `navigator.onLine` (D-133) |
| Https stack, chat over `wss://`, presigned upload, sign-in | Pass in WebKit and Firefox (D-133) |
| `make visual` | 6 of 6 (last run before the Dependabot join; no UI code changed since) |
| `pip-audit`, `pnpm audit --audit-level high` | No finding; two moderate findings (`glob`, `minimatch` under `@sentry/nextjs`) were there before |

What the gate found and fixed on the way (D-130 to D-134): a Dependabot join that broke the ten-day rule, host ports on
the flaky IPv6 loopback of Docker Desktop (now IPv4, configurable), test cleanup that depended on other services, an
onboarding save race in the test, and WebKit timing. The records-cleanup path has its own test (`records-cleanup.spec.ts`).

## 3. Everything still open

"Blocks launch" is judged against §7 (non-functional) and §14 (security) of the spec. The first block is the list the
product owner asked for; the second keeps the older items that are still open.

| Item | Reference | Blocks launch? |
|---|---|---|
| **Account deletion** is not built (design only, ADR 0005 is proposed and unmerged until its 12 decisions are answered); feed, forum, assignment and quiz rows delete with the account, chat keeps text without an author | ADR 0005, D-091, D-093, D-108, D-112 | **Yes** (§5.4 right to deletion). First Phase 4 item |
| **Real iOS Safari check**: `PushManager.getSubscription()` freezes the page in the WebKit build used for tests (the app calls it on mount; proposed fix: call it lazily with a timeout), and the WebKit service worker sometimes stays `installing` (about 2 of 16 fresh contexts, cause unknown: not shown to be the self-signed certificate, which could not be tested without trusting a CA in the system store) | D-133 | **Yes**: iOS Safari is supported (product owner, 2026-11-04); both must be checked on a real device in Phase 4 |
| **Onboarding save race**: the tour hides at once and saves in the background; leaving the page within the save time shows it again (proposed fix: `keepalive` or wait for the save) | D-133 | No |
| **Service-worker error reporting** | D-118, D-119 | No |
| **Update banner** with a real second deploy | D-118, D-119 | No |
| **Native-speaker review** of the English and Russian texts (first drafts, formal register) | D-114 | No for M4; **yes** before the languages are announced |
| **Dependabot**: eight of nine bumps of #13 to #21 were reverted (releases under ten days old). A ten-day cooldown is now configured, so they come back at the right age; security fixes are exempt | D-014, D-130, D-132 | No |
| **Keycloak login theme in English and Russian** stays Azerbaijani only | D-113 | No for M4; yes before the languages are announced |
| Real cabinet provider; the cabinet's API is unknown | D-010, D-126 | **Yes**, if grades must show real data. With no real provider, production refuses to start (`fake` is refused, `azmiu` has no implementation) |
| Audit entry on every transcript read grows the audit log | D-126 | No; revisit with real volumes |
| iOS install steps (manual check) | D-124 | **Yes** (iOS Safari is supported) |
| At-rest encryption of the stored offline copy | D-119 | No (the stored copy is the user's own data behind the browser profile; the switch is the control) |
| Exam-integrity enforcement beyond the report reason and blocked terms; blocks not applied in feed and forum | D-091 | No |
| No notification when an assignment opens or is graded; assignments and quizzes cannot be edited or deleted | D-093 | No (not in the spec) |
| No idempotency key on `POST /feedback` | D-076 | No (rate limit bounds it) |
| Download of a purged file after storage loss untested; load-test `prepare.py up/down` untested | D-076, D-077 | No |
| The launch load target (3,000 sockets, 200 messages per second, homepage 500 requests per second) has not been run; 1,000 sockets at 50 messages per second passed on the compose stack | D-082, roadmap Phase 4 | **Yes**: the load test is a Phase 4 launch item |
| Phase 4 items (load test, penetration test, backup and restore drill, production infra, data import, guide recruitment, content, accessibility audit) | roadmap Phase 4 | **Yes**, they are the exit criteria of M5 |
| First-navigation stalls and connection resets: probable cause is the IPv6 loopback of Docker Desktop (about 0.5 % of new connections dropped), fixed for development by binding to IPv4. Not proven for D-125; earlier green gates may have passed despite it | D-125, D-134 | No |
| Pilot server must set `NGINX_BIND_ADDR=0.0.0.0` (nginx only); everything else stays on loopback | D-134, `docs/runbooks/pilot.md` | **Yes**, a deployment step: without it the site is not reachable from the network |

Closed since the last version of this report: `NEVER_STORED` now lists `/api/v1/cabinet` (D-131); WebKit and Firefox
offline runs have an https front (D-133); the Dependabot divergence is joined and gated (D-130).

## 4. §12.9 visual QA checklist

Ticked only where an automated check or a recorded review is the evidence. "Manual" means no recorded check exists, so it
is not ticked.

- [x] **No gradients, glassmorphism, glow, blobs.** `design-rules.test.ts` ("uses no gradients, blur or glow effects"), runs in every `make test`.
- [x] **No radius above 6 px, no shadow on static surfaces.** `design-rules.test.ts` (radius, "uses only the overlay shadow").
- [x] **Only IBM Plex; Azerbaijani glyphs; `lang` attributes.** `design-system.spec.ts` (alphabet at every weight, Cyrillic at every weight), `i18n.spec.ts` (`lang` per language).
- [ ] **One primary action per view; consistent header and breadcrumb.** Followed by convention and reviewed per sprint, but no automated check; not ticked.
- [x] **Contrast in light and dark.** `tokens.test.ts` (values and both themes defined), axe on every functional spec (light), axe on `/design-system` which renders both themes. Dark mode on application screens is not axe-checked screen by screen: partial.
- [x] **Loading, empty, error and forbidden states.** Vitest cases per feature (for example `cabinet.test.tsx`, `community.test.tsx` after D-129). Staff-only screens show the forbidden state through the shared component. Some roles are never refused, so a few 403 states rest on the shared component only (D-091).
- [ ] **Keyboard-only pass.** `design-system.spec.ts` covers dialogs and menus; no recorded full keyboard-only pass of the screens (D-115 says the same for the language switcher); not ticked.
- [x] **320 px and 1440 px reviewed; no overflow, no truncated Azerbaijani words.** Visual baselines of 33 specimen sections at 1440 and 320 px in az, en and ru; `touch-targets.spec.ts` and `cabinet.spec.ts` check sideways scroll and 44 px targets at 320 px. Words are cut with an ellipsis in tags by design (§13.6).
- [x] **No emoji as icons; one icon set.** `design-rules.test.ts` (no emoji in chrome); Lucide only (`Icon` component).
- [ ] **Copy reviewed for tone and terminology.** Azerbaijani copy reviewed in the closeouts; English and Russian are first drafts (D-114); not ticked.
- [ ] **Screenshots of changed screens attached to the PR.** Not applicable as worded: work is merged as branches without PRs; the visual baselines in the repository take that place for specimens. Application screens have no screenshots beyond the specimens; not ticked.

## 5. Branches

- Merged into `main` and pushed: `feat/cabinet-adapter`, `test/open-gaps-sprint15`, `chore/dependabot-cooldown`, `chore/local-tls`, `test/records-cleanup`, `docs/m4-final`.
- `docs/adr-account-deletion`: ADR 0005 "Account deletion" (proposed, not accepted); on `origin`, not merged. It waits for the product owner's 12 decisions.

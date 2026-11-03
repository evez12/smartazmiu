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

## 2. Gate results (Group C closeout, stack built from scratch)

`make reset`, `make up`, `make seed`, then:

| Check | Result |
|---|---|
| `make lint test` | Green. API 570 tests, 95 % total coverage, 99 % in the cabinet module. Web 570 tests (58 files) |
| `make visual` | 6 of 6 after new specimens were recorded (`make visual-update`); old dark baselines moved by one pixel row (sub-pixel layout offset, D-128) |
| Functional E2E, production build, `--workers=2 --retries=0`, seed-data check on | **91 of 91** on the last run. Two earlier runs found a 44 px touch-target defect and test locator problems; fixed and re-run (D-128) |
| `pwa.spec.ts` Chromium | 9 of 9 |
| `pwa.spec.ts` Firefox | 4 passed, 5 skipped. Playwright's offline mode does not reach the worker's own requests in Firefox; the installability check is Chromium-only |
| `pwa.spec.ts` WebKit | 0 passed, 9 skipped. Sign-in cannot complete over plain HTTP (the app's `Secure` state cookie is not sent to `http://localhost`) |
| D-125 stall | Not seen in three full runs; cause still not established |

Nothing was retried. The skips are in the spec with their reasons (D-128).

## 3. Everything still open

"Blocks launch" is judged against §7 (non-functional) and §14 (security) of the spec.

| Item | Reference | Blocks launch? |
|---|---|---|
| Real cabinet provider; the cabinet's API is unknown | D-010, D-126 | **Yes**, if grades must show real data. With no real provider, production refuses to start (`fake` is refused, `azmiu` has no implementation) |
| Audit entry on every transcript read grows the audit log | D-126 | No; revisit with real volumes |
| `NEVER_STORED` lacks `/api/v1/cabinet` (staff endpoints; they answer `no-store` and the worker never stores them). Diff in D-127 | D-124, D-127 | No; needs the product owner's decision (cache policy) |
| Safari/WebKit and Firefox-offline runs of the PWA spec need an HTTPS front for the local stack and a way to take the network from a worker | D-128 | No for M4; **yes** before launch if iOS is supported (§7) |
| iOS install steps | D-124 | Yes if iOS is supported |
| Service-worker error reporting; update banner with a real second deploy; at-rest encryption of the stored copy | D-118, D-119 | No (the stored copy is the user's own data behind the browser profile; switch is the control) |
| Native-speaker review of English and Russian text | D-114 | No for M4; yes before the languages are announced |
| Account deletion is not built; foreign keys of feed, forum, assignment and quiz rows delete with the account, chat keeps text without an author | D-091, D-093, D-108, D-112 | **Yes** (§5.4 right to deletion) |
| Exam-integrity enforcement beyond the report reason and blocked terms; blocks not applied in feed and forum | D-091 | No |
| No notification when an assignment opens or is graded; assignments and quizzes cannot be edited or deleted | D-093 | No (not in the spec) |
| No idempotency key on `POST /feedback` | D-076 | No (rate limit bounds it) |
| Download of a purged file after storage loss untested; load-test `prepare.py up/down` untested | D-076, D-077 | No |
| The launch load target (3,000 sockets, 200 messages per second, homepage 500 requests per second) has not been run; 1,000 sockets at 50 messages per second passed on the compose stack | D-082, roadmap Phase 4 | **Yes**: the load test is a Phase 4 launch item |
| Phase 4 items (load test, penetration test, backup and restore drill, production infra, data import, guide recruitment, content, accessibility audit) | roadmap Phase 4 | **Yes**, they are the exit criteria of M5 |
| `origin/main` has merged Dependabot pull requests #13 to #21 that no gate of this work covers; local `main` holds the unpushed merge of `feat/cabinet-adapter` | D-014, D-129 | No, but the two lines must be joined and gated before anything else lands |
| D-125 first-navigation stall, cause not established | D-125 | No; record a Chromium net-log if it recurs |
| Provisional decisions awaiting the product owner | none this time | The ask-first questions of Group C were answered (CLAUDE.md and one question on 2026-11-03) |
| Bugs found by the test-gap work | none | The scan-job and concurrency tests passed; no `xfail` was needed |

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

## 5. Branches waiting for review

- `feat/cabinet-adapter`: on `origin`, merged into local `main` with `--no-ff`, **local `main` not pushed**.
- `test/open-gaps-sprint15`: the test-only gap closures (D-129) and this report; on `origin`, not merged.

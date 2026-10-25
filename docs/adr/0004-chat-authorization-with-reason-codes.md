# ADR 0004 — One chat authorisation function with reason codes

- Status: proposed (2026-10-26), awaiting product owner approval
- Related: §5.1, §5.5, §5.9, §12.7, §13.2 ("slow mode + exam mode + mute interplay"), §13.4; DECISIONS D-003

## Context

A message can be refused for many reasons: the channel is archived, read-only, in exam mode, in slow mode, the
user is muted, or is sending too fast. §13.2 asks for a single authorisation function that returns a reason code,
and for the UI to show the specific reason. The same rules apply to REST (the fallback send), every WebSocket event
(§5.9), and the composer banner (§12.7). If each path checks separately, they drift.

## Decision

### The function

`authorize(action, context) -> Decision(allowed: bool, reason: str | None, until: datetime | None,
retry_after: int | None)` is a pure function in `app/modules/chat/policy.py`, with no I/O. A loader builds
`context` with one query per channel (membership, channel state, exam window) plus the Redis counters, and every
caller (REST endpoint, WebSocket handler, the channel list that renders the banner) goes through it.

Actions: `read`, `send`, `send_attachment`, `react`, `edit`, `delete`, `mention_channel`, and later `pin`,
`verify`.

### Reasons, in precedence order

The first matching reason wins, so the user always sees the most fundamental one.

| # | Code | Applies to | Source |
|---|---|---|---|
| 1 | `chat.not_member` | every action | no `channel_members` row; REST answers 404 and WebSocket events are dropped, so existence never leaks (§13.2) |
| 2 | `chat.account_inactive` | every write | `users.status` |
| 3 | `chat.channel_archived` | every write | `channels.is_archived` (semester over) |
| 4 | `chat.exam_mode` (+ `until`) | send, react, edit; `send_attachment` | exam window from persisted exam slots, computed at read time (§5.2, §13.4, D-003) |
| 5 | `chat.channel_readonly` | send, react, edit | `channels.is_readonly` (announcement channels) or membership role `readonly` |
| 6 | `chat.muted` (+ `until`) | send, react | moderator mute of this user in this channel (§5.5) |
| 7 | `chat.slow_mode` (+ `retry_after`) | send | `channels.slow_mode_seconds` and the user's last post |
| 8 | `chat.rate_limited` (+ `retry_after`) | send | 10 messages per 10 s per user per channel (§5.5) |
| 9 | `chat.attachments_not_allowed` | send_attachment | exam mode; new accounts in communities (Sprint 10) |
| 10 | `chat.channel_mention_not_allowed` | mention_channel | only teachers and channel moderators (§5.3) |

Reading is allowed for members in every state (archived and exam-mode channels stay readable).

### Who is exempt

- Channel owners, moderators and the offering's teachers are exempt from **slow mode** (#7).
- **Exam mode (#4) applies to everyone, including teachers.** Exam questions must not be discussed during the
  exam, and teachers can still reach the class through announcements. *(Open question for the product owner:
  should teachers of the offering keep posting during their own exam window?)*
- The global staff and admin roles get no implicit chat rights; moderation acts through moderator actions
  (Sprint 10), never through bypassing this function.

### Data sources

- **Two separate mutes.** `channel_members.muted_until` in §5.7 is the member's own notification snooze ("mute
  channel", §5.3). The moderation mute (§5.5, 1 h / 24 h / 7 d) is a separate column,
  `channel_members.posting_muted_until`, set only through moderation actions and audited in `moderation_actions`.
  The schema has both from Sprint 5; the moderator console that sets the second arrives in Sprint 10.
- **Exam windows** come from `exam_slots`, which is built in Sprint 10. Until then the loader reports "no exam
  window"; the reason code, the precedence and the tests (with a stub window) exist from Sprint 5.
- **Slow mode** claims a Redis key on instance B, `chat:slow:<channel>:<user>`, with `SET NX EX
  slow_mode_seconds`. If that key is evicted, the user can post slightly early, which is harmless.
- **Rate limit** uses the existing fixed-window limiter on instance B.

### Delivery to the client

- REST errors use the envelope with the reason code and `details.until` or `details.retry_after_seconds`.
- WebSocket replies `error { id, code, detail }` to the event that was refused.
- The channel payload includes `posting: { allowed, reason, until }` for the composer banner. A
  `channel.updated` event re-sends it when state changes (exam window starts or ends, slow mode set, mute applied,
  archive).

## Consequences

- REST, WebSocket and the UI share one decision; a table-driven test covers every reason, the precedence between
  them, and the exemptions.
- The two mute columns need a plain-language distinction in the UI ("Bildirişləri susdurun" vs. "Yazmaq
  qadağandır, … qədər").
- Exam mode is fully enforceable once exam slots exist (Sprint 10) without touching any caller.

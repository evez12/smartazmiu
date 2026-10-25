# ADR 0003 — WebSocket authentication with one-use tickets

- Status: proposed (2026-10-26), awaiting product owner approval
- Related: §5.9, §14; ADR 0001; DECISIONS D-037, D-040, D-053

## Context

Browsers cannot send an `Authorization` header when opening a WebSocket, and the access token never reaches the
browser: it lives in the server-side session of the web app (D-037). §5.9 requires the query-string credential to
be a short-lived, single-purpose ticket (`POST /ws/ticket`, valid 60 s, one use), not the JWT, so tokens never land
in access logs. Sockets must also end when the account's authorisation ends, and long sessions must not drop
silently when the 15-minute access token expires.

## Decision

### Issuing

- `POST /api/v1/ws/ticket` is an ordinary authenticated API call: the browser calls it through the web app's
  proxy (CSRF-checked like every mutating request, D-025), which forwards the user's access token. The API
  returns `{ "ticket": "<43 chars>", "expires_at": "…" }`.
- The ticket is 256 random bits (`secrets.token_urlsafe(32)`). Redis instance A (never evicts, D-053) stores
  `ws:ticket:<sha256(ticket)> → {user_id, token_expires_at, issued_at}` with a 60 s TTL; the ticket itself is never
  stored. `token_expires_at` is the `exp` of the access token that minted it.
- Issuing is rate-limited per user (30 per minute, on instance B) so a broken client cannot fill Redis.

### Connecting

- The browser opens `wss://<host>/ws?ticket=<ticket>` directly; nginx proxies `/ws` to the API with the upgrade
  headers and logs the path without its query string.
- The gateway redeems the ticket with one atomic `GETDEL`: a second use, an expired ticket or an unknown one gets
  close code **4401** before any data is sent. It also checks that the `Origin` header is the app's own origin
  (cross-site WebSocket hijacking, §14), and that the account is still active.
- The connection's authorisation lasts until `token_expires_at`.

### Staying signed in

- About a minute before expiry the server sends `auth.refresh_needed`. The client gets a fresh ticket (the web app
  refreshes its tokens as usual) and sends `{ "type": "auth.refresh", "data": { "ticket": … } }`. The gateway
  redeems it, checks it belongs to the same user, and extends the connection's authorisation to the new token's
  expiry; a ticket of another user closes the socket (4401).
- Without a refresh, at expiry the server sends `error { code: "auth.expired" }` and closes with **4401**; the
  client gets a ticket and reconnects with `after=<last id>` to backfill (§5.9).
- Every event is still authorised against current membership and channel state (ADR 0004); a deactivated account
  or a role change takes effect through the per-user control channel (§5.9), which closes or unsubscribes sockets
  immediately.

### Close codes

| Code | Meaning | Client action |
|---|---|---|
| 4401 | ticket invalid, used, expired, or authorisation expired | new ticket, reconnect |
| 4403 | account inactive or origin not allowed | stop; show the status page |
| 4408 | slow consumer: send queue full (backpressure) | reconnect with backfill |
| 4429 | too many connections or events | wait for `retry_after`, reconnect |
| 1001 | server shutting down | reconnect with backoff |

## Consequences

- Nothing long-lived ever appears in a URL or a log line; a leaked ticket is worthless after its first use or
  60 s.
- The API stays stateless with respect to sign-in; it keeps only the 60 s ticket entries.
- Native development without nginx: the web app tells the browser the WebSocket URL (`WS_PUBLIC_URL`, the API
  directly on :8000 in development, `/ws` on the app's origin behind nginx); origin checks use the configured app
  URL.
- This changes how the browser authenticates to the API for one new endpoint; it does not change sign-in, sessions
  or token handling (ADR 0001, D-040).

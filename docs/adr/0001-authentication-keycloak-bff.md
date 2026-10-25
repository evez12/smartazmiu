# ADR 0001 — Authentication: Keycloak OIDC behind a backend-for-frontend

- Status: accepted (2026-10-24)
- Related: §4, §5.9, §14; DECISIONS D-005, D-016, D-018

## Context

AzMİU staff and students must sign in through a university identity provider. Access tokens are short-lived
(15 minutes), refresh tokens must not be readable by page JavaScript, staff and administrators need a second factor,
and the WebSocket gateway (Sprint 5) needs its own short-lived credential.

## Decision

- Keycloak is the identity provider (realm `smartazmiu`, exported in `infra/keycloak/realm`). A future AzMİU SSO is
  federated into this realm rather than integrated into the apps.
- The Next.js server is a confidential OIDC client running authorization code + PKCE. It keeps tokens in a server-side
  session in Redis (the browser holds only an opaque httpOnly session id, DECISIONS D-037) and forwards the access token to FastAPI as a bearer token.
- FastAPI is a stateless resource server: it validates RS256 signatures against the realm JWKS (cached, refetched on
  an unknown key id at most every 30 s), and checks issuer, audience `smartazmiu-api`, expiry and `typ=Bearer`.
- Keycloak owns global role membership; the API mirrors it per request and owns role → permission bundles.

## Consequences

- One login implementation for every client; the API never sees passwords or refresh tokens.
- Tokens are issued for the browser-facing URL while containers reach Keycloak by its internal hostname
  (`KC_HOSTNAME_BACKCHANNEL_DYNAMIC`), so issuer and JWKS URL are configured separately.

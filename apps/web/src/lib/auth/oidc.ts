import "server-only";

import * as client from "openid-client";

import { env } from "@/lib/env";

import type { TokenSet } from "./session";

let configuration: client.Configuration | undefined;

/**
 * Keycloak endpoints are configured explicitly: browsers use the public URL (which is also the issuer),
 * while this server talks to Keycloak over the internal network (DECISIONS D-005, ADR 0001).
 */
export function oidcConfiguration(): client.Configuration {
  if (configuration) return configuration;
  const publicRealm = env.oidcIssuer;
  const internalRealm = env.oidcInternalUrl;
  configuration = new client.Configuration(
    {
      issuer: publicRealm,
      authorization_endpoint: `${publicRealm}/protocol/openid-connect/auth`,
      token_endpoint: `${internalRealm}/protocol/openid-connect/token`,
      jwks_uri: `${internalRealm}/protocol/openid-connect/certs`,
      end_session_endpoint: `${internalRealm}/protocol/openid-connect/logout`,
    },
    env.oidcClientId,
    env.oidcClientSecret,
  );
  if (internalRealm.startsWith("http://")) {
    // Local stacks only: Keycloak is reached over plain HTTP inside Docker or on localhost.
    client.allowInsecureRequests(configuration);
  }
  return configuration;
}

export function callbackUrl(): string {
  return new URL("/auth/callback", env.appUrl).toString();
}

export async function beginSignIn() {
  const codeVerifier = client.randomPKCECodeVerifier();
  const state = client.randomState();
  const nonce = client.randomNonce();
  const url = client.buildAuthorizationUrl(oidcConfiguration(), {
    redirect_uri: callbackUrl(),
    scope: "openid",
    code_challenge: await client.calculatePKCECodeChallenge(codeVerifier),
    code_challenge_method: "S256",
    state,
    nonce,
  });
  return { url, codeVerifier, state, nonce };
}

export async function completeSignIn(
  currentUrl: URL,
  checks: { codeVerifier: string; state: string; nonce: string },
): Promise<TokenSet> {
  return client.authorizationCodeGrant(oidcConfiguration(), currentUrl, {
    pkceCodeVerifier: checks.codeVerifier,
    expectedState: checks.state,
    expectedNonce: checks.nonce,
    idTokenExpected: true,
  });
}

/*
 * Refresh tokens rotate and may be used once (§14). Parallel requests from one browser would race and the
 * loser would be signed out, so concurrent refreshes of the same token share a single grant.
 */
const inflightRefreshes = new Map<string, Promise<TokenSet>>();
const REFRESH_RESULT_TTL_MS = 30_000;

export function refreshTokens(refreshToken: string): Promise<TokenSet> {
  const existing = inflightRefreshes.get(refreshToken);
  if (existing) return existing;
  const grant = client.refreshTokenGrant(oidcConfiguration(), refreshToken) as Promise<TokenSet>;
  inflightRefreshes.set(refreshToken, grant);
  const forget = () =>
    setTimeout(() => inflightRefreshes.delete(refreshToken), REFRESH_RESULT_TTL_MS);
  grant.then(forget, forget);
  return grant;
}

/** Ends the Keycloak session from the server, so no logout confirmation page is shown. */
export async function endSession(refreshToken: string): Promise<void> {
  await fetch(`${env.oidcInternalUrl}/protocol/openid-connect/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: env.oidcClientId,
      client_secret: env.oidcClientSecret,
      refresh_token: refreshToken,
    }),
    signal: AbortSignal.timeout(5000),
  });
}

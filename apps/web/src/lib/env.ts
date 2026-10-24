import "server-only";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable ${name}`);
  return value;
}

/** Server configuration, read on first use so `next build` does not need runtime secrets. */
export const env = {
  /** Public origin of the web app, e.g. http://localhost behind nginx. Used for every redirect. */
  get appUrl() {
    return required("APP_URL");
  },
  get apiInternalUrl() {
    return required("API_INTERNAL_URL");
  },
  /** Browser-facing realm URL; also the token issuer. */
  get oidcIssuer() {
    return required("OIDC_ISSUER");
  },
  /** Realm URL reachable from this server (the container network in Docker). */
  get oidcInternalUrl() {
    return process.env.OIDC_INTERNAL_URL || required("OIDC_ISSUER");
  },
  get oidcClientId() {
    return required("OIDC_CLIENT_ID");
  },
  get oidcClientSecret() {
    return required("OIDC_CLIENT_SECRET");
  },
  get sessionSecret() {
    const secret = required("SESSION_SECRET");
    if (secret.length < 32) throw new Error("SESSION_SECRET must be at least 32 characters");
    return secret;
  },
  get isHttps() {
    return this.appUrl.startsWith("https://");
  },
};

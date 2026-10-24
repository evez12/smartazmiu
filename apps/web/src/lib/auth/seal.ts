import { EncryptJWT, jwtDecrypt, type JWTPayload } from "jose";

/*
 * Cookie payloads are encrypted (JWE, dir + A256GCM) with a key derived from SESSION_SECRET, so tokens are
 * neither readable nor forgeable by the browser.
 */

const keyCache = new Map<string, Promise<Uint8Array>>();

function deriveKey(secret: string): Promise<Uint8Array> {
  let key = keyCache.get(secret);
  if (!key) {
    key = crypto.subtle
      .digest("SHA-256", new TextEncoder().encode(`smartazmiu-session:${secret}`))
      .then((digest) => new Uint8Array(digest));
    keyCache.set(secret, key);
  }
  return key;
}

export async function seal<T extends object>(
  payload: T,
  secret: string,
  maxAgeSeconds: number,
): Promise<string> {
  return new EncryptJWT({ ...payload } as JWTPayload)
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    .setExpirationTime(Math.floor(Date.now() / 1000) + maxAgeSeconds)
    .encrypt(await deriveKey(secret));
}

/** Returns null for anything missing, tampered with, sealed with another key or expired. */
export async function unseal<T>(value: string | undefined, secret: string): Promise<T | null> {
  if (!value) return null;
  try {
    const { payload } = await jwtDecrypt(value, await deriveKey(secret));
    return payload as T;
  } catch {
    return null;
  }
}

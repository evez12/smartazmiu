import { isLocale, type Locale } from "@/i18n/config";
import { env } from "@/lib/env";

/** Longest the sign-in may wait for the account's language; after that the page picks it up by itself (D-114). */
const TIMEOUT_MS = 3_000;

/** The language saved on the account, or null. Never throws: signing in must not depend on this call. */
export async function accountLocale(accessToken: string): Promise<Locale | null> {
  try {
    const response = await fetch(new URL("/api/v1/me", env.apiInternalUrl), {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return null;
    const { locale } = (await response.json()) as { locale?: unknown };
    return isLocale(locale) ? locale : null;
  } catch {
    return null;
  }
}

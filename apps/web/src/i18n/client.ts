import { LOCALE_COOKIE, type Locale } from "./config";

const ONE_YEAR_SECONDS = 365 * 24 * 60 * 60;

/** Remembers the language in the browser; the next server render reads it (D-113). */
export function setLocaleCookie(locale: Locale): void {
  const secure = globalThis.location?.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${LOCALE_COOKIE}=${locale}; Path=/; Max-Age=${ONE_YEAR_SECONDS}; SameSite=Lax${secure}`;
}

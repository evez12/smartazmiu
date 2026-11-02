export const LOCALES = ["az", "en", "ru"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "az";
/** Mirrors `users.locale` for signed-out pages and for the first render on a device (D-113). */
export const LOCALE_COOKIE = "NEXT_LOCALE";
/** Every date and time is shown in Baku time, whatever the device's zone (§1.3, §13.4). */
export const TIME_ZONE = "Asia/Baku";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

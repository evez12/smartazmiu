import { DEFAULT_LOCALE, isLocale, type Locale } from "./config";

/** The best supported language of an Accept-Language header, or null when none is supported. */
export function negotiateLocale(header: string | null | undefined): Locale | null {
  if (!header) return null;
  const candidates: { locale: Locale; quality: number; position: number }[] = [];
  header.split(",").forEach((part, position) => {
    const [tag = "", ...parameters] = part.trim().split(";");
    const language = tag.trim().toLowerCase().split("-")[0];
    const quality = Number(
      parameters
        .map((parameter) => parameter.trim())
        .find((parameter) => parameter.startsWith("q="))
        ?.slice(2) ?? "1",
    );
    if (isLocale(language) && quality > 0) candidates.push({ locale: language, quality, position });
  });
  candidates.sort((a, b) => b.quality - a.quality || a.position - b.position);
  return candidates[0]?.locale ?? null;
}

/** Cookie (an explicit choice), then Accept-Language, then Azerbaijani. */
export function resolveLocale(
  cookie: string | null | undefined,
  acceptLanguage: string | null | undefined,
): Locale {
  if (isLocale(cookie)) return cookie;
  return negotiateLocale(acceptLanguage) ?? DEFAULT_LOCALE;
}

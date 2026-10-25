import { DEFAULT_LOCALE, TIME_ZONE } from "@/i18n/config";

const dateFormat = new Intl.DateTimeFormat(DEFAULT_LOCALE, {
  timeZone: TIME_ZONE,
  day: "numeric",
  month: "long",
  year: "numeric",
});
const timeFormat = new Intl.DateTimeFormat(DEFAULT_LOCALE, {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const numberFormat = new Intl.NumberFormat(DEFAULT_LOCALE);
const dayMonthFormat = new Intl.DateTimeFormat(DEFAULT_LOCALE, {
  timeZone: "UTC",
  day: "numeric",
  month: "long",
});
const weekdayFormat = new Intl.DateTimeFormat(DEFAULT_LOCALE, { timeZone: "UTC", weekday: "long" });

function capitalize(word: string): string {
  return word.charAt(0).toLocaleUpperCase(DEFAULT_LOCALE) + word.slice(1);
}

/** "24 Oktyabr 2026" (§1.3). Intl writes Azerbaijani month names in lower case. */
export function formatDate(value: Date | string): string {
  return dateFormat
    .formatToParts(new Date(value))
    .map((part) => (part.type === "month" ? capitalize(part.value) : part.value))
    .join("");
}

/** "24 Oktyabr 2026, 14:30" in Baku time. */
export function formatDateTime(value: Date | string): string {
  return `${formatDate(value)}, ${timeFormat.format(new Date(value))}`;
}

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

/** A calendar date (`2026-10-26`) has no time zone; it is formatted as the same day everywhere. */
function calendarDate(day: string): Date {
  return new Date(`${day}T00:00:00Z`);
}

/** "26 Oktyabr" for a calendar date. */
export function formatDayMonth(day: string): string {
  return dayMonthFormat
    .formatToParts(calendarDate(day))
    .map((part) => (part.type === "month" ? capitalize(part.value) : part.value))
    .join("");
}

/** "Bazar ertəsi, 26 Oktyabr" for a calendar date. */
export function formatWeekdayDate(day: string): string {
  return `${capitalize(weekdayFormat.format(calendarDate(day)))}, ${formatDayMonth(day)}`;
}

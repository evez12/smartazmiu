import { DEFAULT_LOCALE, TIME_ZONE } from "@/i18n/config";

/*
 * Month and weekday names are written out here: browsers with reduced ICU data (some Chromium builds) have no
 * Azerbaijani names and fall back to "2026 M10 26". Intl only supplies the numeric Baku date and time.
 */
const MONTHS = [
  "Yanvar",
  "Fevral",
  "Mart",
  "Aprel",
  "May",
  "İyun",
  "İyul",
  "Avqust",
  "Sentyabr",
  "Oktyabr",
  "Noyabr",
  "Dekabr",
] as const;
/** ISO order, Monday first (§1.3). */
const WEEKDAYS = [
  "Bazar ertəsi",
  "Çərşənbə axşamı",
  "Çərşənbə",
  "Cümə axşamı",
  "Cümə",
  "Şənbə",
  "Bazar",
] as const;

const bakuParts = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const numberFormat = new Intl.NumberFormat(DEFAULT_LOCALE);

type BakuParts = { year: string; month: string; day: string; hour: string; minute: string };

function partsInBaku(value: Date | string): BakuParts {
  const parts = Object.fromEntries(
    bakuParts.formatToParts(new Date(value)).map((part) => [part.type, part.value]),
  );
  return parts as BakuParts;
}

function dayMonth(day: string, month: string): string {
  return `${Number(day)} ${MONTHS[Number(month) - 1]}`;
}

/** The Baku calendar day of an instant as `2026-10-26`, for grouping by day. */
export function bakuDay(value: Date | string): string {
  const { year, month, day } = partsInBaku(value);
  return `${year}-${month}-${day}`;
}

/** "24 Oktyabr 2026" (§1.3), the Baku date of an instant. */
export function formatDate(value: Date | string): string {
  const { year, month, day } = partsInBaku(value);
  return `${dayMonth(day, month)} ${year}`;
}

/** "14:30" in Baku time. */
export function formatTime(value: Date | string): string {
  const { hour, minute } = partsInBaku(value);
  return `${hour}:${minute}`;
}

/** "24 Oktyabr 2026, 14:30" in Baku time. */
export function formatDateTime(value: Date | string): string {
  return `${formatDate(value)}, ${formatTime(value)}`;
}

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

/** "26 Oktyabr" for a calendar date (`2026-10-26`), which has no time zone. */
export function formatDayMonth(day: string): string {
  const [, month, date] = day.split("-");
  return dayMonth(date!, month!);
}

/** "Bazar ertəsi, 26 Oktyabr" for a calendar date. */
export function formatWeekdayDate(day: string): string {
  const weekday = (new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7;
  return `${WEEKDAYS[weekday]}, ${formatDayMonth(day)}`;
}

/** Baku has had no daylight saving time since 2016, so its offset is fixed (§1.3). */
const BAKU_OFFSET = "+04:00";

/** A `datetime-local` value ("2026-12-01T09:00") read as Baku time, as an ISO instant for the API. */
export function bakuInputToIso(value: string): string {
  return `${value}:00${BAKU_OFFSET}`;
}

/** An instant as a `datetime-local` value in Baku time, whatever the device's zone. */
export function isoToBakuInput(value: string): string {
  const { year, month, day, hour, minute } = partsInBaku(value);
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

/** "1 Dekabr 2026, 14:00–16:00" within a Baku day, otherwise both ends in full. */
export function formatDateTimeRange(start: string, end: string): string {
  if (isoToBakuInput(start).slice(0, 10) === isoToBakuInput(end).slice(0, 10)) {
    return `${formatDateTime(start)}–${formatTime(end)}`;
  }
  return `${formatDateTime(start)} – ${formatDateTime(end)}`;
}

import { TIME_ZONE } from "@/i18n/config";
import type { components } from "@/lib/api/schema";

export type Schedule = components["schemas"]["ScheduleOut"];
export type ScheduleDay = components["schemas"]["ScheduleDayOut"];
export type ClassItem = components["schemas"]["ClassOut"];

export type ScheduleView = "week" | "day";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const bakuDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Today's calendar date in Baku, whatever the device's time zone (§13.4). */
export function bakuToday(now: Date = new Date()): string {
  return bakuDate.format(now);
}

/** Calendar arithmetic on `YYYY-MM-DD` strings, in UTC so no time zone can shift the day. */
export function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function mondayOf(day: string): string {
  const weekday = new Date(`${day}T00:00:00Z`).getUTCDay();
  return addDays(day, -((weekday + 6) % 7));
}

/** A `date` query parameter, or today when it is missing or malformed. */
export function dayFromParam(value: string | undefined, today: string): string {
  if (!value || !ISO_DATE.test(value)) return today;
  return Number.isNaN(new Date(`${value}T00:00:00Z`).getTime()) ? today : value;
}

export function scheduleHref(view: ScheduleView, day: string): string {
  return `/schedule?view=${view}&date=${day}`;
}

export function mapHref(roomCode: string): string {
  return `/map?room=${encodeURIComponent(roomCode)}`;
}

/** Saturday and Sunday are shown only when they have classes. */
export function visibleDays(days: ScheduleDay[]): ScheduleDay[] {
  return days.filter((day, index) => index < 5 || day.classes.length > 0);
}

import type { components } from "@/lib/api/schema";

export type ExamSlot = components["schemas"]["ExamSlotOut"];
export type ExamOverlap = components["schemas"]["ExamOverlapOut"];

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export type Countdown =
  | { kind: "running" }
  | { kind: "days"; days: number; hours: number }
  | { kind: "hours"; hours: number; minutes: number }
  | { kind: "minutes"; minutes: number };

/**
 * How long until an exam starts, rounded down to the unit shown; an exam that has started and not ended is
 * "running". The clock is the caller's, so a screen can tick it and a test can fix it.
 */
export function countdown(startsAt: string, endsAt: string, now: number): Countdown {
  const until = Date.parse(startsAt) - now;
  if (until <= 0)
    return Date.parse(endsAt) > now ? { kind: "running" } : { kind: "minutes", minutes: 0 };
  if (until >= DAY) {
    return { kind: "days", days: Math.floor(until / DAY), hours: Math.floor((until % DAY) / HOUR) };
  }
  if (until >= HOUR) {
    return {
      kind: "hours",
      hours: Math.floor(until / HOUR),
      minutes: Math.floor((until % HOUR) / MINUTE),
    };
  }
  return { kind: "minutes", minutes: Math.max(1, Math.ceil(until / MINUTE)) };
}

export function mapLink(roomCode: string): string {
  return `/map?room=${encodeURIComponent(roomCode)}`;
}

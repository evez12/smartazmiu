import type { components } from "@/lib/api/schema";

export type EventItem = components["schemas"]["EventOut"];
export type EventPage = components["schemas"]["EventPageOut"];
export type Attendees = components["schemas"]["AttendeesOut"];

export const MANAGE_PERMISSION = "events.manage";
export const CHECK_IN_PERMISSION = "events.check_in";
export const PAGE_SIZE = 20;
export const TITLE_MAX = 200;
export const DESCRIPTION_MAX = 5000;

export type EventFilter = "upcoming" | "past" | "registered";

export function filterFromParams(params: { period?: string; registered?: string }): EventFilter {
  if (params.registered === "true") return "registered";
  return params.period === "past" ? "past" : "upcoming";
}

/** For what the page offers only; the API decides whether an RSVP or check-in is still possible (§13.2). */
export function hasEnded(event: EventItem, now: Date = new Date()): boolean {
  return new Date(event.ends_at) <= now;
}

export function hasStarted(event: EventItem, now: Date = new Date()): boolean {
  return new Date(event.starts_at) <= now;
}

/**
 * What may be kept on a device for offline use, and under which keys (D-117). Everything here is an allowlist: a
 * kind of data is stored only if it is named in this file, so a new endpoint is never cached by accident.
 */

export const OFFLINE_PATH = "/offline";
export const OFFLINE_DB = "smartazmiu-offline";
/** Every Cache Storage name of the service worker starts with this; wiping deletes all of them. */
export const CACHE_PREFIX = "sa-";
/** `localStorage` keys that belong to the offline feature start with this and are removed by a wipe. */
export const STORAGE_PREFIX = "sa:offline:";
/** A sign-out that was asked for offline and still has to reach the server; survives a wipe on purpose. */
export const SIGN_OUT_PENDING_KEY = "sa:signout-pending";

export const MESSAGES_PER_CHANNEL = 50;
export const MAX_CHANNELS = 40;
export const SYNC_INTERVAL_MS = 10 * 60_000;
/** Schedule weeks kept: this one and the next (§7). */
export const SCHEDULE_WEEKS = 2;

/**
 * Conversation types whose history may be stored. Direct messages are never stored (product owner, Sprint 15);
 * support and private-group conversations are as personal as a direct message and are treated the same (D-117).
 */
const STORABLE_CHANNEL_TYPES: ReadonlySet<string> = new Set([
  "course_offering",
  "subject_community",
  "academic_group",
  "faculty",
  "announcement",
  "club",
]);

export function isStorableChannel(channel: { type: string; is_archived: boolean }): boolean {
  return STORABLE_CHANNEL_TYPES.has(channel.type) && !channel.is_archived;
}

export type SnapshotKind = "schedule" | "channels" | "channel";

/** Keys are namespaced by the user id, so one account's data can never be addressed as another's (§14). */
export function snapshotKey(userId: string, kind: SnapshotKind, id = ""): string {
  return `u:${userId}:${kind}:${id}`;
}

export function belongsTo(userId: string, key: string): boolean {
  return key.startsWith(`u:${userId}:`);
}

/**
 * Data that is never kept, whatever asks for it: grades and the calculator, attendance, exams and past papers,
 * exports, attachments, tokens and socket tickets, administration and moderation (§5.4, §14, product owner).
 * The writer only takes the three allowed kinds above; this list is the second line, checked on every response
 * before it is stored. The service worker keeps its own allowlist of static files and holds no user data.
 */
const NEVER_STORED = [
  /^\/api\/v1\/me\/(grades|academics|transcript|export|exports|push-subscriptions|notification-settings)/,
  /^\/api\/v1\/(attendance|exams|gpa|uomg|admin|reports|moderation|privacy|imports|audit)/,
  /^\/api\/v1\/chat\/(ws-ticket|attachments)/,
  /^\/api\/v1\/chat\/messages\/.*\/attachments/,
  /^\/api\/v1\/.*\/(download|attachments|export|files)(\/|$)/,
  /^\/auth\//,
  /^\/smartazmiu\//,
  /^\/ws$/,
];

export function isNeverStored(pathname: string): boolean {
  return NEVER_STORED.some((pattern) => pattern.test(pathname));
}

/** A response that says it must not be stored is not stored (`Cache-Control: no-store`, `private` is allowed). */
export function forbidsStoring(headers: Headers): boolean {
  return /\bno-store\b/i.test(headers.get("cache-control") ?? "");
}

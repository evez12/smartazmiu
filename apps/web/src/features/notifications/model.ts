import type { components } from "@/lib/api/schema";

export type NotificationItem = components["schemas"]["NotificationOut"];
export type NotificationKind = NotificationItem["kind"];
export type NotificationSettings = components["schemas"]["NotificationSettingsOut"];
export type NotificationCategory = components["schemas"]["NotificationCategory"];

/** Message keys under `notifications.kinds`; next-intl reads dots as nesting, so the API codes are mapped. */
export const KIND_KEYS = {
  "announcement.published": "announcementPublished",
  "event.published": "eventPublished",
  "event.changed": "eventChanged",
  "event.cancelled": "eventCancelled",
  "schedule.changed": "scheduleChanged",
  "chat.mention": "chatMention",
  "chat.reply": "chatReply",
} as const satisfies Record<NotificationKind, string>;

/** Query keys shared by the bell and the notifications page, so marking read updates both. */
export const notificationKeys = {
  all: ["notifications"] as const,
  unread: ["notifications", "unread"] as const,
  latest: ["notifications", "latest"] as const,
};

/** How often the bell checks for new notifications while the chat socket is not connected. */
export const UNREAD_POLL_MS = 60_000;

/** Notifications per page on the notifications page. */
export const PAGE_SIZE = 20;

import type { components } from "@/lib/api/schema";
import { bakuDay } from "@/lib/format";

export type Channel = components["schemas"]["ChannelOut"];
export type ChannelDetail = components["schemas"]["ChannelDetailOut"];
export type ChannelType = Channel["type"];
export type ChatMessage = components["schemas"]["MessageOut"];
export type Author = components["schemas"]["AuthorOut"];
export type Posting = components["schemas"]["PostingOut"];
export type PostingReason = NonNullable<Posting["reason"]>;

/** Server limit for a message body (§5.9); the counter appears from `COUNTER_FROM` characters. */
export const MAX_BODY = 4000;
export const COUNTER_FROM = 3600;
/** Consecutive messages of one author within this window share one header (§12.7). */
export const COLLAPSE_MS = 5 * 60_000;
/** A queued message older than the server's backfill window is not resent without the user asking (D-058). */
export const QUEUE_LIMIT_MS = 3 * 24 * 60 * 60_000;
export const PAGE_SIZE = 50;

export const chatKeys = {
  all: ["chat"] as const,
  channels: ["chat", "channels"] as const,
  channel: (id: string) => ["chat", "channel", id] as const,
  members: (id: string) => ["chat", "members", id] as const,
};

export type SidebarGroupKey = "courses" | "communities" | "groups" | "direct";

/** Message keys under `chat.reasons`; next-intl reads dots as nesting, so the API codes are mapped. */
export const REASON_KEYS = {
  "chat.not_member": "notMember",
  "chat.account_inactive": "accountInactive",
  "chat.channel_archived": "archived",
  "chat.exam_mode": "examMode",
  "chat.channel_readonly": "readonly",
  "chat.user_blocked": "userBlocked",
  "chat.dm_unavailable": "dmUnavailable",
  "chat.muted": "muted",
  "chat.slow_mode": "slowMode",
  "chat.rate_limited": "rateLimited",
  "chat.channel_mention_not_allowed": "channelMention",
} as const satisfies Record<PostingReason, string>;

const GROUP_OF: Record<ChannelType, SidebarGroupKey> = {
  course_offering: "courses",
  subject_community: "communities",
  academic_group: "groups",
  faculty: "groups",
  announcement: "groups",
  club: "groups",
  private_group: "groups",
  dm: "direct",
};

export type SidebarGroup = { key: SidebarGroupKey; open: Channel[]; archived: Channel[] };

/** Sidebar sections in the order of §8 Sprint 5 (Fənlər, Fənn icmaları, Qrup, Şəxsi); empty ones are left out. */
export function sidebarGroups(channels: Channel[]): SidebarGroup[] {
  const order: SidebarGroupKey[] = ["courses", "communities", "groups", "direct"];
  const collator = new Intl.Collator("az");
  return order
    .map((key) => {
      const members = channels
        .filter((channel) => GROUP_OF[channel.type] === key)
        .sort((a, b) => collator.compare(a.name, b.name));
      return {
        key,
        open: members.filter((channel) => !channel.is_archived),
        archived: members.filter((channel) => channel.is_archived),
      };
    })
    .filter((group) => group.open.length + group.archived.length > 0);
}

/** Snowflake ids are 64-bit; compare them as BigInt, never as JavaScript numbers (§4.2). */
export function compareIds(a: string, b: string): number {
  const left = BigInt(a);
  const right = BigInt(b);
  return left < right ? -1 : left > right ? 1 : 0;
}

export function newestId(ids: Iterable<string>): string | null {
  let newest: string | null = null;
  for (const id of ids) if (newest === null || compareIds(id, newest) > 0) newest = id;
  return newest;
}

export type PendingState = "queued" | "sending" | "failed";

/** A message written locally that the server has not confirmed yet (§13.2: "göndərilir" / "uğursuz"). */
export type PendingMessage = {
  clientMsgId: string;
  channelId: string;
  body: string;
  state: PendingState;
  createdAt: number;
  /** Code of the last refusal, shown with the retry button. */
  error?: string;
  errorDetail?: { until?: string | null; retry_after_seconds?: number | null };
};

export type TimelineItem =
  | { kind: "day"; key: string; day: string }
  | { kind: "unread"; key: string }
  | { kind: "message"; key: string; message: ChatMessage; showHeader: boolean }
  | { kind: "pending"; key: string; pending: PendingMessage; showHeader: boolean };

/**
 * The rows of the message list: day separators, the "new messages" divider after the read marker, and
 * consecutive messages of one author within five minutes under one header (§12.7). Messages are ordered by id,
 * never by arrival (§5.9); unconfirmed ones follow in the order they were written.
 */
export function buildTimeline(
  messages: ChatMessage[],
  pending: PendingMessage[],
  options: { lastReadId: string | null; currentUserId: string },
): TimelineItem[] {
  const items: TimelineItem[] = [];
  // Held in an object: the closure below updates it, which TypeScript's narrowing cannot follow.
  const last: { row: { authorId: string | null; at: number; day: string } | null } = { row: null };
  let dividerPlaced = options.lastReadId === null;
  const sorted = [...messages].sort((a, b) => compareIds(a.id, b.id));

  const place = (authorId: string | null, at: number, day: string) => {
    const previous = last.row;
    if (previous?.day !== day) items.push({ kind: "day", key: `day-${day}`, day });
    const continues =
      previous !== null &&
      previous.day === day &&
      previous.authorId === authorId &&
      authorId !== null &&
      at - previous.at < COLLAPSE_MS;
    last.row = { authorId, at, day };
    return !continues;
  };

  for (const message of sorted) {
    const unread =
      !dividerPlaced &&
      compareIds(message.id, options.lastReadId!) > 0 &&
      message.author?.id !== options.currentUserId;
    if (unread) {
      items.push({ kind: "unread", key: "unread" });
      dividerPlaced = true;
      // The divider starts a new header; the day separator stays where it is.
      if (last.row) last.row = { ...last.row, authorId: null };
    }
    const at = Date.parse(message.created_at);
    const showHeader = place(message.author?.id ?? null, at, bakuDay(message.created_at));
    items.push({ kind: "message", key: message.id, message, showHeader });
  }
  for (const item of [...pending].sort((a, b) => a.createdAt - b.createdAt)) {
    const at = item.createdAt;
    const showHeader = place(options.currentUserId, at, bakuDay(new Date(at)));
    items.push({ kind: "pending", key: item.clientMsgId, pending: item, showHeader });
  }
  return items;
}

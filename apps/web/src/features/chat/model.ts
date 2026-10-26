import type { components } from "@/lib/api/schema";
import { bakuDay } from "@/lib/format";

export type Channel = components["schemas"]["ChannelOut"];
export type ChannelDetail = components["schemas"]["ChannelDetailOut"];
export type ChannelType = Channel["type"];
export type ChatMessage = components["schemas"]["MessageOut"];
export type Author = components["schemas"]["AuthorOut"];
export type Posting = components["schemas"]["PostingOut"];
export type PostingReason = NonNullable<Posting["reason"]>;
export type Mention = components["schemas"]["MentionOut"];
export type Thread = components["schemas"]["ThreadOut"];
export type NotifyLevel = Channel["notify_level"];

/** Server limit for a message body (§5.9); the counter appears from `COUNTER_FROM` characters. */
export const MAX_BODY = 4000;
export const COUNTER_FROM = 3600;
/** Consecutive messages of one author within this window share one header (§12.7). */
export const COLLAPSE_MS = 5 * 60_000;
/** A queued message older than the server's backfill window is not resent without the user asking (D-058). */
export const QUEUE_LIMIT_MS = 3 * 24 * 60 * 60_000;
export const PAGE_SIZE = 50;
/** The author may edit or delete a message this long after sending it (§5.3); the server decides, this hides the
 * actions that would be refused. */
export const CHANGE_WINDOW_MS = 15 * 60_000;
/**
 * The fixed reaction set, in the server's order (D-067). Written as escapes: emoji belong to user content and
 * reactions only, never to UI chrome (§12), and the source check enforces that.
 * Thumbs up, red heart, tears of joy, open mouth, crying, folded hands, party popper, check mark.
 */
export const REACTIONS = [
  "\u{1F44D}",
  "\u{2764}\u{FE0F}",
  "\u{1F602}",
  "\u{1F62E}",
  "\u{1F622}",
  "\u{1F64F}",
  "\u{1F389}",
  "\u{2705}",
] as const;

export function canChange(message: ChatMessage, currentUserId: string, now: number): boolean {
  return (
    message.author?.id === currentUserId &&
    message.deleted_at === null &&
    now - Date.parse(message.created_at) < CHANGE_WINDOW_MS
  );
}

/** A muted channel or level "none" shows no count; "mentions" shows only mentions (§5.3, D-067). */
export function badgeCounts(
  channel: Channel,
  now: number = Date.now(),
): { unread: number; mentions: number } {
  const muted = channel.muted_until !== null && Date.parse(channel.muted_until) > now;
  if (muted || channel.notify_level === "none") return { unread: 0, mentions: 0 };
  if (channel.notify_level === "mentions") return { unread: 0, mentions: channel.mention_count };
  return { unread: channel.unread_count, mentions: channel.mention_count };
}

export function isMuted(channel: Channel, now: number): boolean {
  return (
    channel.notify_level === "none" ||
    (channel.muted_until !== null && Date.parse(channel.muted_until) > now)
  );
}

const MENTION_TOKEN = /<@([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})>/gi;

export type BodyPart =
  { kind: "text"; text: string } | { kind: "mention"; id: string; name: string | null };

/**
 * Splits raw text at `<@user-id>` tokens. Names come only from the message's `mentions` (channel members); any
 * other token renders without a name, so nothing about non-members is revealed (§13.2).
 */
export function splitMentions(body: string, mentions: Mention[]): BodyPart[] {
  const names = new Map(
    mentions.map((mention) => [mention.id.toLowerCase(), mention.display_name]),
  );
  const parts: BodyPart[] = [];
  let last = 0;
  for (const match of body.matchAll(MENTION_TOKEN)) {
    if (match.index > last) parts.push({ kind: "text", text: body.slice(last, match.index) });
    const id = match[1]!.toLowerCase();
    parts.push({ kind: "mention", id, name: names.get(id) ?? null });
    last = match.index + match[0].length;
  }
  if (last < body.length) parts.push({ kind: "text", text: body.slice(last) });
  return parts;
}

/** Composer text shows `@Name`; the people picked from the suggestions become `<@id>` tokens when sent. */
export function encodeMentions(text: string, picked: ReadonlyMap<string, string>): string {
  // Longest names first, so "Aysel Məmmədova" wins over a member called "Aysel".
  const names = [...picked.keys()].sort((a, b) => b.length - a.length);
  if (!names.length) return text;
  const escaped = names.map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`@(${escaped.join("|")})(?![\\p{L}\\p{N}])`, "gu");
  return text.replace(pattern, (_, name: string) => `<@${picked.get(name)}>`);
}

/** The reverse of `encodeMentions`, for editing a sent message. */
export function decodeMentions(
  body: string,
  mentions: Mention[],
): { text: string; picked: Map<string, string> } {
  const picked = new Map<string, string>();
  const text = splitMentions(body, mentions)
    .map((part) => {
      if (part.kind === "text") return part.text;
      if (part.name === null) return `<@${part.id}>`;
      picked.set(part.name, part.id);
      return `@${part.name}`;
    })
    .join("");
  return { text, picked };
}

export const chatKeys = {
  all: ["chat"] as const,
  thread: (id: string) => ["chat", "thread", id] as const,
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
  "chat.attachments_not_allowed": "attachmentsNotAllowed",
} as const satisfies Record<PostingReason, string>;

/** Refusals of edits, deletes and reactions that are not policy reasons. */
export const CHANGE_ERROR_KEYS: Record<string, string> = {
  "chat.not_author": "notAuthor",
  "chat.change_window_expired": "changeWindowExpired",
  "chat.message_not_found": "messageNotFound",
  "chat.parent_not_found": "parentNotFound",
  "chat.reaction_not_allowed": "reactionNotAllowed",
};

const GROUP_OF: Record<ChannelType, SidebarGroupKey> = {
  course_offering: "courses",
  subject_community: "communities",
  academic_group: "groups",
  faculty: "groups",
  announcement: "groups",
  club: "groups",
  private_group: "groups",
  support: "groups",
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
  /** Set for a reply: the message shows in the thread panel, not in the channel. */
  parentId?: string;
  /** Topic of a course or community channel (§5.1); none in other channels. */
  topicId?: string;
  attachmentIds?: string[];
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
  for (const item of [...pending]
    .filter((entry) => !entry.parentId)
    .sort((a, b) => a.createdAt - b.createdAt)) {
    const at = item.createdAt;
    const showHeader = place(options.currentUserId, at, bakuDay(new Date(at)));
    items.push({ kind: "pending", key: item.clientMsgId, pending: item, showHeader });
  }
  return items;
}

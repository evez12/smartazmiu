import { compareIds, type Channel, type ChatMessage, type Mention } from "@/features/chat/model";
import { addDays, type Schedule } from "@/features/schedule/model";
import { MESSAGES_PER_CHANNEL, SCHEDULE_WEEKS } from "@/lib/offline/policy";

/**
 * What the offline view needs of a message and nothing more: no photo address, no read state, no reactions of the
 * reader, no attachment files (only their names, the files themselves are never stored; §14).
 */
export type OfflineMessage = {
  id: string;
  authorName: string | null;
  anonymous: boolean;
  /** Body of a message from a blocked author, a moderated or a deleted message is not kept (§13.2, D-062). */
  body: string;
  state: "visible" | "blocked" | "moderated" | "deleted";
  createdAt: string;
  edited: boolean;
  mentions: Mention[];
  attachmentNames: string[];
};

export type OfflineChannel = {
  id: string;
  name: string;
  context: string | null;
};

export type ChannelList = { channels: OfflineChannel[] };
export type ChannelHistory = { channel: OfflineChannel; messages: OfflineMessage[] };

export function toOfflineChannel(channel: Channel): OfflineChannel {
  return { id: channel.id, name: channel.name, context: channel.context };
}

export function toOfflineMessage(
  message: ChatMessage,
  blockedAuthors: ReadonlySet<string>,
): OfflineMessage {
  const blocked = message.author !== null && blockedAuthors.has(message.author.id);
  const deleted = message.deleted_at !== null;
  const moderated = message.moderation !== "visible";
  const state = deleted ? "deleted" : moderated ? "moderated" : blocked ? "blocked" : "visible";
  const shown = state === "visible";
  return {
    id: message.id,
    authorName: message.is_anonymous ? null : (message.author?.display_name ?? null),
    anonymous: message.is_anonymous,
    body: shown ? message.body : "",
    state,
    createdAt: message.created_at,
    edited: message.edited_at !== null,
    mentions: shown ? message.mentions : [],
    attachmentNames: shown ? message.attachments.map((file) => file.filename) : [],
  };
}

/** The newest `MESSAGES_PER_CHANNEL` top-level messages, oldest first. */
export function lastMessages(messages: Iterable<ChatMessage>): ChatMessage[] {
  return [...messages]
    .filter((message) => message.parent_id === null)
    .sort((a, b) => compareIds(a.id, b.id))
    .slice(-MESSAGES_PER_CHANNEL);
}

/**
 * Stored history plus what the open channel holds now: a message in both is taken from the newer source, and the
 * result is cut to the newest `MESSAGES_PER_CHANNEL`. A short live window never shrinks a fuller stored copy.
 */
export function mergeHistory(
  stored: readonly OfflineMessage[],
  live: readonly OfflineMessage[],
): OfflineMessage[] {
  const byId = new Map(stored.map((message) => [message.id, message]));
  for (const message of live) byId.set(message.id, message);
  return [...byId.values()].sort((a, b) => compareIds(a.id, b.id)).slice(-MESSAGES_PER_CHANNEL);
}

/** The stored fortnight as one schedule per week; `today` is set again when it is shown. */
export function splitWeeks(schedule: Schedule): Schedule[] {
  return Array.from({ length: SCHEDULE_WEEKS }, (_, week) => {
    const days = schedule.days.slice(week * 7, week * 7 + 7);
    return {
      ...schedule,
      start: addDays(schedule.start, week * 7),
      end: addDays(schedule.start, week * 7 + 6),
      days,
    };
  }).filter((week) => week.days.length > 0);
}

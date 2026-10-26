import { createStore } from "zustand/vanilla";

import {
  compareIds,
  newestId,
  REACTIONS,
  type ChatMessage,
  type PendingMessage,
  type PendingState,
  type Thread,
} from "./model";

export type ConnectionStatus = "connecting" | "online" | "offline" | "fallback";

/** The loaded part of one channel's history; not always the latest part (jump to unread, §13.2). */
export type ChannelWindow = {
  messages: Record<string, ChatMessage>;
  hasOlder: boolean;
  /** Newer messages exist that are not loaded; live messages are not appended until the gap is closed. */
  hasNewer: boolean;
  /** The reconnect gap was too large to replay: the window was dropped and reloaded (§13.2). */
  truncated: boolean;
};

export type Typist = { name: string; until: number };

/** An open thread: its root and the replies loaded so far, oldest first (§5.3). */
export type ThreadWindow = {
  root: ChatMessage;
  replies: Record<string, ChatMessage>;
  hasMore: boolean;
};

export type DeletedEvent = {
  id: string;
  channel_id: string;
  parent_id: string | null;
  deleted_at: string | null;
};

export type ReactionEvent = {
  message_id: string;
  channel_id: string;
  emoji: string;
  count: number;
  user_id: string;
  added: boolean;
};

export type ChatState = {
  status: ConnectionStatus;
  windows: Record<string, ChannelWindow>;
  threads: Record<string, ThreadWindow>;
  /** Replies already counted on their root, so a reply delivered live and again in a backfill counts once. */
  countedReplies: Record<string, true>;
  pending: Record<string, PendingMessage>;
  typing: Record<string, Record<string, Typist>>;
  presence: Record<string, "online" | "offline">;
  /** Newest message id this client has seen, the reconnect backfill cursor (§5.9). */
  lastSeenId: string | null;
  /** A channel the user lost access to while it was open; the pane shows a neutral notice (§13.2). */
  revoked: string | null;
  /** Notices from the last send per channel, e.g. an @channel that was not allowed (§13.2). */
  notices: Record<string, string[]>;
};

/**
 * `latest` replaces the window with the newest page; `older`/`newer` extend it; `unread` replaces it with the
 * page that starts at the read marker (jump to unread).
 */
export type PageDirection = "latest" | "older" | "newer" | "unread";

export type ChatActions = {
  setStatus: (status: ConnectionStatus) => void;
  loadPage: (
    channelId: string,
    page: { messages: ChatMessage[]; has_more: boolean },
    direction: PageDirection,
  ) => void;
  /** A live or replayed message; it replaces the local copy written with the same client id. */
  receive: (message: ChatMessage) => void;
  /** An edited message, or one the server re-sent (reply count); the reader's own reactions are kept. */
  update: (message: ChatMessage) => void;
  markDeleted: (event: DeletedEvent) => void;
  applyReaction: (event: ReactionEvent, currentUserId: string) => void;
  loadThread: (rootId: string, thread: Thread, mode: "replace" | "append") => void;
  truncate: (channelId: string) => void;
  queue: (pending: PendingMessage) => void;
  setPending: (
    clientMsgId: string,
    state: PendingState,
    error?: string,
    errorDetail?: PendingMessage["errorDetail"],
  ) => void;
  dropPending: (clientMsgId: string) => void;
  setTyping: (channelId: string, userId: string, name: string, until: number) => void;
  expireTyping: (now: number) => void;
  setPresence: (userId: string, status: "online" | "offline") => void;
  revoke: (channelId: string) => void;
  clearRevoked: () => void;
  setNotices: (channelId: string, notices: string[]) => void;
};

export type ChatStore = ReturnType<typeof createChatStore>;

const EMPTY_WINDOW: ChannelWindow = {
  messages: {},
  hasOlder: false,
  hasNewer: false,
  truncated: false,
};

export function createChatStore() {
  return createStore<ChatState & ChatActions>()((set) => ({
    status: "connecting",
    windows: {},
    threads: {},
    countedReplies: {},
    pending: {},
    typing: {},
    presence: {},
    lastSeenId: null,
    revoked: null,
    notices: {},

    setStatus: (status) => set({ status }),

    loadPage: (channelId, page, direction) =>
      set((state) => {
        const current = state.windows[channelId] ?? EMPTY_WINDOW;
        const fresh = direction === "latest" || direction === "unread";
        const messages = fresh ? {} : { ...current.messages };
        for (const message of page.messages) messages[message.id] = message;
        const window: ChannelWindow = {
          messages,
          hasOlder:
            direction === "unread" || (direction === "newer" ? current.hasOlder : page.has_more),
          hasNewer:
            direction === "newer" || direction === "unread"
              ? page.has_more
              : direction === "latest"
                ? false
                : current.hasNewer,
          truncated: direction === "unread" ? false : current.truncated,
        };
        return {
          windows: { ...state.windows, [channelId]: window },
          pending: withoutConfirmed(state.pending, page.messages),
          lastSeenId: newestId([
            ...(state.lastSeenId ? [state.lastSeenId] : []),
            ...page.messages.map((message) => message.id),
          ]),
        };
      }),

    receive: (message) =>
      set((state) => {
        const lastSeenId =
          state.lastSeenId && compareIds(state.lastSeenId, message.id) >= 0
            ? state.lastSeenId
            : message.id;
        const pending = withoutConfirmed(state.pending, [message]);
        if (message.parent_id) {
          const rootId = message.parent_id;
          const known =
            message.id in state.countedReplies ||
            message.id in (state.threads[rootId]?.replies ?? {});
          let next = patch(state, rootId, (root) =>
            known
              ? root
              : {
                  ...root,
                  reply_count: root.reply_count + 1,
                  last_reply_at: message.created_at,
                },
          );
          const thread = next.threads[rootId];
          if (thread && !known) {
            next = {
              ...next,
              threads: {
                ...next.threads,
                [rootId]: { ...thread, replies: { ...thread.replies, [message.id]: message } },
              },
            };
          }
          return {
            ...next,
            lastSeenId,
            pending,
            countedReplies: { ...state.countedReplies, [message.id]: true as const },
          };
        }
        const current = state.windows[message.channel_id];
        const windows =
          current && !current.hasNewer
            ? {
                ...state.windows,
                [message.channel_id]: {
                  ...current,
                  messages: { ...current.messages, [message.id]: message },
                },
              }
            : state.windows;
        return { windows, lastSeenId, pending };
      }),

    update: (message) =>
      set((state) =>
        patch(state, message.id, (current) => ({
          ...message,
          my_reactions: message.my_reactions ?? current.my_reactions,
          // Broadcasts carry clean files only; the author keeps their own files still being scanned.
          attachments: [
            ...message.attachments,
            ...current.attachments.filter(
              (own) =>
                own.status !== "clean" && !message.attachments.some((item) => item.id === own.id),
            ),
          ],
        })),
      ),

    markDeleted: (event) =>
      set((state) => {
        let next = patch(state, event.id, (current) =>
          current.deleted_at
            ? current
            : {
                ...current,
                body: "",
                deleted_at: event.deleted_at ?? new Date().toISOString(),
                reactions: [],
                my_reactions: [],
                mentions: [],
                mentions_channel: false,
                is_verified_answer: false,
              },
        );
        if (event.parent_id) {
          next = patch(next, event.parent_id, (root) => ({
            ...root,
            reply_count: Math.max(0, root.reply_count - 1),
          }));
        }
        return next;
      }),

    applyReaction: (event, currentUserId) =>
      set((state) =>
        patch(state, event.message_id, (current) => {
          const counts = new Map(current.reactions.map((item) => [item.emoji, item.count]));
          if (event.count > 0) counts.set(event.emoji, event.count);
          else counts.delete(event.emoji);
          const reactions = REACTIONS.filter((emoji) => counts.has(emoji)).map((emoji) => ({
            emoji,
            count: counts.get(emoji)!,
          }));
          let mine = current.my_reactions;
          if (event.user_id === currentUserId && mine) {
            const others = mine.filter((emoji) => emoji !== event.emoji);
            mine = event.added
              ? REACTIONS.filter((emoji) => emoji === event.emoji || others.includes(emoji))
              : others;
          }
          return { ...current, reactions, my_reactions: mine };
        }),
      ),

    loadThread: (rootId, thread, mode) =>
      set((state) => {
        const current = state.threads[rootId];
        const replies = mode === "append" && current ? { ...current.replies } : {};
        for (const reply of thread.replies) replies[reply.id] = reply;
        return {
          threads: {
            ...state.threads,
            [rootId]: { root: thread.root, replies, hasMore: thread.has_more },
          },
          pending: withoutConfirmed(state.pending, thread.replies),
        };
      }),

    truncate: (channelId) =>
      set((state) => ({
        windows: { ...state.windows, [channelId]: { ...EMPTY_WINDOW, truncated: true } },
      })),

    queue: (pending) =>
      set((state) => ({ pending: { ...state.pending, [pending.clientMsgId]: pending } })),

    setPending: (clientMsgId, pendingState, error, errorDetail) =>
      set((state) => {
        const current = state.pending[clientMsgId];
        if (!current) return {};
        return {
          pending: {
            ...state.pending,
            [clientMsgId]: { ...current, state: pendingState, error, errorDetail },
          },
        };
      }),

    dropPending: (clientMsgId) =>
      set((state) => ({
        pending: Object.fromEntries(
          Object.entries(state.pending).filter(([id]) => id !== clientMsgId),
        ),
      })),

    setTyping: (channelId, userId, name, until) =>
      set((state) => ({
        typing: {
          ...state.typing,
          [channelId]: { ...state.typing[channelId], [userId]: { name, until } },
        },
      })),

    expireTyping: (now) =>
      set((state) => {
        const typing: ChatState["typing"] = {};
        for (const [channelId, typists] of Object.entries(state.typing)) {
          const live = Object.fromEntries(
            Object.entries(typists).filter(([, typist]) => typist.until > now),
          );
          if (Object.keys(live).length) typing[channelId] = live;
        }
        return { typing };
      }),

    setPresence: (userId, status) =>
      set((state) => ({ presence: { ...state.presence, [userId]: status } })),

    revoke: (channelId) =>
      set((state) => {
        const windows = Object.fromEntries(
          Object.entries(state.windows).filter(([id]) => id !== channelId),
        );
        const threads = Object.fromEntries(
          Object.entries(state.threads).filter(
            ([, thread]) => thread.root.channel_id !== channelId,
          ),
        );
        const pending = Object.fromEntries(
          Object.entries(state.pending).filter(([, item]) => item.channelId !== channelId),
        );
        return { windows, threads, pending, revoked: channelId };
      }),

    clearRevoked: () => set({ revoked: null }),

    setNotices: (channelId, notices) =>
      set((state) =>
        !notices.length && !state.notices[channelId]
          ? {}
          : { notices: { ...state.notices, [channelId]: notices } },
      ),
  }));
}

/** Applies `change` to every loaded copy of a message: the channel window, a thread root or a reply. */
function patch(
  state: Pick<ChatState, "windows" | "threads">,
  messageId: string,
  change: (message: ChatMessage) => ChatMessage,
): Pick<ChatState, "windows" | "threads"> {
  let windows = state.windows;
  for (const [channelId, window] of Object.entries(state.windows)) {
    const found = window.messages[messageId];
    if (!found) continue;
    windows = {
      ...windows,
      [channelId]: { ...window, messages: { ...window.messages, [messageId]: change(found) } },
    };
  }
  let threads = state.threads;
  for (const [rootId, thread] of Object.entries(state.threads)) {
    if (thread.root.id === messageId) {
      threads = { ...threads, [rootId]: { ...thread, root: change(thread.root) } };
    } else if (thread.replies[messageId]) {
      const reply = thread.replies[messageId];
      threads = {
        ...threads,
        [rootId]: { ...thread, replies: { ...thread.replies, [messageId]: change(reply) } },
      };
    }
  }
  return { windows, threads };
}

function withoutConfirmed(
  pending: Record<string, PendingMessage>,
  messages: ChatMessage[],
): Record<string, PendingMessage> {
  const confirmed = new Set(messages.map((message) => message.client_msg_id));
  if (!messages.some((message) => message.client_msg_id in pending)) return pending;
  return Object.fromEntries(Object.entries(pending).filter(([id]) => !confirmed.has(id)));
}

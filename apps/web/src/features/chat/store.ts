import { createStore } from "zustand/vanilla";

import {
  compareIds,
  newestId,
  type ChatMessage,
  type PendingMessage,
  type PendingState,
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

export type ChatState = {
  status: ConnectionStatus;
  windows: Record<string, ChannelWindow>;
  pending: Record<string, PendingMessage>;
  typing: Record<string, Record<string, Typist>>;
  presence: Record<string, "online" | "offline">;
  /** Newest message id this client has seen, the reconnect backfill cursor (§5.9). */
  lastSeenId: string | null;
  /** A channel the user lost access to while it was open; the pane shows a neutral notice (§13.2). */
  revoked: string | null;
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
    pending: {},
    typing: {},
    presence: {},
    lastSeenId: null,
    revoked: null,

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
        const lastSeenId =
          state.lastSeenId && compareIds(state.lastSeenId, message.id) >= 0
            ? state.lastSeenId
            : message.id;
        return { windows, lastSeenId, pending: withoutConfirmed(state.pending, [message]) };
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
        const pending = Object.fromEntries(
          Object.entries(state.pending).filter(([, item]) => item.channelId !== channelId),
        );
        return { windows, pending, revoked: channelId };
      }),

    clearRevoked: () => set({ revoked: null }),
  }));
}

function withoutConfirmed(
  pending: Record<string, PendingMessage>,
  messages: ChatMessage[],
): Record<string, PendingMessage> {
  const confirmed = new Set(messages.map((message) => message.client_msg_id));
  if (!messages.some((message) => message.client_msg_id in pending)) return pending;
  return Object.fromEntries(Object.entries(pending).filter(([id]) => !confirmed.has(id)));
}

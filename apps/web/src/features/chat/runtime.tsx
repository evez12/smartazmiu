"use client";

import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useStore } from "zustand";

import { notificationKeys } from "@/features/notifications/model";
import { ApiRequestError, unwrap, type BrowserApi } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import {
  chatKeys,
  compareIds,
  QUEUE_LIMIT_MS,
  type Channel,
  type ChatMessage,
  type PendingMessage,
} from "./model";
import { ChatConnection, SocketError, TicketError, type ServerEvent } from "./socket";
import { createChatStore, type ChatActions, type ChatState, type ChatStore } from "./store";

/** How often the open channel is polled while the socket is down (REST fallback, §13.5). */
export const FALLBACK_POLL_MS = 5_000;
const TYPING_SHOWN_MS = 5_000;
const TYPING_SEND_MS = 3_000;
const READ_DEBOUNCE_MS = 800;

export type ChatRuntime = {
  store: ChatStore;
  currentUserId: string;
  send: (channelId: string, body: string) => void;
  retry: (clientMsgId: string) => void;
  markRead: (channelId: string, messageId: string) => void;
  typing: (channelId: string) => void;
  watchPresence: (userIds: string[]) => void;
  setActiveChannel: (channelId: string | null) => void;
};

const RuntimeContext = createContext<ChatRuntime | null>(null);

export function useChatRuntime(): ChatRuntime {
  const runtime = useContext(RuntimeContext);
  if (!runtime) throw new Error("useChatRuntime must be used inside <ChatRuntimeProvider>");
  return runtime;
}

export function useChatState<T>(selector: (state: ChatState & ChatActions) => T): T {
  return useStore(useChatRuntime().store, selector);
}

/** The socket's state for components outside chat (the bell polls only while it is not online, D-049). */
export function useChatStatus(): ChatState["status"] {
  const runtime = useContext(RuntimeContext);
  const fallbackStore = useMemo(() => createChatStore(), []);
  return useStore(runtime?.store ?? fallbackStore, (state) => (runtime ? state.status : "offline"));
}

export async function fetchChannels(api: BrowserApi) {
  return unwrap(await api.GET("/api/v1/chat/channels"));
}

export function useChannels() {
  const api = useApi();
  const status = useChatStatus();
  return useQuery({
    queryKey: chatKeys.channels,
    queryFn: () => fetchChannels(api),
    // Live updates arrive over the socket; without it the list refreshes itself.
    refetchInterval: status === "online" ? false : 30_000,
  });
}

type ChannelsData = Awaited<ReturnType<typeof fetchChannels>>;

function updateChannel(
  queryClient: QueryClient,
  channelId: string,
  change: (channel: Channel) => Channel,
): void {
  queryClient.setQueryData<ChannelsData>(chatKeys.channels, (data) =>
    data
      ? {
          ...data,
          channels: data.channels.map((channel) =>
            channel.id === channelId ? change(channel) : channel,
          ),
        }
      : data,
  );
}

/**
 * One socket per signed-in tab, for the whole app: chat, unread badges and the notification bell (§5.9).
 */
export function ChatRuntimeProvider({
  socketUrl,
  currentUserId,
  children,
}: {
  socketUrl: string;
  currentUserId: string;
  children: ReactNode;
}) {
  const api = useApi();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [store] = useState(createChatStore);
  const connection = useRef<ChatConnection | null>(null);
  const active = useRef<string | null>(null);
  const subscribed = useRef(new Set<string>());
  const watched = useRef(new Set<string>());
  const lastTyping = useRef(new Map<string, number>());
  const readTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const engine = useMemo(() => {
    const state = () => store.getState();

    const deliver = async (pending: PendingMessage): Promise<void> => {
      if (Date.now() - pending.createdAt > QUEUE_LIMIT_MS) {
        // Older than the server remembers client ids (D-058): only the user may resend it.
        state().setPending(pending.clientMsgId, "failed", "chat.queue_expired");
        return;
      }
      state().setPending(pending.clientMsgId, "sending");
      const payload = { body: pending.body, client_msg_id: pending.clientMsgId };
      try {
        if (connection.current?.isOpen) {
          await connection.current.request("message.send", {
            channel_id: pending.channelId,
            ...payload,
          });
          return;
        }
        if (state().status === "fallback" || state().status === "offline") {
          const result = unwrap(
            await api.POST("/api/v1/chat/channels/{channel_id}/messages", {
              params: { path: { channel_id: pending.channelId } },
              body: payload,
            }),
          );
          state().receive(result.message);
          return;
        }
        state().setPending(pending.clientMsgId, "queued");
      } catch (error) {
        const code =
          error instanceof SocketError || error instanceof ApiRequestError ? error.code : null;
        if (code === "chat.connection_closed" || code === "chat.ack_timeout" || code === null) {
          // Kept in the outbox and resent after the reconnect; the client id makes that safe.
          state().setPending(pending.clientMsgId, "queued");
          return;
        }
        const detail =
          error instanceof SocketError ? error.detail : (error as ApiRequestError).details;
        state().setPending(pending.clientMsgId, "failed", code, detail);
      }
    };

    const flush = async () => {
      const queued = Object.values(state().pending)
        .filter((item) => item.state !== "failed")
        .sort((a, b) => a.createdAt - b.createdAt);
      // One at a time, so the server assigns ids in the order the messages were written.
      for (const item of queued) await deliver(item);
    };

    const runtime: ChatRuntime = {
      store,
      currentUserId,
      send: (channelId, body) => {
        const pending: PendingMessage = {
          clientMsgId: crypto.randomUUID(),
          channelId,
          body,
          state: "queued",
          createdAt: Date.now(),
        };
        state().queue(pending);
        void deliver(pending);
      },
      retry: (clientMsgId) => {
        const pending = state().pending[clientMsgId];
        if (pending) void deliver({ ...pending, createdAt: Date.now() });
      },
      markRead: (channelId, messageId) => {
        const channel = queryClient
          .getQueryData<ChannelsData>(chatKeys.channels)
          ?.channels.find((item) => item.id === channelId);
        const marker = channel?.last_read_message_id;
        if (marker && compareIds(marker, messageId) >= 0 && channel.unread_count === 0) return;
        updateChannel(queryClient, channelId, (item) => ({
          ...item,
          unread_count: 0,
          last_read_message_id: messageId,
        }));
        clearTimeout(readTimers.current.get(channelId));
        readTimers.current.set(
          channelId,
          setTimeout(() => {
            const request = connection.current?.isOpen
              ? connection.current.request("read", { channel_id: channelId, message_id: messageId })
              : api.POST("/api/v1/chat/channels/{channel_id}/read", {
                  params: { path: { channel_id: channelId } },
                  body: { last_read_message_id: messageId },
                });
            void Promise.resolve(request).catch(() => undefined);
          }, READ_DEBOUNCE_MS),
        );
      },
      typing: (channelId) => {
        const now = Date.now();
        if (now - (lastTyping.current.get(channelId) ?? 0) < TYPING_SEND_MS) return;
        lastTyping.current.set(channelId, now);
        connection.current?.emit("typing", { channel_id: channelId });
      },
      watchPresence: (userIds) => {
        const fresh = userIds.filter((id) => !watched.current.has(id));
        if (!fresh.length) return;
        for (const id of fresh) watched.current.add(id);
        connection.current
          ?.request("subscribe", { channel_ids: [], presence: fresh })
          .catch(() => undefined);
      },
      setActiveChannel: (channelId) => {
        active.current = channelId;
      },
    };
    return { runtime, flush };
  }, [api, currentUserId, queryClient, store]);

  useEffect(() => {
    const state = () => store.getState();
    const subscribe = async (channelIds: string[], after: string | null) => {
      if (!connection.current?.isOpen && !channelIds.length) return;
      const presence = [...watched.current];
      const ack = await connection.current!.request("subscribe", {
        channel_ids: channelIds,
        ...(after ? { after } : {}),
        presence,
      });
      for (const id of (ack.channel_ids as string[]) ?? []) subscribed.current.add(id);
      for (const id of (ack.truncated as string[]) ?? []) {
        // Too many missed messages to replay: drop the local window, the pane reloads the latest page.
        state().truncate(id);
      }
    };

    const onEvent = (event: ServerEvent) => {
      const data = event.data;
      switch (event.type) {
        case "message.created": {
          const message = data as unknown as ChatMessage;
          state().receive(message);
          const mine = message.author?.id === currentUserId;
          if (!mine && message.channel_id !== active.current) {
            updateChannel(queryClient, message.channel_id, (channel) => ({
              ...channel,
              unread_count: Math.min(channel.unread_count + 1, 100),
            }));
          }
          break;
        }
        case "typing": {
          if (data.user_id === currentUserId) break;
          state().setTyping(
            String(data.channel_id),
            String(data.user_id),
            String(data.display_name),
            Date.now() + TYPING_SHOWN_MS,
          );
          break;
        }
        case "presence":
          state().setPresence(
            String(data.user_id),
            data.status === "online" ? "online" : "offline",
          );
          break;
        case "read.updated":
          // Another tab of this user read the channel (§13.2).
          updateChannel(queryClient, String(data.channel_id), (channel) => ({
            ...channel,
            last_read_message_id: String(data.last_read_message_id),
          }));
          void queryClient.invalidateQueries({ queryKey: chatKeys.channels });
          break;
        case "channel.updated": {
          const channelId = String(data.channel_id);
          if (data.removed) {
            subscribed.current.delete(channelId);
            queryClient.setQueryData<ChannelsData>(chatKeys.channels, (list) =>
              list ? { ...list, channels: list.channels.filter((c) => c.id !== channelId) } : list,
            );
            if (active.current === channelId) state().revoke(channelId);
            break;
          }
          void queryClient.invalidateQueries({ queryKey: chatKeys.channels });
          void queryClient.invalidateQueries({ queryKey: chatKeys.channel(channelId) });
          if (data.added) void subscribe([channelId], null).catch(() => undefined);
          break;
        }
        case "notification":
          void queryClient.invalidateQueries({ queryKey: notificationKeys.unread });
          void queryClient.invalidateQueries({ queryKey: notificationKeys.latest });
          break;
        default:
          break;
      }
    };

    const instance = new ChatConnection({
      url: socketUrl,
      getTicket: async () => {
        const result = await api.POST("/api/v1/ws/ticket");
        if (result.response.status === 401) throw new TicketError("signed_out");
        if (!result.response.ok || !result.data) throw new TicketError("unavailable");
        return result.data.ticket;
      },
      onOpen: async () => {
        subscribed.current.clear();
        const channels = await queryClient.fetchQuery({
          queryKey: chatKeys.channels,
          queryFn: () => fetchChannels(api),
          staleTime: 0,
        });
        await subscribe(
          channels.channels.map((channel) => channel.id),
          state().lastSeenId,
        );
        await engine.flush();
      },
      onEvent,
      onStatus: (status) => {
        state().setStatus(status);
        if (status === "fallback" || status === "offline") {
          void engine.flush();
        }
      },
      onStopped: (reason) => {
        if (reason === "signed_out") {
          const returnTo = `${window.location.pathname}${window.location.search}`;
          router.push(`/login?returnTo=${encodeURIComponent(returnTo)}`);
        }
      },
    });
    connection.current = instance;
    instance.start();
    const expiry = setInterval(() => state().expireTyping(Date.now()), 1000);
    const timers = readTimers.current;
    return () => {
      clearInterval(expiry);
      for (const timer of timers.values()) clearTimeout(timer);
      instance.stop();
      connection.current = null;
    };
  }, [api, currentUserId, engine, queryClient, router, socketUrl, store]);

  return <RuntimeContext value={engine.runtime}>{children}</RuntimeContext>;
}

import { addDays, bakuToday, mondayOf, type Schedule } from "@/features/schedule/model";
import { ApiRequestError, unwrap, type BrowserApi } from "@/lib/api/browser";
import {
  forbidsStoring,
  isNeverStored,
  isStorableChannel,
  MAX_CHANNELS,
  MESSAGES_PER_CHANNEL,
  SCHEDULE_WEEKS,
  SYNC_INTERVAL_MS,
} from "@/lib/offline/policy";
import { deleteSnapshots, getSnapshot, listSnapshots, putSnapshot } from "@/lib/offline/store";

import {
  lastMessages,
  toOfflineChannel,
  toOfflineMessage,
  type ChannelHistory,
  type ChannelList,
} from "./model";

/** Refuses a response that must not be kept, before anything is written (§14, D-117). */
function storable<T>(result: { data?: T; response: Response; error?: unknown }): T {
  const { pathname } = new URL(result.response.url || "http://local/");
  if (isNeverStored(pathname) || forbidsStoring(result.response.headers)) {
    throw new Error("This response must not be stored");
  }
  return unwrap(result);
}

export async function syncSchedule(api: BrowserApi, userId: string, now = new Date()) {
  const start = mondayOf(bakuToday(now));
  const schedule: Schedule = storable(
    await api.GET("/api/v1/me/schedule", {
      params: { query: { start, end: addDays(start, SCHEDULE_WEEKS * 7 - 1) } },
    }),
  );
  await putSnapshot(userId, "schedule", "", schedule, now.getTime());
}

/**
 * The channels' newest messages. A channel is refreshed only when its stored copy is older than the sync interval,
 * and a channel the user no longer belongs to loses its stored copy (§13.2: access that ends ends offline access).
 */
export async function syncChannels(
  api: BrowserApi,
  userId: string,
  { force = false, now = Date.now() }: { force?: boolean; now?: number } = {},
) {
  const list = storable(await api.GET("/api/v1/chat/channels"));
  const blocked = new Set(list.blocked_user_ids);
  const channels = list.channels.filter(isStorableChannel).slice(0, MAX_CHANNELS);
  const summary: ChannelList = { channels: channels.map(toOfflineChannel) };
  await putSnapshot(userId, "channels", "", summary, now);

  const current = new Set(channels.map((channel) => channel.id));
  const gone = (await listSnapshots<ChannelHistory>(userId, "channel")).filter(
    (entry) => !current.has(entry.data.channel.id),
  );
  await deleteSnapshots(gone.map((entry) => entry.key));

  let failure: unknown = null;
  for (const channel of channels) {
    const stored = await getSnapshot<ChannelHistory>(userId, "channel", channel.id);
    if (!force && stored && now - stored.savedAt < SYNC_INTERVAL_MS) continue;
    try {
      const page = storable(
        await api.GET("/api/v1/chat/channels/{channel_id}/messages", {
          params: { path: { channel_id: channel.id }, query: { limit: MESSAGES_PER_CHANNEL } },
        }),
      );
      const history: ChannelHistory = {
        channel: toOfflineChannel(channel),
        messages: lastMessages(page.messages).map((message) => toOfflineMessage(message, blocked)),
      };
      await putSnapshot(userId, "channel", channel.id, history, now);
    } catch (error) {
      if (error instanceof ApiRequestError && (error.status === 403 || error.status === 404)) {
        if (stored) await deleteSnapshots([stored.key]);
      } else {
        failure ??= error;
      }
    }
  }
  if (failure) throw failure;
}

export async function syncAll(api: BrowserApi, userId: string, force = false) {
  // One kind failing must not stop the other.
  const results = await Promise.allSettled([
    syncSchedule(api, userId),
    syncChannels(api, userId, { force }),
  ]);
  const failed = results.find((result) => result.status === "rejected");
  if (failed) throw failed.reason;
}

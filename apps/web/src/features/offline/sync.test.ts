import "fake-indexeddb/auto";

import { IDBFactory } from "fake-indexeddb";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BrowserApi } from "@/lib/api/browser";
import { claimDevice, setOfflineEnabled } from "@/lib/offline/device";
import { closeDatabase, getSnapshot, listSnapshots } from "@/lib/offline/store";

import type { ChannelHistory, ChannelList } from "./model";
import { syncChannels, syncSchedule } from "./sync";

const USER = "01a19d28-c354-7be3-83ff-a11dbd4de9d1";
const SESSION_END = Math.floor(Date.now() / 1000) + 3600;

function channel(id: string, type: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    name: `Kanal ${id}`,
    context: "765a2",
    type,
    is_archived: false,
    ...overrides,
  };
}

function page(count: number) {
  return {
    has_more: true,
    messages: Array.from({ length: count }, (_, index) => ({
      id: String(1000 + index),
      channel_id: "c1",
      client_msg_id: `m${index}`,
      author: { id: "u-ramin", display_name: "Ramin Əliyev", photo_url: null },
      body: `Mesaj ${index}`,
      created_at: "2026-11-02T08:30:00Z",
      edited_at: null,
      deleted_at: null,
      parent_id: null,
      is_anonymous: false,
      mentions: [],
      attachments: [],
      moderation: "visible",
    })),
  };
}

type Reply = { data?: unknown; status?: number; headers?: Record<string, string> };

/** Answers `api.GET(path)` from a table; the response carries the status and headers the real proxy would send. */
function fakeApi(routes: Record<string, Reply | ((options: unknown) => Reply)>) {
  const get = vi.fn(async (path: string, options?: unknown) => {
    const entry = routes[path];
    if (!entry) throw new Error(`Unexpected request: ${path}`);
    const reply = typeof entry === "function" ? entry(options) : entry;
    const status = reply.status ?? 200;
    const response = new Response(null, { status, headers: reply.headers });
    return status < 400
      ? { data: reply.data, response }
      : { error: { error: { code: "chat.not_found", message: "" } }, response };
  });
  return { api: { GET: get } as unknown as BrowserApi, get };
}

beforeEach(async () => {
  globalThis.indexedDB = new IDBFactory();
  await claimDevice(USER, SESSION_END);
  await setOfflineEnabled(USER, true, SESSION_END);
});

afterEach(() => closeDatabase());

describe("syncing the channels", () => {
  const list = (channels: unknown[]) => ({ data: { channels, blocked_user_ids: [] } });

  it("stores the last 50 messages of group channels and never touches a direct message", async () => {
    const { api, get } = fakeApi({
      "/api/v1/chat/channels": list([
        channel("c1", "course_offering"),
        channel("c2", "dm"),
        channel("c3", "support"),
        channel("c4", "private_group"),
        channel("c5", "club", { is_archived: true }),
      ]),
      "/api/v1/chat/channels/{channel_id}/messages": { data: page(60) },
    });

    await syncChannels(api, USER, { force: true });

    const requested = get.mock.calls
      .filter(([path]) => path.endsWith("/messages"))
      .map(([, options]) => (options as { params: { path: { channel_id: string } } }).params.path);
    expect(requested).toEqual([{ channel_id: "c1" }]);
    const stored = await getSnapshot<ChannelHistory>(USER, "channel", "c1");
    expect(stored!.data.messages).toHaveLength(50);
    expect(stored!.data.messages.at(-1)!.body).toBe("Mesaj 59");
    expect(await listSnapshots(USER, "channel")).toHaveLength(1);
    const summary = await getSnapshot<ChannelList>(USER, "channels");
    expect(summary!.data.channels.map((entry) => entry.id)).toEqual(["c1"]);
  });

  it("asks for exactly 50 messages per channel", async () => {
    const { api, get } = fakeApi({
      "/api/v1/chat/channels": list([channel("c1", "faculty")]),
      "/api/v1/chat/channels/{channel_id}/messages": { data: page(3) },
    });
    await syncChannels(api, USER, { force: true });
    const options = get.mock.calls.find(([path]) => path.endsWith("/messages"))![1] as {
      params: { query: { limit: number } };
    };
    expect(options.params.query.limit).toBe(50);
  });

  it("deletes the stored copy of a channel the user no longer belongs to", async () => {
    const both = fakeApi({
      "/api/v1/chat/channels": list([channel("c1", "faculty"), channel("c2", "faculty")]),
      "/api/v1/chat/channels/{channel_id}/messages": { data: page(2) },
    });
    await syncChannels(both.api, USER, { force: true });
    expect(await listSnapshots(USER, "channel")).toHaveLength(2);

    const one = fakeApi({
      "/api/v1/chat/channels": list([channel("c1", "faculty")]),
      "/api/v1/chat/channels/{channel_id}/messages": { data: page(2) },
    });
    await syncChannels(one.api, USER, { force: true });
    expect(
      (await listSnapshots<ChannelHistory>(USER, "channel")).map((e) => e.data.channel.id),
    ).toEqual(["c1"]);
  });

  it("deletes a channel's copy when the server says access ended, and goes on with the others", async () => {
    const first = fakeApi({
      "/api/v1/chat/channels": list([channel("c1", "faculty"), channel("c2", "faculty")]),
      "/api/v1/chat/channels/{channel_id}/messages": { data: page(2) },
    });
    await syncChannels(first.api, USER, { force: true });

    const second = fakeApi({
      "/api/v1/chat/channels": list([channel("c1", "faculty"), channel("c2", "faculty")]),
      "/api/v1/chat/channels/{channel_id}/messages": (options) =>
        (options as { params: { path: { channel_id: string } } }).params.path.channel_id === "c1"
          ? { status: 404 }
          : { data: page(5) },
    });
    await syncChannels(second.api, USER, { force: true });

    expect(await getSnapshot(USER, "channel", "c1")).toBeNull();
    expect((await getSnapshot<ChannelHistory>(USER, "channel", "c2"))!.data.messages).toHaveLength(
      5,
    );
  });

  it("skips a channel whose stored copy is still fresh, unless forced", async () => {
    const routes = {
      "/api/v1/chat/channels": list([channel("c1", "faculty")]),
      "/api/v1/chat/channels/{channel_id}/messages": { data: page(2) },
    };
    const first = fakeApi(routes);
    await syncChannels(first.api, USER, { force: true });
    const again = fakeApi(routes);
    await syncChannels(again.api, USER);
    expect(again.get.mock.calls.filter(([path]) => path.endsWith("/messages"))).toHaveLength(0);
    await syncChannels(again.api, USER, { force: true });
    expect(again.get.mock.calls.filter(([path]) => path.endsWith("/messages"))).toHaveLength(1);
  });

  it("refuses a response marked no-store and writes nothing from it", async () => {
    const { api } = fakeApi({
      "/api/v1/chat/channels": {
        ...list([channel("c1", "faculty")]),
        headers: { "cache-control": "private, no-store" },
      },
    });
    await expect(syncChannels(api, USER, { force: true })).rejects.toThrow("must not be stored");
    expect(await getSnapshot(USER, "channels")).toBeNull();
  });
});

describe("syncing the schedule", () => {
  it("asks for the current and the next week in one request, from Monday", async () => {
    const { api, get } = fakeApi({
      "/api/v1/me/schedule": {
        data: { start: "2026-11-02", end: "2026-11-15", today: "2026-11-02", days: [] },
      },
    });
    // Tuesday 3 November 2026, 12:00 in Baku.
    await syncSchedule(api, USER, new Date("2026-11-03T08:00:00Z"));
    const options = get.mock.calls[0]![1] as { params: { query: { start: string; end: string } } };
    expect(options.params.query).toEqual({ start: "2026-11-02", end: "2026-11-15" });
    expect(await getSnapshot(USER, "schedule")).not.toBeNull();
  });

  it("does not store a schedule answer that says no-store", async () => {
    const { api } = fakeApi({
      "/api/v1/me/schedule": {
        data: { start: "2026-11-02", end: "2026-11-15", today: "2026-11-02", days: [] },
        headers: { "cache-control": "no-store" },
      },
    });
    await expect(syncSchedule(api, USER)).rejects.toThrow("must not be stored");
  });
});

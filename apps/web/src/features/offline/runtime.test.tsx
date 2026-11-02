import "fake-indexeddb/auto";

import { act, render, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { IDBFactory } from "fake-indexeddb";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createChatStore } from "@/features/chat/store";
import type { ChatMessage } from "@/features/chat/model";
import { claimDevice, setOfflineEnabled } from "@/lib/offline/device";
import { SIGN_OUT_PENDING_KEY } from "@/lib/offline/policy";
import { closeDatabase, getSnapshot, putSnapshot, readDevice } from "@/lib/offline/store";

import az from "../../../messages/az.json";
import type { ChannelHistory } from "./model";
import { OfflineRuntime } from "./runtime";

const chatStore = createChatStore();
const syncAll = vi.fn(async () => undefined);
const submitSignOut = vi.fn();

vi.mock("@/lib/api/provider", () => ({ useApi: () => ({}) }));
vi.mock("@/features/chat/runtime", () => ({
  useChatRuntime: () => ({ store: chatStore }),
  useChannels: () => ({
    data: {
      blocked_user_ids: [],
      channels: [
        {
          id: "c1",
          name: "İqtisadiyyat",
          context: "765a2",
          type: "course_offering",
          is_archived: false,
        },
      ],
    },
  }),
}));
vi.mock("./sync", () => ({ syncAll: (...args: unknown[]) => syncAll(...(args as [])) }));
vi.mock("@/lib/offline/sign-out", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/offline/sign-out")>()),
  submitSignOut: (...args: unknown[]) => submitSignOut(...args),
}));

const AYSEL = "01a19d28-c354-7be3-83ff-a11dbd4de9d1";
const RAMIN = "01a19d28-c354-7be3-83ff-a11dbd4de9d2";
const inSeconds = (seconds: number) => Math.floor(Date.now() / 1000) + seconds;

function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => value });
  window.dispatchEvent(new Event(value ? "online" : "offline"));
}

function mount(userId = AYSEL, sessionEndsAt = inSeconds(3600)) {
  return render(
    <NextIntlClientProvider locale="az" messages={az}>
      <OfflineRuntime userId={userId} sessionEndsAt={sessionEndsAt} csrfToken="csrf-token" />
    </NextIntlClientProvider>,
  );
}

function message(id: string, body: string): ChatMessage {
  return {
    id,
    channel_id: "c1",
    client_msg_id: id,
    author: { id: "u-ramin", display_name: "Ramin Əliyev", photo_url: null },
    body,
    created_at: "2026-11-02T08:30:00Z",
    edited_at: null,
    deleted_at: null,
    parent_id: null,
    is_anonymous: false,
    mentions: [],
    attachments: [],
    moderation: "visible",
  } as unknown as ChatMessage;
}

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
  localStorage.clear();
  syncAll.mockClear();
  submitSignOut.mockClear();
  setOnline(true);
});

afterEach(async () => {
  vi.useRealTimers();
  await closeDatabase();
  chatStore.setState({ windows: {} });
});

describe("the offline runtime", () => {
  it("makes the signed-in user the owner of the device with storing off", async () => {
    mount();
    await waitFor(async () =>
      expect(await readDevice()).toMatchObject({ userId: AYSEL, enabled: false }),
    );
    expect(syncAll).not.toHaveBeenCalled();
  });

  it("deletes the data of the previous user before the new one is registered", async () => {
    await claimDevice(AYSEL, inSeconds(3600));
    await setOfflineEnabled(AYSEL, true, inSeconds(3600));
    await putSnapshot(AYSEL, "schedule", "", { days: [] });

    mount(RAMIN);

    await waitFor(async () => expect((await readDevice())?.userId).toBe(RAMIN));
    expect(await getSnapshot(AYSEL, "schedule")).toBeNull();
  });

  it("syncs when storing is on and the device is online, and not while it is offline", async () => {
    await claimDevice(AYSEL, inSeconds(3600));
    await setOfflineEnabled(AYSEL, true, inSeconds(3600));
    setOnline(false);
    mount();
    await act(async () => undefined);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(syncAll).not.toHaveBeenCalled();

    act(() => setOnline(true));
    await waitFor(() => expect(syncAll).toHaveBeenCalledWith(expect.anything(), AYSEL, true));
  });

  it("deletes everything when the session reaches its absolute end, while the page is still open", async () => {
    await claimDevice(AYSEL, inSeconds(1));
    await setOfflineEnabled(AYSEL, true, inSeconds(1));
    mount(AYSEL, inSeconds(1));
    await waitFor(async () => expect(await readDevice()).not.toBeNull());
    await waitFor(async () => expect(await readDevice()).toBeNull(), { timeout: 3000 });
  });

  it("sends a sign-out that was asked for offline as soon as the connection is back", async () => {
    localStorage.setItem(SIGN_OUT_PENDING_KEY, "1");
    setOnline(false);
    mount();
    await act(async () => undefined);
    expect(submitSignOut).not.toHaveBeenCalled();

    act(() => setOnline(true));

    await waitFor(() => expect(submitSignOut).toHaveBeenCalledWith("csrf-token"));
    expect(localStorage.getItem(SIGN_OUT_PENDING_KEY)).toBeNull();
    // A pending sign-out never registers the device again.
    expect(await readDevice()).toBeNull();
  });

  it("keeps the stored history of an open channel up to date from the live window", async () => {
    await claimDevice(AYSEL, inSeconds(3600));
    await setOfflineEnabled(AYSEL, true, inSeconds(3600));
    const earlier: ChannelHistory = {
      channel: { id: "c1", name: "İqtisadiyyat", context: "765a2" },
      messages: [
        {
          id: "1001",
          authorName: "Ramin Əliyev",
          anonymous: false,
          body: "Köhnə mesaj",
          state: "visible",
          createdAt: "2026-11-02T08:00:00Z",
          edited: false,
          mentions: [],
          attachmentNames: [],
        },
      ],
    };
    await putSnapshot(AYSEL, "channel", "c1", earlier);
    mount();
    await waitFor(async () => expect(await readDevice()).not.toBeNull());

    act(() =>
      chatStore.setState({
        windows: {
          c1: {
            messages: { "1002": message("1002", "Yeni mesaj") },
            hasOlder: true,
            hasNewer: false,
            truncated: false,
          },
        },
      }),
    );

    await waitFor(
      async () => {
        const stored = await getSnapshot<ChannelHistory>(AYSEL, "channel", "c1");
        expect(stored!.data.messages.map((entry) => entry.body)).toEqual([
          "Köhnə mesaj",
          "Yeni mesaj",
        ]);
      },
      { timeout: 4000 },
    );
  });

  it("does not store a window that is not the newest part of the history", async () => {
    await claimDevice(AYSEL, inSeconds(3600));
    await setOfflineEnabled(AYSEL, true, inSeconds(3600));
    mount();
    await waitFor(async () => expect(await readDevice()).not.toBeNull());

    act(() =>
      chatStore.setState({
        windows: {
          c1: {
            messages: { "1": message("1", "Çox köhnə") },
            hasOlder: false,
            hasNewer: true,
            truncated: false,
          },
        },
      }),
    );
    await new Promise((resolve) => setTimeout(resolve, 2600));
    expect(await getSnapshot(AYSEL, "channel", "c1")).toBeNull();
  });
});

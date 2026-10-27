import { describe, expect, it } from "vitest";

import type { ChatMessage } from "./model";
import { createChatStore } from "./store";

function message(id: string, clientMsgId = `client-${id}`, channelId = "c-1"): ChatMessage {
  return {
    id,
    channel_id: channelId,
    topic_id: null,
    parent_id: null,
    author: { id: "u-aysel", display_name: "Aysel Məmmədova", photo_url: null, badge: null },
    body: `Mesaj ${id}`,
    client_msg_id: clientMsgId,
    created_at: "2026-10-26T10:00:00Z",
    edited_at: null,
    deleted_at: null,
    is_verified_answer: false,
    verified_by_name: null,
    is_anonymous: false,
    pinned: false,
    saved: null,
    poll: null,
    reply_count: 0,
    last_reply_at: null,
    reactions: [],
    my_reactions: [],
    mentions: [],
    mentions_channel: false,
    attachments: [],
  };
}

describe("chat store", () => {
  it("replaces an optimistic message with the server's copy by client id (§5.9)", () => {
    const store = createChatStore();
    store.getState().loadPage("c-1", { messages: [message("10")], has_more: false }, "latest");
    store.getState().queue({
      clientMsgId: "local-1",
      channelId: "c-1",
      body: "Sabah görüşərik",
      state: "sending",
      createdAt: 1,
    });
    expect(Object.keys(store.getState().pending)).toEqual(["local-1"]);
    store.getState().receive(message("20", "local-1"));
    expect(store.getState().pending).toEqual({});
    expect(Object.keys(store.getState().windows["c-1"]!.messages).sort()).toEqual(["10", "20"]);
    // The same message delivered twice (live and in a backfill) stays one message.
    store.getState().receive(message("20", "local-1"));
    expect(Object.keys(store.getState().windows["c-1"]!.messages)).toHaveLength(2);
  });

  it("keeps the backfill cursor at the newest id seen, whatever the arrival order", () => {
    const store = createChatStore();
    store.getState().receive(message("108000816563679233"));
    store.getState().receive(message("108000816563679232"));
    expect(store.getState().lastSeenId).toBe("108000816563679233");
    store
      .getState()
      .loadPage("c-2", { messages: [message("5", "x", "c-2")], has_more: true }, "older");
    expect(store.getState().lastSeenId).toBe("108000816563679233");
  });

  it("does not append live messages to a window that is not at the latest page", () => {
    const store = createChatStore();
    store.getState().loadPage("c-1", { messages: [message("10")], has_more: true }, "unread");
    expect(store.getState().windows["c-1"]).toMatchObject({ hasOlder: true, hasNewer: true });
    store.getState().receive(message("99"));
    expect(Object.keys(store.getState().windows["c-1"]!.messages)).toEqual(["10"]);
    store.getState().loadPage("c-1", { messages: [message("50")], has_more: false }, "newer");
    expect(store.getState().windows["c-1"]).toMatchObject({ hasNewer: false });
    store.getState().receive(message("99"));
    expect(Object.keys(store.getState().windows["c-1"]!.messages).sort()).toEqual([
      "10",
      "50",
      "99",
    ]);
  });

  it("drops a window whose reconnect gap was too large and remembers why", () => {
    const store = createChatStore();
    store.getState().loadPage("c-1", { messages: [message("10")], has_more: false }, "latest");
    store.getState().truncate("c-1");
    expect(store.getState().windows["c-1"]).toEqual({
      messages: {},
      hasOlder: false,
      hasNewer: false,
      truncated: true,
    });
    store.getState().loadPage("c-1", { messages: [message("2000")], has_more: true }, "latest");
    expect(store.getState().windows["c-1"]!.truncated).toBe(true);
    store.getState().loadPage("c-1", { messages: [message("1500")], has_more: true }, "unread");
    expect(store.getState().windows["c-1"]!.truncated).toBe(false);
  });

  it("forgets a channel the user lost access to, with its unsent messages", () => {
    const store = createChatStore();
    store.getState().loadPage("c-1", { messages: [message("10")], has_more: false }, "latest");
    store.getState().queue({
      clientMsgId: "local-1",
      channelId: "c-1",
      body: "Salam",
      state: "queued",
      createdAt: 1,
    });
    store.getState().revoke("c-1");
    expect(store.getState().windows).toEqual({});
    expect(store.getState().pending).toEqual({});
    expect(store.getState().revoked).toBe("c-1");
    store.getState().clearRevoked();
    expect(store.getState().revoked).toBeNull();
  });

  it("marks failures and expires typing indicators", () => {
    const store = createChatStore();
    store.getState().queue({
      clientMsgId: "local-1",
      channelId: "c-1",
      body: "Salam",
      state: "sending",
      createdAt: 1,
    });
    store.getState().setPending("local-1", "failed", "chat.rate_limited");
    expect(store.getState().pending["local-1"]).toMatchObject({
      state: "failed",
      error: "chat.rate_limited",
    });
    store.getState().dropPending("local-1");
    expect(store.getState().pending).toEqual({});

    store.getState().setTyping("c-1", "u-ramin", "Ramin Əliyev", 5000);
    store.getState().expireTyping(4000);
    expect(store.getState().typing["c-1"]).toBeDefined();
    store.getState().expireTyping(5000);
    expect(store.getState().typing).toEqual({});
  });
});

describe("threads, edits and reactions", () => {
  const thumbs = "\u{1F44D}";
  const heart = "\u{2764}\u{FE0F}";

  it("routes replies to their thread and counts them on the root once", () => {
    const store = createChatStore();
    store.getState().loadPage("c-1", { messages: [message("10")], has_more: false }, "latest");
    const reply = { ...message("11", "local-r"), parent_id: "10" };
    store.getState().receive(reply);
    store.getState().receive(reply);
    const root = store.getState().windows["c-1"]!.messages["10"]!;
    expect(root.reply_count).toBe(1);
    expect(Object.keys(store.getState().windows["c-1"]!.messages)).toEqual(["10"]);

    store.getState().loadThread("10", { root, replies: [reply], has_more: false }, "replace");
    store.getState().receive({ ...message("12"), parent_id: "10" });
    expect(Object.keys(store.getState().threads["10"]!.replies).sort()).toEqual(["11", "12"]);
    expect(store.getState().threads["10"]!.root.reply_count).toBe(2);
  });

  it("keeps the reader's own reactions when a broadcast edit carries none", () => {
    const store = createChatStore();
    const mine = {
      ...message("10"),
      reactions: [{ emoji: thumbs, count: 1 }],
      my_reactions: [thumbs],
    };
    store.getState().loadPage("c-1", { messages: [mine], has_more: false }, "latest");
    store.getState().update({ ...mine, body: "Düzəliş", my_reactions: null, edited_at: "x" });
    const updated = store.getState().windows["c-1"]!.messages["10"]!;
    expect(updated.body).toBe("Düzəliş");
    expect(updated.my_reactions).toEqual([thumbs]);
  });

  it("shows deletions everywhere and lowers the root's reply count", () => {
    const store = createChatStore();
    const root = { ...message("10"), reply_count: 1, reactions: [{ emoji: thumbs, count: 2 }] };
    const reply = { ...message("11"), parent_id: "10" };
    store.getState().loadPage("c-1", { messages: [root], has_more: false }, "latest");
    store.getState().loadThread("10", { root, replies: [reply], has_more: false }, "replace");
    store.getState().markDeleted({ id: "11", channel_id: "c-1", parent_id: "10", deleted_at: "t" });
    expect(store.getState().windows["c-1"]!.messages["10"]!.reply_count).toBe(0);
    expect(store.getState().threads["10"]!.replies["11"]!.deleted_at).toBe("t");
    store.getState().markDeleted({ id: "10", channel_id: "c-1", parent_id: null, deleted_at: "t" });
    const deleted = store.getState().threads["10"]!.root;
    expect(deleted.body).toBe("");
    expect(deleted.reactions).toEqual([]);
  });

  it("applies reaction counts in the fixed order and tracks only the reader's own", () => {
    const store = createChatStore();
    store.getState().loadPage("c-1", { messages: [message("10")], has_more: false }, "latest");
    const event = { message_id: "10", channel_id: "c-1", user_id: "u-ramin", added: true };
    store.getState().applyReaction({ ...event, emoji: heart, count: 1 }, "u-aysel");
    store
      .getState()
      .applyReaction({ ...event, emoji: thumbs, count: 1, user_id: "u-aysel" }, "u-aysel");
    let current = store.getState().windows["c-1"]!.messages["10"]!;
    expect(current.reactions).toEqual([
      { emoji: thumbs, count: 1 },
      { emoji: heart, count: 1 },
    ]);
    expect(current.my_reactions).toEqual([thumbs]);
    store
      .getState()
      .applyReaction(
        { ...event, emoji: thumbs, count: 0, user_id: "u-aysel", added: false },
        "u-aysel",
      );
    current = store.getState().windows["c-1"]!.messages["10"]!;
    expect(current.reactions).toEqual([{ emoji: heart, count: 1 }]);
    expect(current.my_reactions).toEqual([]);
  });
});

describe("messages that arrive before the first page", () => {
  it("keeps a live message the page read just before it was stored", () => {
    const store = createChatStore();
    // Sent right after opening the channel: the event arrives before the history response.
    store.getState().receive(message("30", "local-1"));
    store
      .getState()
      .loadPage("c-1", { messages: [message("10"), message("20")], has_more: false }, "latest");
    expect(Object.keys(store.getState().windows["c-1"]!.messages).sort()).toEqual([
      "10",
      "20",
      "30",
    ]);
    expect(store.getState().early).toEqual({});
    // Already in the page: nothing is duplicated, and older live copies never replace history.
    store.getState().receive(message("40"));
    store.getState().loadPage("c-1", { messages: [message("40")], has_more: true }, "latest");
    expect(Object.keys(store.getState().windows["c-1"]!.messages)).toEqual(["40"]);
  });

  it("keeps only the last few early messages per channel", () => {
    const store = createChatStore();
    for (let n = 1; n <= 30; n += 1)
      store.getState().receive(message(String(100 + n), `c${n}`, "c-9"));
    expect(Object.keys(store.getState().early["c-9"]!)).toHaveLength(20);
  });
});

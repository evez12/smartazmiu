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

import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@/features/chat/model";
import type { Schedule } from "@/features/schedule/model";

import { lastMessages, mergeHistory, splitWeeks, toOfflineMessage } from "./model";

function message(id: string, overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id,
    channel_id: "c1",
    client_msg_id: `client-${id}`,
    author: {
      id: "u-aysel",
      display_name: "Aysel Məmmədova",
      photo_url: "https://example.test/photo.jpg",
    },
    body: "Mühazirə 1-301-də olacaq.",
    created_at: "2026-11-02T08:30:00Z",
    edited_at: null,
    deleted_at: null,
    parent_id: null,
    topic_id: null,
    is_anonymous: false,
    is_verified_answer: false,
    verified_by_name: null,
    pinned: false,
    reply_count: 0,
    last_reply_at: null,
    mentions: [],
    mentions_channel: false,
    attachments: [],
    reactions: [],
    my_reactions: ["\u{1F44D}"],
    saved: true,
    poll: null,
    moderation: "visible",
    ...overrides,
  } as ChatMessage;
}

describe("what is kept of a message", () => {
  it("is the text, author name and time, without photo, reactions or read state", () => {
    const kept = toOfflineMessage(message("100"), new Set());
    expect(kept).toEqual({
      id: "100",
      authorName: "Aysel Məmmədova",
      anonymous: false,
      body: "Mühazirə 1-301-də olacaq.",
      state: "visible",
      createdAt: "2026-11-02T08:30:00Z",
      edited: false,
      mentions: [],
      attachmentNames: [],
    });
    expect(JSON.stringify(kept)).not.toContain("example.test");
  });

  it("keeps only the names of attachments, never the files", () => {
    const kept = toOfflineMessage(
      message("100", {
        attachments: [
          {
            id: "a1",
            filename: "cədvəl.pdf",
            mime: "application/pdf",
            size_bytes: 1024,
            previewable: true,
            status: "clean",
            width: null,
            height: null,
          },
        ],
      } as Partial<ChatMessage>),
      new Set(),
    );
    expect(kept.attachmentNames).toEqual(["cədvəl.pdf"]);
    expect(Object.keys(kept)).not.toContain("attachments");
  });

  it("drops the body of a message from a blocked author (D-062)", () => {
    const kept = toOfflineMessage(message("100"), new Set(["u-aysel"]));
    expect(kept).toMatchObject({ state: "blocked", body: "", attachmentNames: [] });
  });

  it("drops the body of a deleted or moderated message", () => {
    expect(
      toOfflineMessage(message("1", { deleted_at: "2026-11-02T09:00:00Z" }), new Set()),
    ).toMatchObject({ state: "deleted", body: "" });
    expect(toOfflineMessage(message("2", { moderation: "held" }), new Set())).toMatchObject({
      state: "moderated",
      body: "",
    });
  });

  it("shows no author for an anonymous post", () => {
    const kept = toOfflineMessage(message("100", { is_anonymous: true }), new Set());
    expect(kept).toMatchObject({ authorName: null, anonymous: true });
  });
});

describe("the newest messages of a channel", () => {
  it("are the last 50 top-level messages, oldest first", () => {
    const all = Array.from({ length: 70 }, (_, index) => message(String(1000 + index)));
    const reply = message("5000", { parent_id: "1001" });
    const kept = lastMessages([reply, ...all.reverse()]);
    expect(kept).toHaveLength(50);
    expect(kept[0]!.id).toBe("1020");
    expect(kept.at(-1)!.id).toBe("1069");
    expect(kept.some((entry) => entry.id === "5000")).toBe(false);
  });

  it("compare ids as numbers, so a longer id is newer", () => {
    const kept = lastMessages([message("99"), message("100")]);
    expect(kept.map((entry) => entry.id)).toEqual(["99", "100"]);
  });
});

describe("merging a short live window into the stored history", () => {
  const stored = (id: string) => toOfflineMessage(message(id), new Set());

  it("never shrinks a fuller stored copy", () => {
    const merged = mergeHistory([stored("1"), stored("2"), stored("3")], [stored("3")]);
    expect(merged.map((entry) => entry.id)).toEqual(["1", "2", "3"]);
  });

  it("takes the live copy of a message that is in both, and adds new ones", () => {
    const edited = { ...stored("2"), edited: true };
    const merged = mergeHistory([stored("1"), stored("2")], [edited, stored("3")]);
    expect(merged.map((entry) => entry.id)).toEqual(["1", "2", "3"]);
    expect(merged[1]!.edited).toBe(true);
  });

  it("is cut to the newest 50", () => {
    const old = Array.from({ length: 50 }, (_, index) => stored(String(100 + index)));
    expect(mergeHistory(old, [stored("200")]).map((entry) => entry.id)[49]).toBe("200");
    expect(mergeHistory(old, [stored("200")])).toHaveLength(50);
  });
});

describe("the stored fortnight", () => {
  const days = Array.from({ length: 14 }, (_, index) => ({
    date: `2026-11-${String(2 + index).padStart(2, "0")}`,
    parity: "upper" as const,
    classes: [],
  }));
  const fortnight: Schedule = { start: "2026-11-02", end: "2026-11-15", today: "2026-11-03", days };

  it("is split into this week and next week", () => {
    const [first, second] = splitWeeks(fortnight);
    expect(first).toMatchObject({ start: "2026-11-02", end: "2026-11-08" });
    expect(first!.days).toHaveLength(7);
    expect(second).toMatchObject({ start: "2026-11-09", end: "2026-11-15" });
    expect(second!.days[0]!.date).toBe("2026-11-09");
  });

  it("has only the weeks that were stored", () => {
    expect(splitWeeks({ ...fortnight, days: days.slice(0, 7) })).toHaveLength(1);
  });
});

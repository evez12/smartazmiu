import { describe, expect, it } from "vitest";

import {
  badgeCounts,
  buildTimeline,
  canChange,
  compareIds,
  decodeMentions,
  encodeMentions,
  newestId,
  sidebarGroups,
  splitMentions,
  type Channel,
  type ChatMessage,
  type PendingMessage,
} from "./model";

const AYSEL = { id: "u-aysel", display_name: "Aysel Məmmədova", photo_url: null, badge: null };
const RAMIN = { id: "u-ramin", display_name: "Ramin Əliyev", photo_url: null, badge: null };

function message(id: string, at: string, author = AYSEL, body = "Salam"): ChatMessage {
  return {
    id,
    channel_id: "c-1",
    topic_id: null,
    parent_id: null,
    author,
    body,
    client_msg_id: `client-${id}`,
    created_at: at,
    edited_at: null,
    deleted_at: null,
    is_verified_answer: false,
    reply_count: 0,
    last_reply_at: null,
    reactions: [],
    my_reactions: [],
    mentions: [],
    mentions_channel: false,
  };
}

function channel(overrides: Partial<Channel>): Channel {
  return {
    id: overrides.name ?? "c",
    type: "course_offering",
    name: "Statistika",
    context: null,
    peer: null,
    is_archived: false,
    is_readonly: false,
    notify_level: "all",
    muted_until: null,
    unread_count: 0,
    mention_count: 0,
    last_read_message_id: null,
    posting: { allowed: true, reason: null, until: null, retry_after_seconds: null },
    ...overrides,
  };
}

describe("sidebarGroups", () => {
  it("orders sections as Fənlər, Fənn icmaları, Qrup, Şəxsi and sorts names the Azerbaijani way", () => {
    const groups = sidebarGroups([
      channel({ name: "Ramin Əliyev", type: "dm" }),
      channel({ name: "765a2", type: "academic_group" }),
      channel({ name: "Şəhərsalma", type: "subject_community" }),
      channel({ name: "Çertyoj", type: "course_offering" }),
      channel({ name: "Coğrafiya", type: "course_offering" }),
      channel({ name: "İKT", type: "course_offering", is_archived: true }),
      channel({ name: "Tikinti iqtisadiyyatı fakültəsi", type: "faculty" }),
    ]);
    expect(groups.map((group) => group.key)).toEqual([
      "courses",
      "communities",
      "groups",
      "direct",
    ]);
    // C before Ç (ASCII order would put Ç last).
    expect(groups[0]!.open.map((c) => c.name)).toEqual(["Coğrafiya", "Çertyoj"]);
    expect(groups[0]!.archived.map((c) => c.name)).toEqual(["İKT"]);
    expect(groups[2]!.open.map((c) => c.name)).toEqual([
      "765a2",
      "Tikinti iqtisadiyyatı fakültəsi",
    ]);
  });

  it("leaves out empty sections", () => {
    expect(sidebarGroups([channel({ type: "dm", name: "Ramin" })]).map((g) => g.key)).toEqual([
      "direct",
    ]);
  });
});

describe("snowflake ids", () => {
  it("compares beyond JavaScript's safe integers", () => {
    // Both round to the same double; only BigInt tells them apart.
    expect(compareIds("108000816563679233", "108000816563679232")).toBe(1);
    expect(Number("108000816563679233")).toBe(Number("108000816563679232"));
    expect(newestId(["5", "108000816563679233", "108000816563679232"])).toBe("108000816563679233");
    expect(newestId([])).toBeNull();
  });
});

describe("buildTimeline", () => {
  const options = { lastReadId: null, currentUserId: AYSEL.id };

  it("orders by id, not by arrival, and collapses one author's messages within five minutes", () => {
    const items = buildTimeline(
      [
        message("30", "2026-10-26T10:04:00Z"),
        message("10", "2026-10-26T10:00:00Z"),
        message("20", "2026-10-26T10:01:00Z"),
        message("40", "2026-10-26T10:10:00Z"),
        message("50", "2026-10-26T10:10:30Z", RAMIN),
      ],
      [],
      options,
    );
    const rows = items.flatMap((item) =>
      item.kind === "message" ? [[item.message.id, item.showHeader]] : [],
    );
    expect(rows).toEqual([
      ["10", true],
      ["20", false],
      ["30", false],
      ["40", true], // six minutes after the previous one
      ["50", true], // another author
    ]);
  });

  it("separates days in Baku time", () => {
    // 19:59 UTC is still 23:59 on the 26th in Baku; 20:01 UTC is the 27th.
    const items = buildTimeline(
      [message("1", "2026-10-26T19:59:00Z"), message("2", "2026-10-26T20:01:00Z")],
      [],
      options,
    );
    expect(items.map((item) => item.kind)).toEqual(["day", "message", "day", "message"]);
    expect(items.filter((item) => item.kind === "day").map((item) => item.key)).toEqual([
      "day-2026-10-26",
      "day-2026-10-27",
    ]);
    expect(items[3]).toMatchObject({ showHeader: true });
  });

  it("puts the new-messages divider before the first unread message of someone else", () => {
    const items = buildTimeline(
      [
        message("1", "2026-10-26T10:00:00Z", RAMIN),
        message("2", "2026-10-26T10:01:00Z", AYSEL),
        message("3", "2026-10-26T10:02:00Z", RAMIN),
        message("4", "2026-10-26T10:02:30Z", RAMIN),
      ],
      [],
      { lastReadId: "1", currentUserId: AYSEL.id },
    );
    expect(items.map((item) => (item.kind === "message" ? item.message.id : item.kind))).toEqual([
      "day",
      "1",
      "2",
      "unread",
      "3",
      "4",
    ]);
    // The divider starts a new header even for the same author.
    expect(items[4]).toMatchObject({ showHeader: true });
    expect(items[5]).toMatchObject({ showHeader: false });
  });

  it("shows unconfirmed messages after confirmed ones, in the order they were written", () => {
    const pending = (clientMsgId: string, createdAt: number): PendingMessage => ({
      clientMsgId,
      channelId: "c-1",
      body: "Göndərilir",
      state: "sending",
      createdAt,
    });
    const now = Date.parse("2026-10-26T10:05:00Z");
    const items = buildTimeline(
      [message("1", "2026-10-26T10:04:00Z", RAMIN)],
      [pending("b", now + 2000), pending("a", now + 1000)],
      options,
    );
    expect(items.map((item) => item.key)).toEqual(["day-2026-10-26", "1", "a", "b"]);
    expect(items[2]).toMatchObject({ showHeader: true });
    expect(items[3]).toMatchObject({ showHeader: false });
  });

  it("never collapses messages of deleted accounts", () => {
    const items = buildTimeline(
      [
        { ...message("1", "2026-10-26T10:00:00Z"), author: null },
        { ...message("2", "2026-10-26T10:00:10Z"), author: null },
      ],
      [],
      options,
    );
    expect(items.filter((item) => item.kind === "message").map((item) => item.showHeader)).toEqual([
      true,
      true,
    ]);
  });
});

describe("mentions", () => {
  const ramin = "0a6f3c1e-5b7d-4e2a-9c11-2f3e4d5a6b7c";
  const stranger = "1b2c3d4e-5f60-4718-9a0b-c1d2e3f40516";

  it("names members only and keeps other tokens nameless (§13.2)", () => {
    const parts = splitMentions(`Salam <@${ramin}> və <@${stranger}>!`, [
      { id: ramin, display_name: "Ramin Əliyev" },
    ]);
    expect(parts).toEqual([
      { kind: "text", text: "Salam " },
      { kind: "mention", id: ramin, name: "Ramin Əliyev" },
      { kind: "text", text: " və " },
      { kind: "mention", id: stranger, name: null },
      { kind: "text", text: "!" },
    ]);
  });

  it("encodes picked names as tokens and decodes them for editing", () => {
    const picked = new Map([
      ["Aysel", "a-1"],
      ["Aysel Məmmədova", "a-2"],
    ]);
    // The longer name wins; a name followed by more letters is not a mention.
    expect(encodeMentions("@Aysel Məmmədova və @Aysel, @Ayselə yox", picked)).toBe(
      "<@a-2> və <@a-1>, @Ayselə yox",
    );
    const { text, picked: back } = decodeMentions(`<@${ramin}> bax, <@${stranger}>`, [
      { id: ramin, display_name: "Ramin Əliyev" },
    ]);
    expect(text).toBe(`@Ramin Əliyev bax, <@${stranger}>`);
    expect(back.get("Ramin Əliyev")).toBe(ramin);
  });
});

describe("badges and the change window", () => {
  const now = Date.parse("2026-10-26T10:00:00Z");

  it("follows the notification level and the snooze", () => {
    const base = channel({ unread_count: 7, mention_count: 2 });
    expect(badgeCounts(base, now)).toEqual({ unread: 7, mentions: 2 });
    expect(badgeCounts({ ...base, notify_level: "mentions" }, now)).toEqual({
      unread: 0,
      mentions: 2,
    });
    expect(badgeCounts({ ...base, notify_level: "none" }, now)).toEqual({ unread: 0, mentions: 0 });
    expect(badgeCounts({ ...base, muted_until: "2026-10-26T11:00:00Z" }, now)).toEqual({
      unread: 0,
      mentions: 0,
    });
    // A snooze that has ended no longer hides anything.
    expect(badgeCounts({ ...base, muted_until: "2026-10-26T09:00:00Z" }, now).unread).toBe(7);
  });

  it("offers edits to the author for 15 minutes only", () => {
    const fresh = message("1", "2026-10-26T09:50:00Z");
    expect(canChange(fresh, AYSEL.id, now)).toBe(true);
    expect(canChange(fresh, RAMIN.id, now)).toBe(false);
    expect(canChange(message("2", "2026-10-26T09:44:00Z"), AYSEL.id, now)).toBe(false);
    expect(canChange({ ...fresh, deleted_at: "x" }, AYSEL.id, now)).toBe(false);
  });
});

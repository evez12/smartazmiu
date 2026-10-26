"use client";

import { useTranslations } from "next-intl";

import { ChannelLink } from "./channel-sidebar";
import { Composer } from "./composer";
import { TimelineRow } from "./message-row";
import { REACTIONS, type Channel, type ChatMessage, type TimelineItem } from "./model";
import { PostingBanner } from "./posting";

const posting = { allowed: true, reason: null, until: null, retry_after_seconds: null } as const;

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
    posting,
    ...overrides,
  };
}

const CHANNELS = [
  channel({ name: "Statistika", context: "765a2 · 2026 Payız", unread_count: 3 }),
  channel({ name: "Mikroiqtisadiyyat", context: "765a2 · 2026 Payız" }),
  channel({ name: "Statistika icması", type: "subject_community", unread_count: 120 }),
  channel({
    name: "Ramin Əliyev",
    type: "dm",
    peer: { id: "ramin", display_name: "Ramin Əliyev", photo_url: null, badge: null },
  }),
];

function message(id: string, at: string, author: ChatMessage["author"], body: string): ChatMessage {
  return {
    id,
    channel_id: "statistika",
    topic_id: null,
    parent_id: null,
    author,
    body,
    client_msg_id: id,
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
    attachments: [],
  };
}

const LEYLA = {
  id: "leyla",
  display_name: "Leyla Həsənova",
  photo_url: null,
  badge: "teacher" as const,
};
const RAMIN = { id: "ramin", display_name: "Ramin Əliyev", photo_url: null, badge: null };
const ORXAN = { id: "orxan", display_name: "Orxan Rzayev", photo_url: null, badge: null };

const TIMELINE: TimelineItem[] = [
  { kind: "day", key: "day", day: "2026-11-02" },
  {
    kind: "message",
    key: "1",
    showHeader: true,
    message: message(
      "1",
      "2026-11-02T06:30:00Z",
      LEYLA,
      "Sabahkı seminar 1-305 otağında keçiriləcək.",
    ),
  },
  {
    kind: "message",
    key: "2",
    showHeader: false,
    message: {
      ...message(
        "2",
        "2026-11-02T06:31:00Z",
        LEYLA,
        "<@5d0c6f1e-3a7b-4c2d-9e8f-0a1b2c3d4e5f> ehtimal paylanmaları mövzusunu təkrar edin.",
      ),
      edited_at: "2026-11-02T06:33:00Z",
      mentions: [{ id: "5d0c6f1e-3a7b-4c2d-9e8f-0a1b2c3d4e5f", display_name: "Aysel Məmmədova" }],
      reactions: [
        { emoji: REACTIONS[0], count: 4 },
        { emoji: REACTIONS[5], count: 1 },
      ],
      my_reactions: [REACTIONS[0]],
      reply_count: 3,
      last_reply_at: "2026-11-02T06:40:00Z",
    },
  },
  {
    kind: "message",
    key: "2b",
    showHeader: false,
    message: {
      ...message("2b", "2026-11-02T06:32:00Z", LEYLA, ""),
      deleted_at: "2026-11-02T06:34:00Z",
    },
  },
  { kind: "unread", key: "unread" },
  {
    kind: "message",
    key: "3",
    showHeader: true,
    message: {
      ...message("3", "2026-11-02T07:05:00Z", RAMIN, "Tapşırıq neçənci səhifədən başlayır?"),
      attachments: [
        {
          id: "a1",
          filename: "Ehtimal nəzəriyyəsi — mühazirə 4.pdf",
          mime: "application/pdf",
          size_bytes: 1_572_864,
          width: null,
          height: null,
          status: "clean",
          previewable: true,
        },
        {
          id: "a2",
          filename: "Tapşırıqlar.docx",
          mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          size_bytes: 48_128,
          width: null,
          height: null,
          status: "pending",
          previewable: false,
        },
      ],
    },
  },
  {
    kind: "message",
    key: "4",
    showHeader: true,
    message: message("4", "2026-11-02T07:06:00Z", ORXAN, "Bu mesaj bloklanmış istifadəçidəndir."),
  },
  {
    kind: "pending",
    key: "p1",
    showHeader: true,
    pending: {
      clientMsgId: "p1",
      channelId: "statistika",
      body: "42-ci səhifədən.",
      state: "sending",
      createdAt: 0,
    },
  },
  {
    kind: "pending",
    key: "p2",
    showHeader: false,
    pending: {
      clientMsgId: "p2",
      channelId: "statistika",
      body: "Və 3-cü məsələdən.",
      state: "failed",
      createdAt: 1,
      error: "chat.rate_limited",
      errorDetail: { retry_after_seconds: 7 },
    },
  },
];

/** Static chat parts for the design-system page and its visual baselines (§12.7, §12.9). */
export function ChatSpecimen() {
  const t = useTranslations("chat");
  const me = { id: "aysel", name: "Aysel Məmmədova" };
  return (
    <div className="flex flex-col overflow-hidden rounded-panel border border-border bg-surface md:flex-row">
      <ul className="flex flex-col gap-0.5 border-border p-2 md:w-64 md:border-r">
        <li className="px-2 pb-1 text-xs font-medium text-muted">{t("groups.courses")}</li>
        {CHANNELS.map((item, index) => (
          <li key={item.id}>
            <ChannelLink
              channel={item}
              active={index === 0}
              presence={index === 3 ? "online" : undefined}
            />
          </li>
        ))}
      </ul>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="py-2">
          {TIMELINE.map((item) => (
            <TimelineRow
              key={item.key}
              item={item}
              context={{
                currentUser: me,
                canPost: true,
                members: [],
                onOpenThread: () => undefined,
              }}
              blockedIds={new Set(["orxan"])}
              onRetry={() => undefined}
            />
          ))}
        </div>
        <PostingBanner
          posting={{
            allowed: false,
            reason: "chat.exam_mode",
            until: "2027-01-15T08:00:00Z",
            retry_after_seconds: null,
          }}
        />
        <Composer
          label={t("composerLabel")}
          placeholder={t("composerPlaceholder", { channel: "Statistika" })}
          disabled={false}
          onSend={() => undefined}
          onTyping={() => undefined}
        />
      </div>
    </div>
  );
}

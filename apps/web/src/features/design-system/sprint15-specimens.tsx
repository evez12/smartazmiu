"use client";

import { useTranslations } from "next-intl";

import { InstallOffer } from "@/features/offline/install-prompt";
import type { ChannelHistory, ChannelList } from "@/features/offline/model";
import { OfflineBanner } from "@/features/offline/notices";
import { StoredContent } from "@/features/offline/offline-app";
import { UpdateNotice } from "@/features/offline/update-banner";
import type { Schedule, ScheduleDay } from "@/features/schedule/model";

import { Section } from "./section";

/*
 * Fixed data for the offline screens (Sprint 15, Group B), so `make visual` can compare them without a browser
 * database or a service worker. The dates are fixed as well: "today" must not move the baselines.
 */

const STORED_AT = Date.parse("2026-11-02T07:30:00Z");
const TODAY = "2026-11-03";

function day(date: string, classes: ScheduleDay["classes"] = []): ScheduleDay {
  return { date, parity: "upper", classes };
}

const LECTURE: ScheduleDay["classes"][number] = {
  id: "e1:2026-11-02",
  date: "2026-11-02",
  starts_at: "08:30",
  ends_at: "09:50",
  subject: { code: "IQT-2101", name: "Mikroiqtisadiyyat" },
  class_type: "lecture",
  room: {
    code: "1-301",
    name: "Mühazirə zalı",
    building: "Tədris korpusu 1",
    floor: "3-cü mərtəbə",
  },
  teachers: ["Şəhla Ağayeva"],
  groups: ["765a2"],
  status: "scheduled",
  original_date: "2026-11-02",
  original_starts_at: "08:30",
  moved_to: null,
  room_changed: false,
  teacher_changed: false,
  note: "",
};

const FORTNIGHT: Schedule = {
  start: "2026-11-02",
  end: "2026-11-15",
  today: TODAY,
  days: [
    day("2026-11-02", [LECTURE]),
    day("2026-11-03", [
      {
        ...LECTURE,
        id: "e2:2026-11-03",
        date: "2026-11-03",
        starts_at: "10:00",
        ends_at: "11:20",
        class_type: "seminar",
      },
    ]),
    ...["2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"].map((date) =>
      day(date),
    ),
    ...[
      "2026-11-09",
      "2026-11-10",
      "2026-11-11",
      "2026-11-12",
      "2026-11-13",
      "2026-11-14",
      "2026-11-15",
    ].map((date) => day(date)),
  ],
};

const CHANNELS: ChannelList = {
  channels: [
    { id: "c1", name: "Mikroiqtisadiyyat · 765a2", context: "Payız semestri 2026" },
    { id: "c2", name: "İqtisadiyyat fakültəsi", context: null },
  ],
};

const HISTORY: ChannelHistory = {
  channel: CHANNELS.channels[0]!,
  messages: [],
};

const STORED = {
  schedule: {
    key: "u:specimen:schedule:",
    userId: "specimen",
    kind: "schedule" as const,
    savedAt: STORED_AT,
    data: FORTNIGHT,
  },
  channels: {
    key: "u:specimen:channels:",
    userId: "specimen",
    kind: "channels" as const,
    savedAt: STORED_AT,
    data: CHANNELS,
  },
  histories: [
    {
      key: "u:specimen:channel:c1",
      userId: "specimen",
      kind: "channel" as const,
      savedAt: STORED_AT,
      data: HISTORY,
    },
  ],
};

export function Sprint15Specimens() {
  const t = useTranslations("designSystem.sections");
  return (
    <>
      <Section title={t("offlineNotices")}>
        <OfflineBanner variant="live" lastUpdated={STORED_AT} />
        <OfflineBanner variant="cached" lastUpdated={null} />
        <UpdateNotice unsent={false} onApply={() => undefined} />
        <UpdateNotice unsent onApply={() => undefined} />
        <InstallOffer canPrompt onInstall={() => undefined} onDismiss={() => undefined} />
        <InstallOffer canPrompt={false} onInstall={() => undefined} onDismiss={() => undefined} />
      </Section>
      <Section title={t("offlinePage")}>
        <StoredContent data={STORED} today={TODAY} />
      </Section>
    </>
  );
}

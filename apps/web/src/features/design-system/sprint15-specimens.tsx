"use client";

import { useTranslations } from "next-intl";

import { SourceNotice } from "@/features/cabinet/source-notice";
import { ConflictTable, RunTable } from "@/features/cabinet/sync-admin";
import { AppealTable, SemesterPanel, Summary } from "@/features/cabinet/transcript-page";
import { InstallOffer } from "@/features/offline/install-prompt";
import type { ChannelHistory, ChannelList } from "@/features/offline/model";
import { OfflineBanner } from "@/features/offline/notices";
import { StoredContent } from "@/features/offline/offline-app";
import { UpdateNotice } from "@/features/offline/update-banner";
import type { components } from "@/lib/api/schema";
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

const MIRROR_SYNCED = "2026-11-03T22:40:00Z";
const TRANSCRIPT: components["schemas"]["TranscriptOut"] = {
  source: { state: "unavailable", last_synced_at: MIRROR_SYNCED },
  student: {
    specialty_name: "İqtisadiyyat",
    credits_earned: 24,
    cumulative_average: 78.4,
    synced_at: MIRROR_SYNCED,
  },
  semesters: [
    {
      semester_year: 2025,
      semester_term: "fall",
      credits_attempted: 30,
      credits_earned: 25,
      average: 74.5,
      courses: [
        {
          subject_code: "SOS-1101",
          subject_name: "Azərbaycan tarixi",
          credits: 5,
          score: 87,
          passed: true,
          differs: true,
        },
        {
          subject_code: "XDL-1101",
          subject_name: "Xarici dildə işgüzar və akademik kommunikasiya-1",
          credits: 4,
          score: 76,
          passed: true,
          differs: false,
        },
        {
          subject_code: "KAR-1101",
          subject_name: "Karyera planlaşması-1",
          credits: 5,
          score: 42,
          passed: false,
          differs: false,
        },
      ],
    },
  ],
};
const APPEALS: components["schemas"]["AppealOut"][] = [
  {
    reference: "MQ-2025-5201-1",
    subject_code: "KAR-1101",
    subject_name: "Karyera planlaşması-1",
    semester_year: 2025,
    semester_term: "fall",
    status: "under_review",
    submitted_on: "2026-02-05",
    decided_on: null,
  },
  {
    reference: "MQ-2025-5201-2",
    subject_code: "SOS-1101",
    subject_name: "Azərbaycan tarixi",
    semester_year: 2025,
    semester_term: "fall",
    status: "upheld",
    submitted_on: "2026-02-03",
    decided_on: "2026-02-10",
  },
];
const RUNS: components["schemas"]["SyncRunOut"][] = [
  {
    id: "r2",
    trigger: "nightly",
    outcome: "failed",
    started_at: "2026-11-03T22:40:00Z",
    finished_at: "2026-11-03T22:41:00Z",
    students_synced: 0,
    students_not_found: 0,
    students_mismatched: 0,
    conflicts: 0,
    error_code: "cabinet.unavailable",
  },
  {
    id: "r1",
    trigger: "manual",
    outcome: "succeeded",
    started_at: "2026-11-02T22:40:00Z",
    finished_at: "2026-11-02T22:41:00Z",
    students_synced: 47,
    students_not_found: 1,
    students_mismatched: 0,
    conflicts: 1,
    error_code: null,
  },
];
const CONFLICTS: components["schemas"]["ConflictOut"][] = [
  {
    university_id: "25765201",
    subject_code: "SOS-1101",
    semester_year: 2025,
    semester_term: "fall",
    detected_at: MIRROR_SYNCED,
  },
];

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
      <Section title={t("transcript")}>
        <SourceNotice source={TRANSCRIPT.source} />
        <Summary data={TRANSCRIPT} />
        {TRANSCRIPT.semesters.map((semester) => (
          <SemesterPanel key={semester.semester_year} semester={semester} />
        ))}
        <AppealTable items={APPEALS} />
      </Section>
      <Section title={t("cabinetStaff")}>
        <RunTable items={RUNS} />
        <ConflictTable items={CONFLICTS} />
      </Section>
    </>
  );
}

"use client";

import { useTranslations } from "next-intl";

import { Panel, PanelBody } from "@/components/ui/panel";
import { CodeCard, Roster } from "@/features/attendance/session-screen";
import { ReportTable, type ReportRow } from "@/features/attendance/report-pages";
import { ExamCard } from "@/features/exams/exams-page";
import type { ExamSlot } from "@/features/exams/model";
import { PaperCard } from "@/features/exams/papers-page";
import { Courses, Rules, Simulator, Summary } from "@/features/gpa/gpa-page";
import { GPA_DEFAULTS } from "@/features/gpa/uomg";
import { Overlaps, SlotTable } from "@/features/exams/slots-admin";
import { ApiProvider } from "@/lib/api/provider";

import { Section } from "./section";

/*
 * Fixed data for the Sprint 14 screens, so `make visual` can compare them without an API: the same components, the
 * same copy, no network. The code is a made-up string: the specimen never shows a working attendance code.
 */

const ROSTER = [
  {
    student_id: "3b8f1e52-9a4c-4d70-8e16-2c5a7b9d0e41",
    display_name: "Aysel Məmmədova",
    university_id: "25765201",
    group: "765a2",
    present: true,
    method: "qr" as const,
    checked_in_at: "2026-11-02T06:03:00Z",
    reason: null,
  },
  {
    student_id: "6d2a9c47-1f8e-4b35-a0c9-7e4d3f2b1a68",
    display_name: "Nihad Vəliyev",
    university_id: "25765215",
    group: "765a2",
    present: true,
    method: "manual" as const,
    checked_in_at: "2026-11-02T06:12:00Z",
    reason: "Telefonu işləmirdi",
  },
  {
    student_id: "9e5b3d81-4c7a-4f26-b1d8-0a6c2e8f4b93",
    display_name: "Ülviyyə Zeynalova",
    university_id: "25765221",
    group: "765a2",
    present: false,
    method: null,
    checked_in_at: null,
    reason: null,
  },
];

const REPORT_ROWS: ReportRow[] = ROSTER.map((entry, index) => ({
  student_id: entry.student_id,
  display_name: entry.display_name,
  university_id: entry.university_id,
  group: entry.group,
  attended: [7, 5, 2][index]!,
  total: 8,
  rate: [0.875, 0.625, 0.25][index]!,
  marks: [],
}));

const OFFERING = {
  id: "7a1e2c64-5b90-4d18-8f23-1c4d6e8a0b35",
  subject_name: "Statistika",
  subject_code: "IQT-2102",
  groups: ["765a2"],
  semester: "2026 Payız",
};
const OTHER = {
  ...OFFERING,
  id: "2f6b8d10-9c34-4e57-a1b8-6d0e2f4a8c71",
  subject_name: "Mikroiqtisadiyyat",
  subject_code: "IQT-2101",
};
/** A fixed clock, so the countdown never changes between runs. */
const NOW = Date.parse("2027-01-10T08:00:00Z");
const SLOTS: ExamSlot[] = [
  {
    id: "c3d4e5f6-1a2b-4c3d-8e4f-5a6b7c8d9e01",
    offering: OFFERING,
    starts_at: "2027-01-14T06:00:00Z",
    ends_at: "2027-01-14T07:30:00Z",
    room_code: "2-204",
    overlaps: [
      {
        kind: "group",
        slot_id: "d4e5f6a7-2b3c-4d4e-9f50-6b7c8d9e0f12",
        offering: OTHER,
        starts_at: "2027-01-14T06:30:00Z",
        ends_at: "2027-01-14T08:00:00Z",
      },
    ],
  },
  {
    id: "e5f6a7b8-3c4d-4e5f-a061-7c8d9e0f1a23",
    offering: OTHER,
    starts_at: "2027-01-14T06:30:00Z",
    ends_at: "2027-01-14T08:00:00Z",
    room_code: null,
    overlaps: [],
  },
];

const PAPER = {
  id: "f6a7b8c9-4d5e-4f60-b172-8d9e0f1a2b34",
  subject_id: OFFERING.id,
  semester: "2025 Payız",
  kind: "final" as const,
  title: "Yekun imtahan, 2025 payız",
  filename: "Yekun.pdf",
  size_bytes: 1_572_864,
  status: "pending" as const,
  scan_status: "clean" as const,
  uploaded_by_me: false,
  can_review: true,
  can_download: true,
  review_note: null,
  created_at: "2026-11-01T08:00:00Z",
};

function result(
  id: string,
  subject: string,
  credits: number,
  score: number,
  year: number,
  term: "fall" | "spring",
) {
  return {
    enrollment_id: id,
    subject_id: subject,
    subject_code: subject,
    subject_name: SUBJECT_NAMES[subject] ?? subject,
    credits,
    semester_year: year,
    semester_term: term,
    score,
    passed: score >= 51,
  };
}

const SUBJECT_NAMES: Record<string, string> = {
  "RIY-1101": "Xətti cəbr və riyazi analiz",
  "IQT-2102": "Statistika",
  "XDL-1101": "Xarici dil",
};

/** A failed course retaken the next spring, so the table shows a replaced attempt. */
const GRADES = [
  result("g1", "RIY-1101", 8, 40, 2024, "fall"),
  result("g2", "XDL-1101", 4, 89, 2024, "fall"),
  result("g3", "RIY-1101", 8, 80, 2025, "spring"),
  result("g4", "IQT-2102", 10, 93, 2025, "fall"),
];

function ListPanel({ children }: { children: React.ReactNode }) {
  return (
    <Panel>
      <PanelBody>{children}</PanelBody>
    </Panel>
  );
}

export function Sprint14Specimens() {
  const t = useTranslations("designSystem.sections");
  return (
    <ApiProvider csrfToken="specimen">
      <Section title={t("attendanceScreen")}>
        <ListPanel>
          <div className="flex flex-col items-center gap-4">
            <CodeCard
              qr="SAT1.0000000000000000000000000000specimen.0.not-a-working-code"
              digits="042917"
              secondsLeft={21}
              failed={false}
            />
          </div>
        </ListPanel>
        <Roster sessionId="specimen" roster={ROSTER} />
      </Section>
      <Section title={t("attendanceReport")}>
        <ReportTable rows={REPORT_ROWS} />
      </Section>
      <Section title={t("examCards")}>
        <div className="flex flex-col gap-3">
          {SLOTS.map((slot) => (
            <ExamCard key={slot.id} slot={slot} now={NOW} />
          ))}
        </div>
      </Section>
      <Section title={t("examSlots")}>
        <Overlaps overlaps={SLOTS[0]!.overlaps} />
        <SlotTable items={SLOTS} />
      </Section>
      <Section title={t("pastPapers")}>
        <div className="flex flex-col gap-3">
          <PaperCard paper={PAPER} subjectId={OFFERING.id} />
          <PaperCard
            paper={{
              ...PAPER,
              id: "a7b8c9d0-5e6f-4a71-8283-9e0f1a2b3c45",
              status: "approved",
              can_review: false,
              review_note: "Uyğundur",
            }}
            subjectId={OFFERING.id}
          />
        </div>
      </Section>
      <Section title={t("gpaSummary")}>
        <Summary grades={GRADES} config={GPA_DEFAULTS} />
        <Courses grades={GRADES} config={GPA_DEFAULTS} />
      </Section>
      <Section title={t("gpaRules")}>
        <Rules config={GPA_DEFAULTS} onChange={() => undefined} />
        <Simulator grades={GRADES} config={GPA_DEFAULTS} />
      </Section>
    </ApiProvider>
  );
}

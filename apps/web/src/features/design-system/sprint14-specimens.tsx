import { useTranslations } from "next-intl";

import { Panel, PanelBody } from "@/components/ui/panel";
import { CodeCard, Roster } from "@/features/attendance/session-screen";
import { ReportTable, type ReportRow } from "@/features/attendance/report-pages";
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
    </ApiProvider>
  );
}

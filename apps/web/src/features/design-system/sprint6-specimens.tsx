import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { FeedbackTable, type FeedbackItem } from "@/features/feedback/feedback-table";
import {
  MaterialReportTable,
  type MaterialReportItem,
} from "@/features/materials/material-report-table";
import { MaterialTable } from "@/features/materials/material-table";
import type { Material, MaterialVersion } from "@/features/materials/model";
import { OnboardingTour } from "@/features/onboarding/onboarding-tour";
import { ReportTable, type ReportItem } from "@/features/reports/report-table";
import { Panel, PanelBody } from "@/components/ui/panel";
import { ApiProvider } from "@/lib/api/provider";

import { Section } from "./section";

/*
 * Fixed data for the Sprint 6 screens that need a signed-in session (materials, tour, feedback and report lists), so
 * `make visual` can compare them without an API: the same components, the same copy, no network.
 */

const LEYLA = { id: "5a1f0c8e-7b2d-4e3a-9c41-6d0e8f2b3a17", display_name: "Leyla Həsənova" };
const AYSEL = { id: "2c7e9d14-0b6a-4f58-8e13-9a4d5c6b7e28", display_name: "Aysel Məmmədova" };
const RAMIN = { id: "8e4b1a60-3d9c-4a72-b5f8-1c2d3e4f5a69", display_name: "Ramin Əliyev" };
const FALL = { id: "0f3d5b7a-1c2e-4a68-9b04-7e8f9a0b1c2d", label: "2026 Payız", can_upload: true };

function version(overrides: Partial<MaterialVersion> = {}): MaterialVersion {
  return {
    id: "b1c2d3e4-f5a6-4b78-8c9d-0e1f2a3b4c5d",
    version: 1,
    filename: "Mühazirə 1.pdf",
    mime: "application/pdf",
    size_bytes: 1_572_864,
    note: "",
    status: "clean",
    previewable: true,
    uploaded_by: LEYLA,
    created_at: "2026-10-20T06:00:00Z",
    ...overrides,
  };
}

function material(id: string, overrides: Partial<Material> = {}): Material {
  return {
    id,
    subject_id: "7d6c5b4a-3e2f-4a10-9b8c-7d6e5f4a3b2c",
    semester: FALL,
    type: "lecture",
    title: "Təsviri statistika",
    description: "",
    created_by: LEYLA,
    created_at: "2026-10-20T06:00:00Z",
    current: version(),
    version_count: 1,
    scanning: false,
    hidden: false,
    can_edit: false,
    ...overrides,
  };
}

const MATERIALS: Material[] = [
  material("a0000000-0000-4000-8000-000000000001"),
  material("a0000000-0000-4000-8000-000000000002", {
    title: "Fənn proqramı",
    type: "syllabus",
    current: null,
    scanning: true,
    can_edit: true,
  }),
  material("a0000000-0000-4000-8000-000000000003", {
    title: "İmtahan nümunələri",
    type: "exam_prep",
    current: version({ filename: "Nümunələr.pdf", size_bytes: 482_304, uploaded_by: LEYLA }),
    version_count: 2,
    hidden: true,
  }),
];

const MATERIAL_REPORTS: MaterialReportItem[] = [
  {
    id: "c0000000-0000-4000-8000-000000000001",
    material_id: MATERIALS[2]!.id,
    material_title: "İmtahan nümunələri",
    subject_id: MATERIALS[2]!.subject_id,
    subject_name: "Statistika",
    material_hidden: true,
    reason: "copyright",
    note: "Fayl dərslikdən skan edilib.",
    status: "open",
    reporter: AYSEL,
    handled_by: null,
    handled_at: null,
    created_at: "2026-10-26T08:00:00Z",
  },
  {
    id: "c0000000-0000-4000-8000-000000000002",
    material_id: MATERIALS[0]!.id,
    material_title: "Təsviri statistika",
    subject_id: MATERIALS[0]!.subject_id,
    subject_name: "Statistika",
    material_hidden: false,
    reason: "wrong_content",
    note: "",
    status: "dismissed",
    reporter: RAMIN,
    handled_by: { id: "d0000000-0000-4000-8000-000000000001", display_name: "Elvin Quliyev" },
    handled_at: "2026-10-26T09:30:00Z",
    created_at: "2026-10-25T14:10:00Z",
  },
];

const FEEDBACK: FeedbackItem[] = [
  {
    id: "e0000000-0000-4000-8000-000000000001",
    category: "problem",
    message: "Cədvəldə 1-301 otağı göstərilmir.",
    page: "/schedule",
    contact_ok: true,
    status: "open",
    sender: { ...AYSEL, email: "aysel.mammadova@smartazmiu.test" },
    handled_by: null,
    handled_at: null,
    created_at: "2026-10-26T08:00:00Z",
  },
  {
    id: "e0000000-0000-4000-8000-000000000002",
    category: "suggestion",
    message: "Qaranlıq rejimdə mətnlər rahat oxunur, təşəkkür edirik.",
    page: "",
    contact_ok: false,
    status: "closed",
    sender: { id: RAMIN.id, display_name: RAMIN.display_name, email: null },
    handled_by: "Elvin Quliyev",
    handled_at: "2026-10-26T10:00:00Z",
    created_at: "2026-10-25T16:20:00Z",
  },
];

const REPORTS: ReportItem[] = [
  {
    id: "f0000000-0000-4000-8000-000000000001",
    target_type: "message",
    reason: "spam",
    note: "",
    status: "open",
    created_at: "2026-10-26T08:00:00Z",
    reporter: { ...AYSEL, photo_url: null, badge: null },
    reported_user: { ...RAMIN, photo_url: null, badge: null },
    message: {
      id: "1001",
      channel_id: "1b2c3d4e-5f60-4a71-8b92-a3b4c5d6e7f8",
      channel_name: "Statistika",
      author: { ...RAMIN, photo_url: null, badge: null },
      body: "Reklam mətni",
      deleted: false,
      created_at: "2026-10-26T07:55:00Z",
    },
    handled_by: null,
    handled_at: null,
    reporters: 2,
    sla_due_at: "2026-10-26T20:00:00Z",
    sla_breached: false,
  },
];

/** The panel the admin and catalogue pages put their tables in. */
function ListPanel({ children }: { children: ReactNode }) {
  return (
    <Panel>
      <PanelBody>{children}</PanelBody>
    </Panel>
  );
}

export function Sprint6Specimens() {
  const t = useTranslations("designSystem.sections");
  const tReports = useTranslations("reports.admin");
  return (
    <ApiProvider csrfToken="specimen">
      <Section title={t("tour")}>
        <OnboardingTour roles={["student"]} />
      </Section>
      <Section title={t("materials")}>
        <ListPanel>
          <MaterialTable items={MATERIALS} caption={t("materials")} showSemester />
        </ListPanel>
      </Section>
      <Section title={t("materialReports")}>
        <ListPanel>
          <MaterialReportTable items={MATERIAL_REPORTS} canHandle />
        </ListPanel>
      </Section>
      <Section title={t("feedbackList")}>
        <ListPanel>
          <FeedbackTable items={FEEDBACK} canHandle />
        </ListPanel>
      </Section>
      <Section title={t("reportList")}>
        <ListPanel>
          <ReportTable items={REPORTS} caption={tReports("tableCaption")} canHandle canGlobalBan />
        </ListPanel>
      </Section>
    </ApiProvider>
  );
}

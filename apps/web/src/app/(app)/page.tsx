import { GraduationCap } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("dashboard");
  return { title: t("title") };
}

/**
 * Sprint 1 dashboard: academic data is not imported yet, so every user sees the explanatory empty state
 * required for "user with no enrollments" (§13.1). Widgets arrive with schedule, announcements and chat.
 */
export default async function DashboardPage() {
  const t = await getTranslations("dashboard");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <Panel>
        <PanelHeader title={t("academicDataTitle")} />
        <PanelBody>
          <EmptyState
            className="py-2"
            icon={GraduationCap}
            message={t("noAcademicData")}
            action={<p className="max-w-[75ch] text-sm text-muted">{t("noAcademicDataHint")}</p>}
          />
        </PanelBody>
      </Panel>
    </>
  );
}

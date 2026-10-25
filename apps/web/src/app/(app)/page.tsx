import { Megaphone, MessagesSquare } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { MyAcademics } from "@/features/academics/my-academics";
import { NoticePrompt } from "@/features/privacy/privacy-parts";
import { bakuToday } from "@/features/schedule/model";
import { TodayClasses } from "@/features/schedule/schedule-views";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("dashboard");
  return { title: t("title") };
}

/**
 * Dashboard: today's classes, announcements and unread chat, then the user's group and subjects. Announcements
 * arrive with Sprint 4 and chat with Sprint 5; until then their widgets explain what will appear (D-043).
 */
export default async function DashboardPage() {
  const t = await getTranslations("dashboard");
  const api = await serverApi();
  const today = bakuToday();
  const [schedule, academics, consents] = await Promise.all([
    api
      .GET("/api/v1/me/schedule", { params: { query: { start: today, end: today } } })
      .then(loaded),
    api.GET("/api/v1/me/academics").then(loaded),
    api.GET("/api/v1/me/consents").then(loaded),
  ]);
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <div className="flex flex-col gap-6">
        {consents.status === "ok" ? <NoticePrompt consents={consents.data} /> : null}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-start">
          {schedule.status === "ok" ? (
            <TodayClasses schedule={schedule.data} />
          ) : (
            <ForbiddenState />
          )}
          <div className="flex flex-col gap-6">
            <Panel>
              <PanelHeader title={t("announcementsTitle")} />
              <PanelBody>
                <EmptyState className="py-0" icon={Megaphone} message={t("announcementsEmpty")} />
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title={t("chatTitle")} />
              <PanelBody>
                <EmptyState className="py-0" icon={MessagesSquare} message={t("chatPlaceholder")} />
              </PanelBody>
            </Panel>
          </div>
        </div>
        {academics.status === "ok" ? <MyAcademics data={academics.data} /> : <ForbiddenState />}
      </div>
    </>
  );
}

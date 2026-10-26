import { Megaphone } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";
import { MyAcademics } from "@/features/academics/my-academics";
import { AnnouncementList } from "@/features/announcements/announcement-list";
import { DASHBOARD_COUNT } from "@/features/announcements/model";
import { UnreadSummary } from "@/features/chat/unread-summary";
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
 * Dashboard: today's classes, the newest announcements and unread chat, then the user's group and subjects.
 */
export default async function DashboardPage() {
  const t = await getTranslations("dashboard");
  const api = await serverApi();
  const today = bakuToday();
  const [schedule, academics, consents, announcements, chat] = await Promise.all([
    api
      .GET("/api/v1/me/schedule", { params: { query: { start: today, end: today } } })
      .then(loaded),
    api.GET("/api/v1/me/academics").then(loaded),
    api.GET("/api/v1/me/consents").then(loaded),
    api
      .GET("/api/v1/announcements", { params: { query: { limit: DASHBOARD_COUNT } } })
      .then(loaded),
    api.GET("/api/v1/chat/channels").then(loaded),
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
              <PanelBody className="flex flex-col gap-4">
                {announcements.status !== "ok" ? (
                  <ForbiddenState />
                ) : announcements.data.items.length === 0 ? (
                  <EmptyState className="py-0" icon={Megaphone} message={t("announcementsEmpty")} />
                ) : (
                  <>
                    <AnnouncementList items={announcements.data.items} compact />
                    <TextLink href="/announcements">{t("allAnnouncements")}</TextLink>
                  </>
                )}
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title={t("chatTitle")} />
              <PanelBody>
                {chat.status === "ok" ? (
                  <UnreadSummary channels={chat.data.channels} />
                ) : (
                  <ForbiddenState />
                )}
              </PanelBody>
            </Panel>
          </div>
        </div>
        {academics.status === "ok" ? <MyAcademics data={academics.data} /> : <ForbiddenState />}
      </div>
    </>
  );
}

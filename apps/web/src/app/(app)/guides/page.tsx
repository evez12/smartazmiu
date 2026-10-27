import { ChevronRight, Compass, GraduationCap, NotebookPen } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { StudentAdviceDisclaimer } from "@/features/mentorship/disclaimer";
import { GuideStatsLine } from "@/features/mentorship/guide-stats";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("guides");
  return { title: t("title") };
}

/** Find a guide for my subjects, become a guide for subjects I passed, my guide profiles (§5.2). */
export default async function GuidesPage() {
  const t = await getTranslations("guides");
  const api = await serverApi();
  const [subjects, eligible, mine, tipSubjects] = await Promise.all([
    api.GET("/api/v1/materials/subjects").then(loaded),
    api.GET("/api/v1/guides/eligible").then(loaded),
    api.GET("/api/v1/guides/me").then(loaded),
    api.GET("/api/v1/tips/eligible").then(loaded),
  ]);
  const tTips = await getTranslations("guides.tips");
  const header = (
    <PageHeader
      title={t("title")}
      description={t("description")}
      breadcrumb={[{ label: t("title") }]}
      actions={
        <Link href="/guides/requests" className={buttonVariants({ variant: "secondary" })}>
          {t("requestsLink")}
        </Link>
      }
    />
  );
  if (subjects.status !== "ok" || eligible.status !== "ok" || mine.status !== "ok") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }
  return (
    <>
      {header}
      <div className="flex flex-col gap-6">
        <StudentAdviceDisclaimer />
        <Panel>
          <PanelHeader title={t("findTitle")} description={t("findDescription")} />
          {subjects.data.items.length === 0 ? (
            <PanelBody>
              <EmptyState icon={Compass} message={t("subjectsEmpty")} />
            </PanelBody>
          ) : (
            <ul aria-label={t("findTitle")} className="divide-y divide-border">
              {subjects.data.items.map((subject) => (
                <li key={subject.id}>
                  <Link
                    href={`/guides/${subject.id}`}
                    className="flex min-h-14 items-center gap-3 px-4 py-2 hover:bg-bg-subtle"
                  >
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="font-medium break-words">{subject.name}</span>
                      <span className="text-sm text-muted">{subject.code}</span>
                    </span>
                    <Icon icon={ChevronRight} className="text-muted" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <PanelHeader title={t("becomeTitle")} description={t("becomeDescription")} />
          {eligible.data.length === 0 ? (
            <PanelBody>
              <EmptyState icon={GraduationCap} message={t("becomeEmpty")} />
            </PanelBody>
          ) : (
            <ul aria-label={t("becomeTitle")} className="divide-y divide-border">
              {eligible.data.map((item) => (
                <li key={item.subject_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium break-words">{item.subject_name}</span>
                    <span className="text-sm text-muted">
                      {t("passedIn", { semester: item.semester })}
                    </span>
                  </span>
                  <Link
                    href={`/guides/opt-in/${item.subject_id}`}
                    className={buttonVariants({
                      variant: item.opted_in ? "secondary" : "primary",
                    })}
                  >
                    {item.opted_in ? t("editProfile") : t("optIn")}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <PanelHeader title={tTips("myCardsTitle")} description={tTips("myCardsDescription")} />
          {tipSubjects.status !== "ok" || tipSubjects.data.length === 0 ? (
            <PanelBody>
              <EmptyState icon={NotebookPen} message={tTips("myCardsEmpty")} />
            </PanelBody>
          ) : (
            <ul aria-label={tTips("myCardsTitle")} className="divide-y divide-border">
              {tipSubjects.data.map((item) => (
                <li
                  key={`${item.subject_id}-${item.semester_id}`}
                  className="flex flex-wrap items-center gap-3 px-4 py-3"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium break-words">{item.subject_name}</span>
                    <span className="text-sm text-muted">{item.semester}</span>
                  </span>
                  {item.tip_status ? (
                    <Tag tone="neutral">{tTips(`status.${item.tip_status}`)}</Tag>
                  ) : null}
                  <Link
                    href={`/guides/tips/${item.subject_id}?semester=${item.semester_id}`}
                    className={buttonVariants({ variant: "secondary" })}
                  >
                    {item.tip_status ? tTips("edit") : tTips("write")}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        {mine.data.length > 0 ? (
          <Panel>
            <PanelHeader title={t("myProfilesTitle")} />
            <ul aria-label={t("myProfilesTitle")} className="divide-y divide-border">
              {mine.data.map((profile) => (
                <li key={profile.subject_id} className="flex flex-col gap-1 px-4 py-3">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{profile.subject_name}</span>
                    <Tag tone="accent" icon={Compass}>
                      {profile.semester}
                    </Tag>
                    <Tag tone="neutral">{t(`availability.${profile.availability}`)}</Tag>
                  </span>
                  <GuideStatsLine stats={profile.stats} />
                </li>
              ))}
            </ul>
          </Panel>
        ) : null}
      </div>
    </>
  );
}

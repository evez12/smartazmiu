import { CalendarArrowDown } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { bakuToday, dayFromParam, mondayOf, type ScheduleView } from "@/features/schedule/model";
import { DayView, ScheduleToolbar, WeekView } from "@/features/schedule/schedule-views";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("schedule");
  return { title: t("title") };
}

type SchedulePageProps = {
  searchParams: Promise<{ view?: string; date?: string }>;
};

export default async function SchedulePage({ searchParams }: SchedulePageProps) {
  const t = await getTranslations("schedule");
  const params = await searchParams;
  const view: ScheduleView = params.view === "day" ? "day" : "week";
  const today = bakuToday();
  const day = dayFromParam(params.date, today);
  const start = view === "week" ? mondayOf(day) : day;

  const result = await loaded(
    await (
      await serverApi()
    ).GET("/api/v1/me/schedule", {
      params: { query: { start, end: view === "week" ? undefined : day } },
    }),
  );

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
        actions={
          // A file download, not a page: a plain anchor through the same-origin API proxy.
          <a href="/api/v1/me/schedule.ics" download className={buttonVariants()}>
            <Icon icon={CalendarArrowDown} />
            {t("download")}
          </a>
        }
      />
      {result.status === "forbidden" ? (
        <ForbiddenState />
      ) : (
        <>
          <ScheduleToolbar view={view} day={day} today={result.data.today} />
          {view === "week" ? (
            <WeekView schedule={result.data} />
          ) : (
            <DayView schedule={result.data} />
          )}
        </>
      )}
    </>
  );
}

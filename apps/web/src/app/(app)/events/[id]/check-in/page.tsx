import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { CheckInDesk } from "@/features/events/check-in";
import { CHECK_IN_PERMISSION } from "@/features/events/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";
import { formatDateTimeRange } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("events.checkIn");
  return { title: t("title") };
}

type CheckInPageProps = { params: Promise<{ id: string }> };

export default async function CheckInPage({ params }: CheckInPageProps) {
  const t = await getTranslations("events");
  const { id } = await params;
  if (!(await hasPermission(CHECK_IN_PERMISSION))) {
    return (
      <>
        <PageHeader
          title={t("checkIn.title")}
          breadcrumb={[{ label: t("title"), href: "/events" }, { label: t("checkIn.title") }]}
        />
        <ForbiddenState />
      </>
    );
  }
  const api = await serverApi();
  const result = await api
    .GET("/api/v1/events/{event_id}", { params: { path: { event_id: id } } })
    .then(loaded);
  if (result.status !== "ok") return <ForbiddenState />;
  const event = result.data;
  return (
    <>
      <PageHeader
        title={t("checkIn.title")}
        description={`${event.title} · ${formatDateTimeRange(event.starts_at, event.ends_at)}`}
        breadcrumb={[
          { label: t("title"), href: "/events" },
          { label: event.title, href: `/events/${event.id}` },
          { label: t("checkIn.title") },
        ]}
      />
      <p className="mb-4 max-w-[75ch] text-muted">{t("checkIn.description")}</p>
      <CheckInDesk eventId={event.id} />
    </>
  );
}

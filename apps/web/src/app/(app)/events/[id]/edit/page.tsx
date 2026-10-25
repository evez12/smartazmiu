import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { EventEditor } from "@/features/events/event-editor";
import { MANAGE_PERMISSION } from "@/features/events/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("events.editor");
  return { title: t("editTitle") };
}

type EditEventPageProps = { params: Promise<{ id: string }> };

export default async function EditEventPage({ params }: EditEventPageProps) {
  const t = await getTranslations("events");
  const { id } = await params;
  const header = (title: string) => (
    <PageHeader
      title={t("editor.editTitle")}
      description={t("editor.editDescription")}
      breadcrumb={[
        { label: t("title"), href: "/events" },
        { label: title, href: `/events/${id}` },
        { label: t("editor.editTitle") },
      ]}
    />
  );
  if (!(await hasPermission(MANAGE_PERMISSION))) {
    return (
      <>
        {header(t("title"))}
        <ForbiddenState />
      </>
    );
  }
  const api = await serverApi();
  const result = await api
    .GET("/api/v1/events/{event_id}", { params: { path: { event_id: id } } })
    .then(loaded);
  if (result.status !== "ok") return <ForbiddenState />;
  return (
    <>
      {header(result.data.title)}
      <Panel>
        <PanelBody>
          <EventEditor event={result.data} />
        </PanelBody>
      </Panel>
    </>
  );
}

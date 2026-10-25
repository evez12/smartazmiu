import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { AnnouncementEditor } from "@/features/announcements/announcement-editor";
import { PUBLISH_PERMISSION } from "@/features/announcements/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("announcements.editor");
  return { title: t("editTitle") };
}

type EditAnnouncementPageProps = { params: Promise<{ id: string }> };

export default async function EditAnnouncementPage({ params }: EditAnnouncementPageProps) {
  const t = await getTranslations("announcements");
  const { id } = await params;
  const header = (title: string) => (
    <PageHeader
      title={t("editor.editTitle")}
      description={t("editor.editDescription")}
      breadcrumb={[
        { label: t("title"), href: "/announcements" },
        { label: title, href: `/announcements/${id}` },
        { label: t("editor.editTitle") },
      ]}
    />
  );
  if (!(await hasPermission(PUBLISH_PERMISSION))) {
    return (
      <>
        {header(t("title"))}
        <ForbiddenState />
      </>
    );
  }
  const api = await serverApi();
  const result = await api
    .GET("/api/v1/announcements/{announcement_id}", { params: { path: { announcement_id: id } } })
    .then(loaded);
  if (result.status !== "ok") return <ForbiddenState />;
  return (
    <>
      {header(result.data.title)}
      <Panel>
        <PanelBody>
          <AnnouncementEditor announcement={result.data} />
        </PanelBody>
      </Panel>
    </>
  );
}

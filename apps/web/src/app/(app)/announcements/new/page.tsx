import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { AnnouncementEditor } from "@/features/announcements/announcement-editor";
import { PUBLISH_PERMISSION } from "@/features/announcements/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("announcements.editor");
  return { title: t("newTitle") };
}

export default async function NewAnnouncementPage() {
  const t = await getTranslations("announcements");
  return (
    <>
      <PageHeader
        title={t("editor.newTitle")}
        description={t("editor.newDescription")}
        breadcrumb={[
          { label: t("title"), href: "/announcements" },
          { label: t("editor.newTitle") },
        ]}
      />
      {(await hasPermission(PUBLISH_PERMISSION)) ? (
        <Panel>
          <PanelBody>
            <AnnouncementEditor />
          </PanelBody>
        </Panel>
      ) : (
        <ForbiddenState />
      )}
    </>
  );
}

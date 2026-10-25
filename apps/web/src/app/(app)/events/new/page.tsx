import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { EventEditor } from "@/features/events/event-editor";
import { MANAGE_PERMISSION } from "@/features/events/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("events.editor");
  return { title: t("newTitle") };
}

export default async function NewEventPage() {
  const t = await getTranslations("events");
  return (
    <>
      <PageHeader
        title={t("editor.newTitle")}
        description={t("editor.newDescription")}
        breadcrumb={[{ label: t("title"), href: "/events" }, { label: t("editor.newTitle") }]}
      />
      {(await hasPermission(MANAGE_PERMISSION)) ? (
        <Panel>
          <PanelBody>
            <EventEditor />
          </PanelBody>
        </Panel>
      ) : (
        <ForbiddenState />
      )}
    </>
  );
}

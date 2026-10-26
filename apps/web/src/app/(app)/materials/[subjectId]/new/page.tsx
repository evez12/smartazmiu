import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { materialHref } from "@/features/materials/model";
import { UploadForm } from "@/features/materials/upload-form";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("materials.form");
  return { title: t("newTitle") };
}

export default async function NewMaterialPage({
  params,
}: {
  params: Promise<{ subjectId: string }>;
}) {
  const t = await getTranslations("materials");
  const { subjectId } = await params;
  const result = await (
    await serverApi()
  )
    .GET("/api/v1/subjects/{subject_id}/materials", { params: { path: { subject_id: subjectId } } })
    .then(loaded);
  const breadcrumb = [
    { label: t("title"), href: "/materials" },
    ...(result.status === "ok"
      ? [{ label: result.data.subject_name, href: materialHref(subjectId) }]
      : []),
    { label: t("form.newTitle") },
  ];
  return (
    <>
      <PageHeader
        title={t("form.newTitle")}
        description={t("form.newDescription")}
        breadcrumb={breadcrumb}
      />
      {result.status !== "ok" || !result.data.can_upload ? (
        <ForbiddenState />
      ) : (
        <Panel className="max-w-2xl">
          <PanelBody>
            <UploadForm mode="material" subjectId={subjectId} semesters={result.data.semesters} />
          </PanelBody>
        </Panel>
      )}
    </>
  );
}

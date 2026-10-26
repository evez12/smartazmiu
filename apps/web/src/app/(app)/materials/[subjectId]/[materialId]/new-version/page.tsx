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
  return { title: t("versionTitle") };
}

export default async function NewVersionPage({
  params,
}: {
  params: Promise<{ subjectId: string; materialId: string }>;
}) {
  const t = await getTranslations("materials");
  const { subjectId, materialId } = await params;
  const result = await (
    await serverApi()
  )
    .GET("/api/v1/materials/{material_id}", { params: { path: { material_id: materialId } } })
    .then(loaded);
  const breadcrumb = [
    { label: t("title"), href: "/materials" },
    ...(result.status === "ok"
      ? [{ label: result.data.title, href: materialHref(subjectId, materialId) }]
      : []),
    { label: t("form.versionTitle") },
  ];
  return (
    <>
      <PageHeader
        title={t("form.versionTitle")}
        description={t("form.versionDescription")}
        breadcrumb={breadcrumb}
      />
      {result.status !== "ok" || !result.data.can_edit ? (
        <ForbiddenState />
      ) : (
        <Panel className="max-w-2xl">
          <PanelBody>
            <UploadForm
              mode="version"
              subjectId={subjectId}
              semesterId={result.data.semester.id}
              materialId={materialId}
            />
          </PanelBody>
        </Panel>
      )}
    </>
  );
}

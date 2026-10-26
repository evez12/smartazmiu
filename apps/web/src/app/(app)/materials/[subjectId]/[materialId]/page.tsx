import { Upload } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Banner } from "@/components/ui/banner";
import { buttonVariants } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { MaterialActions } from "@/features/materials/material-actions";
import { materialHref, STATUS_TONE } from "@/features/materials/model";
import { VersionActions } from "@/features/materials/version-actions";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";
import { formatDateTime } from "@/lib/format";
import { formatSize } from "@/lib/uploads";

type MaterialPageProps = { params: Promise<{ subjectId: string; materialId: string }> };

async function load(materialId: string) {
  return (await serverApi())
    .GET("/api/v1/materials/{material_id}", { params: { path: { material_id: materialId } } })
    .then(loaded);
}

export async function generateMetadata({ params }: MaterialPageProps): Promise<Metadata> {
  const t = await getTranslations("materials");
  const result = await load((await params).materialId);
  return { title: result.status === "ok" ? result.data.title : t("title") };
}

/** A material with every version the viewer may see (§6.1): others see checked files only. */
export default async function MaterialPage({ params }: MaterialPageProps) {
  const t = await getTranslations("materials");
  const { subjectId, materialId } = await params;
  const [result, canManage] = await Promise.all([
    load(materialId),
    hasPermission("materials.manage"),
  ]);
  if (result.status !== "ok") {
    return (
      <>
        <PageHeader title={t("title")} breadcrumb={[{ label: t("title"), href: "/materials" }]} />
        <ForbiddenState />
      </>
    );
  }
  const material = result.data;
  return (
    <>
      <PageHeader
        title={material.title}
        description={`${t(`types.${material.type}`)} · ${material.semester.label}`}
        breadcrumb={[
          { label: t("title"), href: "/materials" },
          { label: material.subject_name, href: materialHref(subjectId) },
          { label: material.title },
        ]}
        actions={
          material.can_edit ? (
            <Link
              href={`${materialHref(subjectId, materialId)}/new-version`}
              className={buttonVariants({ variant: "primary" })}
            >
              <Icon icon={Upload} />
              {t("newVersion")}
            </Link>
          ) : undefined
        }
      />
      <div className="flex flex-col gap-4">
        {material.hidden ? <Banner tone="warning" title={t("hiddenBanner")} /> : null}
        {material.scanning ? <Banner tone="info" title={t("scanningBanner")} /> : null}
        <Panel>
          <PanelBody className="flex flex-col gap-3">
            {material.description ? (
              <p className="break-words whitespace-pre-wrap">{material.description}</p>
            ) : null}
            {material.current ? (
              <div className="flex flex-wrap items-center gap-3">
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="font-medium break-all">{material.current.filename}</span>
                  <span className="text-sm text-muted tabular">
                    {t("versionLabel", { version: material.current.version })} ·{" "}
                    {formatSize(material.current.size_bytes)}
                  </span>
                </span>
                <VersionActions version={material.current} />
              </div>
            ) : (
              <p className="text-muted">{t("noCleanVersion")}</p>
            )}
            <div>
              <MaterialActions
                materialId={material.id}
                hidden={material.hidden}
                canManage={canManage}
              />
            </div>
          </PanelBody>
        </Panel>
        {material.versions.length > 0 ? (
          <Panel>
            <PanelHeader title={t("versions")} />
            <div className="px-4 pb-4">
              <Table>
                <TableCaption>{t("versionsCaption")}</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("columns.file")}</TableHead>
                    <TableHead>{t("columns.updated")}</TableHead>
                    <TableHead>{t("columns.status")}</TableHead>
                    <TableHead>{t("columns.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {material.versions.map((version) => (
                    <TableRow key={version.id}>
                      <TableCell label={t("columns.file")} className="max-w-md">
                        <span className="flex flex-col">
                          <span className="break-all">
                            {t("versionLabel", { version: version.version })} · {version.filename}
                          </span>
                          {version.note ? (
                            <span className="text-sm break-words text-muted">{version.note}</span>
                          ) : null}
                        </span>
                      </TableCell>
                      <TableCell label={t("columns.updated")}>
                        <span className="text-sm tabular">
                          {t("uploadedBy", {
                            name: version.uploaded_by?.display_name ?? t("deletedAccount"),
                            time: formatDateTime(version.created_at),
                          })}
                        </span>
                      </TableCell>
                      <TableCell label={t("columns.status")}>
                        <Tag tone={STATUS_TONE[version.status]}>
                          {t(`status.${version.status}`)}
                        </Tag>
                      </TableCell>
                      <TableCell label={t("columns.actions")}>
                        <VersionActions version={version} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Panel>
        ) : null}
      </div>
    </>
  );
}

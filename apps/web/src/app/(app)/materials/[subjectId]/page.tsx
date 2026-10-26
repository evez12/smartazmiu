import { BookOpen, Upload } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { MaterialTable } from "@/features/materials/material-table";
import { materialHref } from "@/features/materials/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { cn } from "@/lib/cn";
import { loaded, serverApi } from "@/lib/api/server";

type CatalogPageProps = {
  params: Promise<{ subjectId: string }>;
  searchParams: Promise<{ semester?: string }>;
};

export async function generateMetadata({ params }: CatalogPageProps): Promise<Metadata> {
  const t = await getTranslations("materials");
  const { subjectId } = await params;
  const result = await (
    await serverApi()
  )
    .GET("/api/v1/subjects/{subject_id}/materials", { params: { path: { subject_id: subjectId } } })
    .then(loaded);
  return { title: result.status === "ok" ? result.data.subject_name : t("title") };
}

/** One subject's catalogue with a semester filter (§6.1); unknown or unreadable subjects are a 404. */
export default async function SubjectMaterialsPage({ params, searchParams }: CatalogPageProps) {
  const t = await getTranslations("materials");
  const { subjectId } = await params;
  const { semester } = await searchParams;
  const result = await (
    await serverApi()
  )
    .GET("/api/v1/subjects/{subject_id}/materials", {
      params: { path: { subject_id: subjectId }, query: { semester_id: semester || undefined } },
    })
    .then(loaded);
  if (result.status !== "ok") {
    return (
      <>
        <PageHeader title={t("title")} breadcrumb={[{ label: t("title"), href: "/materials" }]} />
        <ForbiddenState />
      </>
    );
  }
  const catalog = result.data;
  const selected = catalog.semesters.find((item) => item.id === semester)?.id;
  const filters = [
    { id: undefined, label: t("allSemesters") },
    ...catalog.semesters.map((item) => ({ id: item.id, label: item.label })),
  ];
  return (
    <>
      <PageHeader
        title={catalog.subject_name}
        description={t("catalogDescription", { code: catalog.subject_code })}
        breadcrumb={[{ label: t("title"), href: "/materials" }, { label: catalog.subject_name }]}
        actions={
          catalog.can_upload ? (
            <Link
              href={`${materialHref(subjectId)}/new`}
              className={buttonVariants({ variant: "primary" })}
            >
              <Icon icon={Upload} />
              {t("upload")}
            </Link>
          ) : undefined
        }
      />
      <Panel>
        {catalog.semesters.length > 1 ? (
          <nav
            aria-label={t("semesterFilter")}
            className="flex gap-4 overflow-x-auto border-b border-border px-4"
          >
            {filters.map((filter) => {
              const active = filter.id === selected;
              return (
                <Link
                  key={filter.id ?? "all"}
                  href={
                    filter.id
                      ? `${materialHref(subjectId)}?semester=${filter.id}`
                      : materialHref(subjectId)
                  }
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "-mb-px flex h-10 items-center border-b-2 font-medium whitespace-nowrap",
                    active
                      ? "border-primary text-text"
                      : "border-transparent text-muted hover:text-text",
                  )}
                >
                  {filter.label}
                </Link>
              );
            })}
          </nav>
        ) : null}
        {catalog.materials.length === 0 ? (
          <PanelBody>
            <EmptyState
              className="py-0"
              icon={BookOpen}
              message={catalog.can_upload ? t("catalogEmptyUploader") : t("catalogEmpty")}
            />
          </PanelBody>
        ) : (
          <div className="px-4 pb-4">
            <MaterialTable
              items={catalog.materials}
              caption={t("tableCaption")}
              showSemester={!selected}
            />
          </div>
        )}
      </Panel>
    </>
  );
}

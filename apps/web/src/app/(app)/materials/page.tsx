import { BookOpen, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { materialHref } from "@/features/materials/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("materials");
  return { title: t("title") };
}

/** Subjects whose catalogue the user can read (§6.1): enrolled, taught, or all with materials for staff. */
export default async function MaterialsPage() {
  const t = await getTranslations("materials");
  const result = await (await serverApi()).GET("/api/v1/materials/subjects").then(loaded);
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      {result.status !== "ok" ? (
        <ForbiddenState />
      ) : result.data.items.length === 0 ? (
        <Panel className="px-4">
          <EmptyState icon={BookOpen} message={t("subjectsEmpty")} />
        </Panel>
      ) : (
        <Panel>
          <ul aria-label={t("subjectsCaption")} className="divide-y divide-border">
            {result.data.items.map((subject) => (
              <li key={subject.id}>
                <Link
                  href={materialHref(subject.id)}
                  className="flex min-h-14 items-center gap-3 px-4 py-2 hover:bg-bg-subtle"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium break-words">{subject.name}</span>
                    <span className="text-sm text-muted">{subject.code}</span>
                  </span>
                  <span className="text-sm text-muted tabular">
                    {t("materialCount", { count: subject.materials })}
                  </span>
                  <Icon icon={ChevronRight} className="text-muted" />
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </>
  );
}

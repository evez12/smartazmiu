import { FileUp, Upload } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { pageFromParam, Pagination } from "@/components/ui/pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { ImportTable } from "@/features/imports/import-table";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

const PAGE_SIZE = 25;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("imports");
  return { title: t("title") };
}

type ImportsPageProps = { searchParams: Promise<{ page?: string | string[] }> };

export default async function ImportsPage({ searchParams }: ImportsPageProps) {
  const t = await getTranslations("imports");
  const page = pageFromParam((await searchParams).page);
  const result = await loaded(
    await (
      await serverApi()
    ).GET("/api/v1/admin/imports", {
      params: { query: { offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE } },
    }),
  );
  const breadcrumb = [{ label: t("title") }];
  if (result.status === "forbidden") {
    return (
      <>
        <PageHeader title={t("title")} breadcrumb={breadcrumb} />
        <ForbiddenState />
      </>
    );
  }

  const uploadLink = (
    <Link href="/admin/imports/new" className={buttonVariants({ variant: "primary" })}>
      <Icon icon={Upload} />
      {t("upload")}
    </Link>
  );
  const { items, total } = result.data;
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={breadcrumb}
        actions={uploadLink}
      />
      <Panel>
        <PanelHeader title={t("recentTitle")} />
        {items.length === 0 ? (
          <PanelBody>
            <EmptyState className="py-0" icon={FileUp} message={t("empty")} />
          </PanelBody>
        ) : (
          <div className="flex flex-col gap-4 px-4 pb-4">
            <ImportTable items={items} now={new Date()} />
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              href={(target) => `/admin/imports?page=${target}`}
            />
          </div>
        )}
      </Panel>
    </>
  );
}

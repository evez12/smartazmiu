import { Upload } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { cache } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { ApplyImportButton } from "@/features/imports/import-actions";
import {
  EncodingBanner,
  ImportIssues,
  ImportStatusBanner,
  ImportSummary,
} from "@/features/imports/import-detail";
import { displayStatus } from "@/features/imports/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";
import { formatDateTime } from "@/lib/format";

type ImportPageProps = { params: Promise<{ id: string }> };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Shared by generateMetadata and the page, so the import is fetched once per request.
const loadImport = cache(async (id: string) => {
  if (!UUID.test(id)) notFound();
  return loaded(
    await (
      await serverApi()
    ).GET("/api/v1/admin/imports/{import_id}", { params: { path: { import_id: id } } }),
  );
});

export async function generateMetadata({ params }: ImportPageProps): Promise<Metadata> {
  const result = await loadImport((await params).id);
  const t = await getTranslations("imports");
  return { title: result.status === "ok" ? result.data.file_name : t("title") };
}

export default async function ImportPage({ params }: ImportPageProps) {
  const t = await getTranslations("imports");
  const result = await loadImport((await params).id);
  if (result.status === "forbidden") {
    return (
      <>
        <PageHeader title={t("title")} breadcrumb={[{ label: t("title") }]} />
        <ForbiddenState />
      </>
    );
  }

  const record = result.data;
  const status = displayStatus(record);
  const uploadAnother = (
    <Link
      href={`/admin/imports/new?kind=${record.kind}`}
      className={buttonVariants({ variant: status === "ready" ? "secondary" : "primary" })}
    >
      <Icon icon={Upload} />
      {t("detail.uploadAnother")}
    </Link>
  );
  return (
    <>
      <PageHeader
        title={record.file_name}
        description={t("detail.kindAndUpload", {
          kind: t(`kinds.${record.kind}`),
          name: record.created_by?.display_name ?? t("system"),
          date: formatDateTime(record.created_at),
        })}
        breadcrumb={[{ label: t("title"), href: "/admin/imports" }, { label: record.file_name }]}
        actions={
          <>
            {uploadAnother}
            {status === "ready" ? <ApplyImportButton record={record} /> : null}
          </>
        }
      />
      <div className="flex flex-col gap-6">
        <ImportStatusBanner record={record} status={status} />
        <EncodingBanner record={record} />
        <ImportSummary record={record} />
        <ImportIssues record={record} />
      </div>
    </>
  );
}

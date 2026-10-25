import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { IMPORT_KINDS, IMPORT_PERMISSION, type ImportKind } from "@/features/imports/model";
import { UploadForm } from "@/features/imports/upload-form";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("imports.new");
  return { title: t("title") };
}

type NewImportPageProps = { searchParams: Promise<{ kind?: string }> };

export default async function NewImportPage({ searchParams }: NewImportPageProps) {
  const t = await getTranslations("imports");
  const breadcrumb = [{ label: t("title"), href: "/admin/imports" }, { label: t("new.title") }];
  if (!(await hasPermission(IMPORT_PERMISSION))) {
    return (
      <>
        <PageHeader title={t("new.title")} breadcrumb={breadcrumb} />
        <ForbiddenState />
      </>
    );
  }
  const requested = (await searchParams).kind;
  const initialKind = IMPORT_KINDS.find((kind) => kind === requested) ?? IMPORT_KINDS[0];
  return (
    <>
      <PageHeader
        title={t("new.title")}
        description={t("new.description")}
        breadcrumb={breadcrumb}
      />
      <Panel>
        <PanelBody className="p-6">
          <UploadForm initialKind={initialKind as ImportKind} />
        </PanelBody>
      </Panel>
    </>
  );
}

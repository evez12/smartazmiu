import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { SyncAdmin } from "@/features/cabinet/sync-admin";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("cabinet.admin"))("title") };
}

/** Staff page for the cabinet sync (D-126). The API checks the permission again on every call. */
export default async function Route() {
  const t = await getTranslations("cabinet.admin");
  const allowed = await hasPermission("cabinet.manage");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      {allowed ? <SyncAdmin /> : <ForbiddenState />}
    </>
  );
}

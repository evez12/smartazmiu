import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { AssignmentsPage } from "@/features/assignments/assignments-list";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("assignments"))("title") };
}

export default async function AssignmentsRoute() {
  const t = await getTranslations("assignments");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <AssignmentsPage />
    </>
  );
}

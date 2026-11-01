import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { ExamsPage } from "@/features/exams/exams-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("exams"))("title") };
}

export default async function Route() {
  const t = await getTranslations("exams");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <ExamsPage />
    </>
  );
}

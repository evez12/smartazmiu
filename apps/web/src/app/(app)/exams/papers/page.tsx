import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { PapersPage } from "@/features/exams/papers-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("exams.papers"))("title") };
}

export default async function Route() {
  const parent = await getTranslations("exams");
  const t = await getTranslations("exams.papers");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: parent("title"), href: "/exams" }, { label: t("title") }]}
      />
      <PapersPage />
    </>
  );
}

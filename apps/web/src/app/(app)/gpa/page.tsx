import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { GpaPage } from "@/features/gpa/gpa-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("gpa"))("title") };
}

export default async function Route() {
  const t = await getTranslations("gpa");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <GpaPage />
    </>
  );
}

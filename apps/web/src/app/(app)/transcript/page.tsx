import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { TranscriptPage } from "@/features/cabinet/transcript-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("cabinet.transcript"))("title") };
}

export default async function Route() {
  const t = await getTranslations("cabinet.transcript");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <TranscriptPage />
    </>
  );
}

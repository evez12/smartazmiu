import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { FeedPage } from "@/features/community/community-pages";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("community");
  return { title: t("feedTitle") };
}

export default async function FeedRoute() {
  const t = await getTranslations("community");
  return (
    <>
      <PageHeader
        title={t("feedTitle")}
        description={t("feedDescription")}
        breadcrumb={[{ label: t("feedTitle") }]}
      />
      <FeedPage />
    </>
  );
}

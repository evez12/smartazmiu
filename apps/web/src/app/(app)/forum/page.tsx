import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuestionsPage } from "@/features/community/community-pages";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("community");
  return { title: t("forumTitle") };
}

export default async function ForumRoute() {
  const t = await getTranslations("community");
  return (
    <>
      <PageHeader
        title={t("forumTitle")}
        description={t("forumDescription")}
        breadcrumb={[{ label: t("forumTitle") }]}
      />
      <QuestionsPage />
    </>
  );
}

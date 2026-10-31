import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuestionsPage } from "@/features/community/forum-pages";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("community");
  return { title: t("forumTitle") };
}

export default async function ForumRoute({
  searchParams,
}: {
  searchParams: Promise<{ tag?: string }>;
}) {
  const t = await getTranslations("community");
  const { tag } = await searchParams;
  return (
    <>
      <PageHeader
        title={t("forumTitle")}
        description={t("forumDescription")}
        breadcrumb={[{ label: t("forumTitle") }]}
      />
      <QuestionsPage tag={tag} />
    </>
  );
}

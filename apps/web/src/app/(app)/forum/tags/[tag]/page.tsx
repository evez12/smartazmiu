import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuestionsPage } from "@/features/community/community-pages";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ tag: string }>;
}): Promise<Metadata> {
  const t = await getTranslations("community");
  const { tag } = await params;
  return { title: `${t("tagTitle")}: ${tag}` };
}

export default async function TagRoute({ params }: { params: Promise<{ tag: string }> }) {
  const t = await getTranslations("community");
  const { tag } = await params;
  return (
    <>
      <PageHeader
        title={`${t("tagTitle")}: ${tag}`}
        breadcrumb={[{ label: t("forumTitle"), href: "/forum" }, { label: tag }]}
      />
      <QuestionsPage tag={tag} />
    </>
  );
}

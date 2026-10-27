import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuestionPage } from "@/features/community/community-pages";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("community");
  return { title: t("questionTitle") };
}

export default async function QuestionRoute({ params }: { params: Promise<{ id: string }> }) {
  const t = await getTranslations("community");
  const { id } = await params;
  return (
    <>
      <PageHeader
        title={t("questionTitle")}
        breadcrumb={[{ label: t("forumTitle"), href: "/forum" }, { label: t("questionTitle") }]}
      />
      <QuestionPage id={id} />
    </>
  );
}

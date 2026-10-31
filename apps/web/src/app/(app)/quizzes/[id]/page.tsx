import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizPage } from "@/features/quizzes/quiz-detail";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("quizzes"))("detailTitle") };
}

export default async function QuizRoute({ params }: { params: Promise<{ id: string }> }) {
  const t = await getTranslations("quizzes");
  const { id } = await params;
  return (
    <>
      <PageHeader
        title={t("detailTitle")}
        breadcrumb={[{ label: t("title"), href: "/quizzes" }, { label: t("detailTitle") }]}
      />
      <QuizPage id={id} />
    </>
  );
}

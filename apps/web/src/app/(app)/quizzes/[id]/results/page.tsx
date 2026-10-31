import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizResults } from "@/features/quizzes/quiz-results";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("quizzes.results"))("title") };
}

export default async function ResultsRoute({ params }: { params: Promise<{ id: string }> }) {
  const t = await getTranslations("quizzes");
  const { id } = await params;
  return (
    <>
      <PageHeader
        title={t("results.title")}
        description={t("results.description")}
        breadcrumb={[
          { label: t("title"), href: "/quizzes" },
          { label: t("detailTitle"), href: `/quizzes/${id}` },
          { label: t("results.title") },
        ]}
      />
      <QuizResults quizId={id} />
    </>
  );
}

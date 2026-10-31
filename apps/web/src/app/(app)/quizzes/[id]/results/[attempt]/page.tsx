import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizReview } from "@/features/quizzes/quiz-review";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("quizzes.review"))("title") };
}

export default async function ReviewRoute({
  params,
}: {
  params: Promise<{ id: string; attempt: string }>;
}) {
  const t = await getTranslations("quizzes");
  const { id, attempt } = await params;
  return (
    <>
      <PageHeader
        title={t("review.title")}
        breadcrumb={[
          { label: t("title"), href: "/quizzes" },
          { label: t("results.title"), href: `/quizzes/${id}/results` },
          { label: t("review.title") },
        ]}
      />
      <QuizReview quizId={id} attemptId={attempt} />
    </>
  );
}

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizAttemptPage } from "@/features/quizzes/quiz-attempt";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("quizzes.attempt"))("resultHeading") };
}

export default async function AttemptRoute({
  params,
}: {
  params: Promise<{ id: string; attempt: string }>;
}) {
  const t = await getTranslations("quizzes");
  const { id, attempt } = await params;
  return (
    <>
      <PageHeader
        title={t("detailTitle")}
        breadcrumb={[
          { label: t("title"), href: "/quizzes" },
          { label: t("detailTitle"), href: `/quizzes/${id}` },
        ]}
      />
      <QuizAttemptPage quizId={id} attemptId={attempt} />
    </>
  );
}

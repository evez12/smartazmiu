import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizAttempt } from "@/features/quizzes/quiz-forms";

export default async function QuizPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("quizzes");
  return (
    <>
      <PageHeader
        title={t("takeTitle")}
        description={t("takeDescription")}
        breadcrumb={[{ label: t("title"), href: "/quizzes" }, { label: t("takeTitle") }]}
      />
      <QuizAttempt quizId={id} />
    </>
  );
}

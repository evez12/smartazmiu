import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizBuilder } from "@/features/quizzes/quiz-forms";

export default async function NewQuizPage({
  searchParams,
}: {
  searchParams: Promise<{ courseOfferingId?: string }>;
}) {
  const t = await getTranslations("quizzes");
  const params = await searchParams;
  return (
    <>
      <PageHeader
        title={t("newTitle")}
        description={t("newDescription")}
        breadcrumb={[{ label: t("title"), href: "/quizzes" }, { label: t("newTitle") }]}
      />
      <QuizBuilder courseOfferingId={params.courseOfferingId ?? ""} />
    </>
  );
}

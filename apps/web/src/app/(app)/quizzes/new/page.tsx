import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizBuilder } from "@/features/quizzes/quiz-builder";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("quizzes"))("newTitle") };
}

export default async function NewQuizRoute() {
  const t = await getTranslations("quizzes");
  return (
    <>
      <PageHeader
        title={t("newTitle")}
        description={t("newDescription")}
        breadcrumb={[{ label: t("title"), href: "/quizzes" }, { label: t("newTitle") }]}
      />
      <QuizBuilder />
    </>
  );
}

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizzesPage } from "@/features/quizzes/quizzes-list";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("quizzes"))("title") };
}

export default async function QuizzesRoute() {
  const t = await getTranslations("quizzes");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <QuizzesPage />
    </>
  );
}

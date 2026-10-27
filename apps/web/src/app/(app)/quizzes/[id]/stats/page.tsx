import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { QuizStats } from "@/features/quizzes/stats-view";

export default async function QuizStatsPage() {
  const t = await getTranslations("quizzes");
  return (
    <>
      <PageHeader
        title={t("statsTitle")}
        description={t("statsDescription")}
        breadcrumb={[{ label: t("title"), href: "/quizzes" }, { label: t("statsTitle") }]}
      />
      <QuizStats />
    </>
  );
}

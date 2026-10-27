import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { GradeView } from "@/features/assignments/grade-view";

export default async function AssignmentGradePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("assignments");
  return (
    <>
      <PageHeader
        title={t("gradeTitle")}
        description={t("gradeDescription")}
        breadcrumb={[{ label: t("title"), href: "/assignments" }, { label: t("gradeTitle") }]}
      />
      <GradeView submissionId={id} />
    </>
  );
}

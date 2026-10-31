import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { GradeSubmission } from "@/features/assignments/grade-submission";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("assignments"))("gradeTitle") };
}

export default async function GradeRoute({
  params,
}: {
  params: Promise<{ id: string; submission: string }>;
}) {
  const t = await getTranslations("assignments");
  const { id, submission } = await params;
  return (
    <>
      <PageHeader
        title={t("gradeTitle")}
        breadcrumb={[
          { label: t("title"), href: "/assignments" },
          { label: t("detailTitle"), href: `/assignments/${id}` },
          { label: t("gradeTitle") },
        ]}
      />
      <GradeSubmission assignmentId={id} submissionId={submission} />
    </>
  );
}

import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { AssignmentSubmission } from "@/features/assignments/assignment-forms";

export default async function AssignmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("assignments");
  return (
    <>
      <PageHeader
        title={t("submitTitle")}
        description={t("submitDescription")}
        breadcrumb={[{ label: t("title"), href: "/assignments" }, { label: t("submitTitle") }]}
      />
      <AssignmentSubmission assignmentId={id} />
    </>
  );
}

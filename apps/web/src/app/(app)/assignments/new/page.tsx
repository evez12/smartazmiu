import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { AssignmentBuilder } from "@/features/assignments/assignment-forms";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("assignments"))("newTitle") };
}

export default async function NewAssignmentPage({
  searchParams,
}: {
  searchParams: Promise<{ courseOfferingId?: string }>;
}) {
  const t = await getTranslations("assignments");
  const params = await searchParams;
  return (
    <>
      <PageHeader
        title={t("newTitle")}
        description={t("newDescription")}
        breadcrumb={[{ label: t("title"), href: "/assignments" }, { label: t("newTitle") }]}
      />
      <AssignmentBuilder courseOfferingId={params.courseOfferingId ?? ""} />
    </>
  );
}

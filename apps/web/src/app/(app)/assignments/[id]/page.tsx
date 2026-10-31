import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { AssignmentPage } from "@/features/assignments/assignment-detail";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("assignments"))("detailTitle") };
}

export default async function AssignmentRoute({ params }: { params: Promise<{ id: string }> }) {
  const t = await getTranslations("assignments");
  const { id } = await params;
  return (
    <>
      <PageHeader
        title={t("detailTitle")}
        breadcrumb={[{ label: t("title"), href: "/assignments" }, { label: t("detailTitle") }]}
      />
      <AssignmentPage id={id} />
    </>
  );
}

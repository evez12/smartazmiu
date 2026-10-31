import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { MyCoursePage } from "@/features/attendance/report-pages";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("attendance.mine"))("title") };
}

export default async function MyCourseRoute({ params }: { params: Promise<{ id: string }> }) {
  const t = await getTranslations("attendance");
  const mine = await getTranslations("attendance.mine");
  const { id } = await params;
  return (
    <>
      <PageHeader
        title={mine("title")}
        breadcrumb={[{ label: t("title"), href: "/attendance" }, { label: mine("title") }]}
      />
      <MyCoursePage offeringId={id} />
    </>
  );
}

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { ReportPage } from "@/features/attendance/report-pages";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("attendance.report"))("title") };
}

export default async function ReportRoute({ params }: { params: Promise<{ id: string }> }) {
  const t = await getTranslations("attendance");
  const report = await getTranslations("attendance.report");
  const { id } = await params;
  return (
    <>
      <PageHeader
        title={report("title")}
        breadcrumb={[{ label: t("title"), href: "/attendance" }, { label: report("title") }]}
      />
      <ReportPage offeringId={id} />
    </>
  );
}

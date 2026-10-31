import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { AttendancePage } from "@/features/attendance/attendance-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("attendance"))("title") };
}

export default async function AttendanceRoute() {
  const t = await getTranslations("attendance");
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <AttendancePage />
    </>
  );
}

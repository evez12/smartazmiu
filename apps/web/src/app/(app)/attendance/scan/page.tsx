import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { ScanPage } from "@/features/attendance/scan-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("attendance.scan"))("title") };
}

export default async function ScanRoute() {
  const t = await getTranslations("attendance");
  const scan = await getTranslations("attendance.scan");
  return (
    <>
      <PageHeader
        title={scan("title")}
        description={scan("description")}
        breadcrumb={[{ label: t("title"), href: "/attendance" }, { label: scan("title") }]}
      />
      <ScanPage />
    </>
  );
}

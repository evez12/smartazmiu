import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { SessionScreen } from "@/features/attendance/session-screen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("attendance.session"))("title") };
}

export default async function SessionRoute({ params }: { params: Promise<{ id: string }> }) {
  const t = await getTranslations("attendance");
  const session = await getTranslations("attendance.session");
  const { id } = await params;
  return (
    <>
      <PageHeader
        title={session("title")}
        breadcrumb={[{ label: t("title"), href: "/attendance" }, { label: session("title") }]}
      />
      <SessionScreen sessionId={id} />
    </>
  );
}

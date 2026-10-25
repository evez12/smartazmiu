import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { MyAcademics } from "@/features/academics/my-academics";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("dashboard");
  return { title: t("title") };
}

/** Dashboard: the user's group and subjects for now; schedule, announcements and chat widgets follow. */
export default async function DashboardPage() {
  const t = await getTranslations("dashboard");
  const academics = await loaded(await (await serverApi()).GET("/api/v1/me/academics"));
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      {academics.status === "ok" ? <MyAcademics data={academics.data} /> : <ForbiddenState />}
    </>
  );
}

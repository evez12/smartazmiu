import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { MyAcademics } from "@/features/academics/my-academics";
import { NoticePrompt } from "@/features/privacy/privacy-parts";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("dashboard");
  return { title: t("title") };
}

/** Dashboard: the user's group and subjects for now; schedule, announcements and chat widgets follow. */
export default async function DashboardPage() {
  const t = await getTranslations("dashboard");
  const api = await serverApi();
  const [academics, consents] = await Promise.all([
    api.GET("/api/v1/me/academics").then(loaded),
    api.GET("/api/v1/me/consents").then(loaded),
  ]);
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <div className="flex flex-col gap-6">
        {consents.status === "ok" ? <NoticePrompt consents={consents.data} /> : null}
        {academics.status === "ok" ? <MyAcademics data={academics.data} /> : <ForbiddenState />}
      </div>
    </>
  );
}

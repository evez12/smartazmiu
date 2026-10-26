import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { RequestList } from "@/features/mentorship/request-list";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("guides");
  return { title: t("requestsTitle") };
}

export default async function MentorRequestsPage() {
  const t = await getTranslations("guides");
  return (
    <>
      <PageHeader
        title={t("requestsTitle")}
        description={t("requestsDescription")}
        breadcrumb={[{ label: t("title"), href: "/guides" }, { label: t("requestsTitle") }]}
      />
      <RequestList />
    </>
  );
}

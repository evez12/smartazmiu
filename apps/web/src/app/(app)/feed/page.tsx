import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { FeedPage } from "@/features/community/feed-page";
import { hasPermission } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("community");
  return { title: t("feedTitle") };
}

export default async function FeedRoute({
  searchParams,
}: {
  searchParams: Promise<{ tag?: string }>;
}) {
  const t = await getTranslations("community");
  const { tag } = await searchParams;
  return (
    <>
      <PageHeader
        title={t("feedTitle")}
        description={t("feedDescription")}
        breadcrumb={[{ label: t("feedTitle") }]}
      />
      <FeedPage canModerate={await hasPermission("admin.reports.handle")} tag={tag} />
    </>
  );
}

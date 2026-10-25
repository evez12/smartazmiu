import { Megaphone, Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";
import { AnnouncementList } from "@/features/announcements/announcement-list";
import { PAGE_SIZE, PUBLISH_PERMISSION } from "@/features/announcements/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("announcements");
  return { title: t("title") };
}

type AnnouncementsPageProps = { searchParams: Promise<{ before?: string }> };

export default async function AnnouncementsPage({ searchParams }: AnnouncementsPageProps) {
  const t = await getTranslations("announcements");
  const { before } = await searchParams;
  const api = await serverApi();
  const [page, canPublish] = await Promise.all([
    api
      .GET("/api/v1/announcements", { params: { query: { limit: PAGE_SIZE, before } } })
      .then(loaded),
    hasPermission(PUBLISH_PERMISSION),
  ]);
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
        actions={
          canPublish ? (
            <>
              <Link href="/announcements/manage" className={buttonVariants()}>
                {t("manage")}
              </Link>
              <Link href="/announcements/new" className={buttonVariants({ variant: "primary" })}>
                <Icon icon={Plus} />
                {t("create")}
              </Link>
            </>
          ) : undefined
        }
      />
      {page.status !== "ok" ? (
        <ForbiddenState />
      ) : page.data.items.length === 0 ? (
        <Panel className="px-4">
          <EmptyState icon={Megaphone} message={t("empty")} />
        </Panel>
      ) : (
        <div className="flex flex-col gap-4">
          <Panel>
            <AnnouncementList items={page.data.items} />
          </Panel>
          {page.data.next_before ? (
            <TextLink href={`/announcements?before=${page.data.next_before}`}>
              {t("loadMore")}
            </TextLink>
          ) : null}
        </div>
      )}
    </>
  );
}

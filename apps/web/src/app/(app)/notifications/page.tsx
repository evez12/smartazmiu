import { Settings } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Inbox } from "@/features/notifications/inbox";
import { PAGE_SIZE } from "@/features/notifications/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("notifications");
  return { title: t("title") };
}

export default async function NotificationsPage() {
  const t = await getTranslations("notifications");
  const api = await serverApi();
  const firstPage = await api
    .GET("/api/v1/me/notifications", { params: { query: { limit: PAGE_SIZE } } })
    .then(loaded);
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
        actions={
          <Link href="/notifications/settings" className={buttonVariants({ variant: "secondary" })}>
            <Icon icon={Settings} />
            {t("openSettings")}
          </Link>
        }
      />
      {firstPage.status === "ok" ? <Inbox firstPage={firstPage.data} /> : <ForbiddenState />}
    </>
  );
}

import { Pencil } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { ArchiveButton } from "@/features/announcements/archive-button";
import { PUBLISH_PERMISSION } from "@/features/announcements/model";
import { AudienceLabel } from "@/features/audiences/audience-label";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";
import { formatDateTime } from "@/lib/format";

type AnnouncementPageProps = { params: Promise<{ id: string }> };

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("announcements");
  return { title: t("title") };
}

export default async function AnnouncementPage({ params }: AnnouncementPageProps) {
  const t = await getTranslations("announcements");
  const { id } = await params;
  const api = await serverApi();
  const [result, canPublish] = await Promise.all([
    api
      .GET("/api/v1/announcements/{announcement_id}", {
        params: { path: { announcement_id: id } },
      })
      .then(loaded),
    hasPermission(PUBLISH_PERMISSION),
  ]);
  if (result.status !== "ok") return <ForbiddenState />;
  const item = result.data;
  const published = item.status === "published";
  return (
    <>
      <PageHeader
        title={item.title}
        breadcrumb={[{ label: t("title"), href: "/announcements" }, { label: item.title }]}
        actions={
          canPublish && published ? (
            <>
              <Link href={`/announcements/${item.id}/edit`} className={buttonVariants()}>
                <Icon icon={Pencil} />
                {t("staff.edit")}
              </Link>
              <ArchiveButton announcementId={item.id} />
            </>
          ) : undefined
        }
      />
      <Panel>
        <PanelBody className="flex flex-col gap-6">
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
            <div className="flex flex-col">
              <dt className="text-sm text-muted">{t("audience")}</dt>
              <dd>
                <AudienceLabel audience={item.audience} />
              </dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-sm text-muted">{t("published")}</dt>
              <dd className="tabular">{formatDateTime(item.published_at)}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-sm text-muted">{t("expires")}</dt>
              <dd className="tabular">
                {!published ? (
                  <Tag>{t("status.archived")}</Tag>
                ) : item.expires_at ? (
                  t("until", { date: formatDateTime(item.expires_at) })
                ) : (
                  t("noExpiry")
                )}
              </dd>
            </div>
          </dl>
          <p className="max-w-[75ch] break-words whitespace-pre-line text-text">{item.body}</p>
        </PanelBody>
      </Panel>
    </>
  );
}

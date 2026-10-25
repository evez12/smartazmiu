import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { pageFromParam, Pagination } from "@/components/ui/pagination";
import { Panel } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { AudienceLabel } from "@/features/audiences/audience-label";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";
import { formatDateTime, formatNumber } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("announcements.staff");
  return { title: t("manageTitle") };
}

type ManagePageProps = { searchParams: Promise<{ page?: string }> };

export default async function ManageAnnouncementsPage({ searchParams }: ManagePageProps) {
  const t = await getTranslations("announcements");
  const page = pageFromParam((await searchParams).page);
  const api = await serverApi();
  const result = await api
    .GET("/api/v1/announcements/managed", { params: { query: { page } } })
    .then(loaded);
  const header = (
    <PageHeader
      title={t("staff.manageTitle")}
      description={t("staff.manageDescription")}
      breadcrumb={[
        { label: t("title"), href: "/announcements" },
        { label: t("staff.manageTitle") },
      ]}
      actions={
        result.status === "ok" ? (
          <Link href="/announcements/new" className={buttonVariants({ variant: "primary" })}>
            <Icon icon={Plus} />
            {t("create")}
          </Link>
        ) : undefined
      }
    />
  );
  if (result.status !== "ok") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }
  const { items, total, page_size: pageSize } = result.data;
  return (
    <>
      {header}
      <Panel>
        {items.length === 0 ? (
          <div className="px-4">
            <EmptyState message={t("staff.manageEmpty")} />
          </div>
        ) : (
          <>
            <Table>
              <TableCaption>{t("staff.tableLabel")}</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("staff.columns.title")}</TableHead>
                  <TableHead>{t("staff.columns.audience")}</TableHead>
                  <TableHead>{t("staff.columns.published")}</TableHead>
                  <TableHead numeric>{t("staff.columns.recipients")}</TableHead>
                  <TableHead>{t("staff.columns.status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell label={t("staff.columns.title")}>
                      <TextLink href={`/announcements/${item.id}`} className="break-words">
                        {item.title}
                      </TextLink>
                    </TableCell>
                    <TableCell label={t("staff.columns.audience")}>
                      <AudienceLabel audience={item.audience} />
                    </TableCell>
                    <TableCell label={t("staff.columns.published")} className="tabular">
                      {formatDateTime(item.published_at)}
                    </TableCell>
                    <TableCell label={t("staff.columns.recipients")} numeric>
                      {formatNumber(item.recipients)}
                    </TableCell>
                    <TableCell label={t("staff.columns.status")}>
                      <Tag tone={item.status === "published" ? "success" : "neutral"}>
                        {t(`status.${item.status}`)}
                      </Tag>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              href={(target) =>
                target === 1 ? "/announcements/manage" : `/announcements/manage?page=${target}`
              }
              className="border-t border-border p-4"
            />
          </>
        )}
      </Panel>
    </>
  );
}

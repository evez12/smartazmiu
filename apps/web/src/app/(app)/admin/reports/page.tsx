import { Flag } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { pageFromParam, Pagination } from "@/components/ui/pagination";
import { Panel, PanelBody } from "@/components/ui/panel";
import { listHref } from "@/features/admin/model";
import { ReportTable } from "@/features/reports/report-table";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { getCurrentUser, loaded, serverApi } from "@/lib/api/server";

const PAGE_SIZE = 25;
const STATUSES = ["open", "actioned", "dismissed"] as const;
type Status = (typeof STATUSES)[number];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("reports.admin");
  return { title: t("title") };
}

type ReportsPageProps = { searchParams: Promise<{ status?: string; page?: string }> };

/** Reports for staff and admins (§5.5, D-070); open ones first by default. No moderation console yet (Sprint 10). */
export default async function ReportsPage({ searchParams }: ReportsPageProps) {
  const t = await getTranslations("reports.admin");
  const params = await searchParams;
  // "all" lists every status; anything unknown falls back to the open queue.
  const status: Status | undefined =
    params.status === "all"
      ? undefined
      : (STATUSES.find((value) => value === params.status) ?? "open");
  const page = pageFromParam(params.page);
  const [result, me] = await Promise.all([
    (async () =>
      loaded(
        await (
          await serverApi()
        ).GET("/api/v1/moderation/reports", {
          params: { query: { status, offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE } },
        }),
      ))(),
    getCurrentUser(),
  ]);
  const header = (
    <PageHeader
      title={t("title")}
      description={t("description")}
      breadcrumb={[{ label: t("title") }]}
    />
  );
  if (result.status === "forbidden") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }
  const canHandle = me.status === "ok" && me.user.permissions.includes("admin.reports.handle");
  const filter = status ?? "all";

  return (
    <>
      {header}
      <Panel>
        <form
          method="get"
          className="grid gap-4 border-b border-border p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
        >
          <Field label={t("columns.status")}>
            <Select name="status" defaultValue={filter}>
              {[...STATUSES, "all" as const].map((value) => (
                <option key={value} value={value}>
                  {t(`filters.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
          <div>
            <Button type="submit">{t("filters.apply")}</Button>
          </div>
        </form>
        {result.data.items.length === 0 ? (
          <PanelBody>
            <EmptyState className="py-0" icon={Flag} message={t("empty")} />
          </PanelBody>
        ) : (
          <div className="flex flex-col gap-4 px-4 pb-4">
            <ReportTable
              items={result.data.items}
              caption={t("tableCaption")}
              canHandle={canHandle}
            />
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={result.data.total}
              href={(target) => listHref("/admin/reports", { status: filter, page: target })}
            />
          </div>
        )}
      </Panel>
    </>
  );
}

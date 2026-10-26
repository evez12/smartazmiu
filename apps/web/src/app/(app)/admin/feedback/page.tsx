import { MessageSquareText } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { pageFromParam, Pagination } from "@/components/ui/pagination";
import { Panel, PanelBody } from "@/components/ui/panel";
import { listHref } from "@/features/admin/model";
import { FeedbackTable } from "@/features/feedback/feedback-table";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";

const PAGE_SIZE = 25;
const STATUSES = ["open", "closed"] as const;
type Status = (typeof STATUSES)[number];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("feedback.admin");
  return { title: t("title") };
}

type FeedbackPageProps = { searchParams: Promise<{ status?: string; page?: string }> };

/** Feedback from the pilot form for staff (D-074); open items first by default. */
export default async function FeedbackPage({ searchParams }: FeedbackPageProps) {
  const t = await getTranslations("feedback.admin");
  const params = await searchParams;
  const status: Status | undefined =
    params.status === "all"
      ? undefined
      : (STATUSES.find((value) => value === params.status) ?? "open");
  const page = pageFromParam(params.page);
  const [result, canHandle] = await Promise.all([
    (await serverApi())
      .GET("/api/v1/admin/feedback", {
        params: { query: { status, offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE } },
      })
      .then(loaded),
    hasPermission("admin.feedback.handle"),
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
            <EmptyState className="py-0" icon={MessageSquareText} message={t("empty")} />
          </PanelBody>
        ) : (
          <div className="flex flex-col gap-4 px-4 pb-4">
            <FeedbackTable items={result.data.items} canHandle={canHandle} />
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={result.data.total}
              href={(target) => listHref("/admin/feedback", { status: filter, page: target })}
            />
          </div>
        )}
      </Panel>
    </>
  );
}

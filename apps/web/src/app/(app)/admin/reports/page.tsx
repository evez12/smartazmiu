import { Flag } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { pageFromParam, Pagination } from "@/components/ui/pagination";
import { Panel, PanelBody } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listHref } from "@/features/admin/model";
import { TipReview } from "@/features/knowledge/tip-review";
import { MaterialReportTable } from "@/features/materials/material-report-table";
import { ReportTable } from "@/features/reports/report-table";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { getCurrentUser, loaded, serverApi } from "@/lib/api/server";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";

const PAGE_SIZE = 25;
const STATUSES = ["open", "actioned", "dismissed"] as const;
type Status = (typeof STATUSES)[number];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("reports.admin");
  return { title: t("title") };
}

type ReportsPageProps = {
  searchParams: Promise<{ kind?: string; status?: string; page?: string }>;
};

/**
 * Reports for staff and admins (§5.5, D-070), messages and people or materials (D-071); open ones first by
 * default. No moderation console yet (Sprint 10).
 */
export default async function ReportsPage({ searchParams }: ReportsPageProps) {
  const t = await getTranslations("reports.admin");
  const tMaterials = await getTranslations("materials");
  const params = await searchParams;
  // "all" lists every status; anything unknown falls back to the open queue.
  const status: Status | undefined =
    params.status === "all"
      ? undefined
      : (STATUSES.find((value) => value === params.status) ?? "open");
  const kind =
    params.kind === "materials"
      ? "materials"
      : params.kind === "guides"
        ? "guides"
        : params.kind === "tips"
          ? "tips"
          : "messages";
  const tTips = await getTranslations("guides.tipModeration");
  const tTipText = await getTranslations("guides.tips");
  const tGuides = await getTranslations("guides.feedbackNotes");
  const tRequest = await getTranslations("guides.request");
  const page = pageFromParam(params.page);
  const query = { status, offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE };
  const api = await serverApi();
  const [messageReports, materialReports, me] = await Promise.all([
    kind === "messages"
      ? api.GET("/api/v1/moderation/reports", { params: { query } }).then(loaded)
      : null,
    kind === "materials"
      ? api.GET("/api/v1/moderation/material-reports", { params: { query } }).then(loaded)
      : null,
    getCurrentUser(),
  ]);
  const guideNotes =
    kind === "guides"
      ? await api
          .GET("/api/v1/moderation/mentor-feedback", {
            params: { query: { offset: query.offset, limit: query.limit } },
          })
          .then(loaded)
      : null;
  const TIP_STATUSES = ["pending", "published", "rejected", "hidden"] as const;
  const tipStatus = TIP_STATUSES.find((value) => value === params.status) ?? "pending";
  const tipQueue =
    kind === "tips"
      ? await api
          .GET("/api/v1/moderation/tips", {
            params: { query: { status: tipStatus, offset: query.offset, limit: query.limit } },
          })
          .then(loaded)
      : null;
  const result = (messageReports ?? materialReports ?? guideNotes ?? tipQueue)!;
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
  const canGlobalBan = me.status === "ok" && me.user.roles.includes("admin");
  const filter = status ?? "all";

  return (
    <>
      {header}
      <nav
        aria-label={tMaterials("admin.tabsLabel")}
        className="mb-4 flex gap-4 overflow-x-auto border-b border-border"
      >
        {(["messages", "materials", "guides", "tips"] as const).map((value) => (
          <Link
            key={value}
            href={listHref("/admin/reports", { kind: value })}
            aria-current={value === kind ? "page" : undefined}
            className={cn(
              "-mb-px flex h-10 items-center border-b-2 font-medium whitespace-nowrap pointer-coarse:h-11",
              value === kind
                ? "border-primary text-text"
                : "border-transparent text-muted hover:text-text",
            )}
          >
            {value === "tips"
              ? tTips("tab")
              : value === "guides"
                ? tGuides("tab")
                : tMaterials(value === "messages" ? "admin.tabMessages" : "admin.tabMaterials")}
          </Link>
        ))}
      </nav>
      {tipQueue?.status === "ok" ? (
        <Panel>
          <form
            method="get"
            className="grid gap-4 border-b border-border p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
          >
            <input type="hidden" name="kind" value="tips" />
            <Field label={tTips("filter")}>
              <Select name="status" defaultValue={tipStatus}>
                {TIP_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {tTipText(`status.${value}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <div>
              <Button type="submit">{tTips("apply")}</Button>
            </div>
          </form>
          {tipQueue.data.items.length === 0 ? (
            <PanelBody>
              <EmptyState className="py-0" icon={Flag} message={tTips("empty")} />
            </PanelBody>
          ) : (
            <div className="flex flex-col gap-4 p-4">
              <ul aria-label={tTips("caption")} className="flex flex-col gap-4">
                {tipQueue.data.items.map((tip) => (
                  <li
                    key={tip.id}
                    className="flex flex-col gap-2 rounded-control border border-border p-4"
                  >
                    <p className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium">{tip.subject_name}</span>
                      <span className="text-muted">{tip.semester}</span>
                      <span className="text-muted">
                        {tTips("author", { name: tip.author_name ?? "—" })}
                      </span>
                      {tip.reports ? (
                        <span className="text-danger">
                          {tTips("reports", { count: tip.reports })}
                        </span>
                      ) : null}
                    </p>
                    <p className="text-sm">
                      {tTipText("difficulty", { value: String(tip.difficulty) })} ·{" "}
                      {tTipText(`hours.${tip.weekly_hours}`)}
                    </p>
                    <p className="break-words whitespace-pre-wrap">{tip.key_topics}</p>
                    <p className="break-words whitespace-pre-wrap">{tip.exam_advice}</p>
                    <p className="break-words whitespace-pre-wrap">{tip.retrospective}</p>
                    {canHandle ? <TipReview tipId={tip.id} status={tip.status} /> : null}
                  </li>
                ))}
              </ul>
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={tipQueue.data.total}
                href={(target) =>
                  listHref("/admin/reports", { kind, status: tipStatus, page: target })
                }
              />
            </div>
          )}
        </Panel>
      ) : guideNotes?.status === "ok" ? (
        <Panel>
          {guideNotes.data.items.length === 0 ? (
            <PanelBody>
              <EmptyState className="py-0" icon={Flag} message={tGuides("empty")} />
            </PanelBody>
          ) : (
            <div className="flex flex-col gap-4 p-4">
              <Table>
                <TableCaption>{tGuides("caption")}</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>{tGuides("subject")}</TableHead>
                    <TableHead>{tGuides("guide")}</TableHead>
                    <TableHead>{tGuides("feedback")}</TableHead>
                    <TableHead>{tGuides("note")}</TableHead>
                    <TableHead>{tGuides("date")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {guideNotes.data.items.map((item) => (
                    <TableRow key={item.request_id}>
                      <TableCell label={tGuides("subject")}>{item.subject_name}</TableCell>
                      <TableCell label={tGuides("guide")}>
                        {item.mentor?.display_name ?? ""}
                      </TableCell>
                      <TableCell label={tGuides("feedback")}>
                        {tRequest(item.feedback === "helpful" ? "helpful" : "notHelpful")}
                      </TableCell>
                      <TableCell
                        label={tGuides("note")}
                        className="break-words whitespace-pre-wrap"
                      >
                        {item.note}
                      </TableCell>
                      <TableCell label={tGuides("date")} className="tabular">
                        {formatDateTime(item.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={guideNotes.data.total}
                href={(target) => listHref("/admin/reports", { kind, page: target })}
              />
            </div>
          )}
        </Panel>
      ) : (
        <Panel>
          <form
            method="get"
            className="grid gap-4 border-b border-border p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
          >
            <input type="hidden" name="kind" value={kind} />
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
              {messageReports?.status === "ok" ? (
                <ReportTable
                  items={messageReports.data.items}
                  caption={t("tableCaption")}
                  canHandle={canHandle}
                  canGlobalBan={canGlobalBan}
                />
              ) : null}
              {materialReports?.status === "ok" ? (
                <MaterialReportTable items={materialReports.data.items} canHandle={canHandle} />
              ) : null}
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={result.data.total}
                href={(target) =>
                  listHref("/admin/reports", { kind, status: filter, page: target })
                }
              />
            </div>
          )}
        </Panel>
      )}
    </>
  );
}

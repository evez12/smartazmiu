"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { offeringLabel, ScreenState, useManagedOfferings } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { useFormatters } from "@/lib/use-format";

export type AssignmentSummary = components["schemas"]["AssignmentSummaryOut"];

const STATUS_TONE = { not_submitted: "neutral", submitted: "info", graded: "success" } as const;

export function AssignmentStatus({
  status,
}: {
  status: NonNullable<AssignmentSummary["my_status"]>;
}) {
  const t = useTranslations("assignments.status");
  return <Tag tone={STATUS_TONE[status]}>{t(status)}</Tag>;
}

/** The assignments of the user's courses: students see their own state, teachers the progress of the class. */
export function AssignmentsPage() {
  const t = useTranslations("assignments");
  const api = useApi();
  const offerings = useManagedOfferings();
  const query = useQuery({
    queryKey: ["assignments"],
    queryFn: async () => unwrap(await api.GET("/api/v1/assignments")).items,
  });
  const canCreate = (offerings.data?.length ?? 0) > 0;
  const items = query.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      {canCreate ? (
        <div>
          <Button asChild variant="primary">
            <Link href="/assignments/new">{t("create")}</Link>
          </Button>
        </div>
      ) : null}
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={!query.isLoading && !query.isError && items.length === 0}
        emptyMessage={canCreate ? t("emptyManager") : t("empty")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
      <ul aria-label={t("listLabel")} className="flex flex-col gap-3">
        {items.map((item) => (
          <li key={item.id}>
            <AssignmentCard item={item} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AssignmentCard({ item }: { item: AssignmentSummary }) {
  const { formatDateTime } = useFormatters();
  const t = useTranslations("assignments");
  return (
    <Panel>
      <PanelBody>
        <article className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold break-words">
            <Link className="text-primary hover:underline" href={`/assignments/${item.id}`}>
              {item.title}
            </Link>
          </h2>
          <p className="text-sm text-muted">{offeringLabel(item.offering)}</p>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
            <span className="tabular">
              {item.deadline
                ? t("deadlineAt", { time: formatDateTime(item.deadline) })
                : t("deadlineNone")}
            </span>
            {item.my_status ? <AssignmentStatus status={item.my_status} /> : null}
            {item.can_manage ? (
              <span className="tabular">
                {t("progress", {
                  submitted: item.submitted_count ?? 0,
                  enrolled: item.enrolled_count ?? 0,
                  graded: item.graded_count ?? 0,
                })}
              </span>
            ) : null}
          </div>
        </article>
      </PanelBody>
    </Panel>
  );
}

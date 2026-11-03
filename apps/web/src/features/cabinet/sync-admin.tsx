"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
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
import { useToast } from "@/components/ui/toast";
import { ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { useFormatters } from "@/lib/use-format";

import { SourceNotice } from "./source-notice";

type Run = components["schemas"]["SyncRunOut"];
type Conflict = components["schemas"]["ConflictOut"];

/**
 * Staff view of the cabinet sync (D-126): outcomes and counts, and which course differs for whom. No grade value
 * from either source appears here or is sent to this page.
 */
export function SyncAdmin() {
  const t = useTranslations("cabinet.admin");
  const api = useApi();
  const toast = useToast();
  const client = useQueryClient();
  const runs = useQuery({
    queryKey: ["cabinet", "runs"],
    queryFn: async () => unwrap(await api.GET("/api/v1/cabinet/sync-runs")),
  });
  const conflicts = useQuery({
    queryKey: ["cabinet", "conflicts"],
    queryFn: async () => unwrap(await api.GET("/api/v1/cabinet/conflicts")),
  });
  const start = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/cabinet/sync-runs")),
    onSuccess: () => {
      toast({ title: t("requested") });
      void client.invalidateQueries({ queryKey: ["cabinet"] });
    },
    onError: () => toast({ title: t("requestFailed"), tone: "danger" }),
  });
  return (
    <div className="flex flex-col gap-4">
      <ScreenState
        loading={runs.isLoading}
        error={runs.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void runs.refetch()}
      />
      {runs.data ? (
        <Panel aria-labelledby="cabinet-runs">
          <PanelHeader
            title={t("runsTitle")}
            titleId="cabinet-runs"
            description={t("runsDescription")}
            action={
              <Button
                network="required"
                variant="secondary"
                loading={start.isPending}
                onClick={() => start.mutate()}
              >
                {t("start")}
              </Button>
            }
          />
          <PanelBody className="flex flex-col gap-3">
            <SourceNotice source={runs.data.source} />
            {runs.data.items.length === 0 ? (
              <p>{t("runsEmpty")}</p>
            ) : (
              <RunTable items={runs.data.items} />
            )}
          </PanelBody>
        </Panel>
      ) : null}
      <Panel aria-labelledby="cabinet-conflicts">
        <PanelHeader
          title={t("conflictsTitle")}
          titleId="cabinet-conflicts"
          description={t("conflictsDescription")}
        />
        <div className="px-4 pb-2">
          <ScreenState
            loading={conflicts.isLoading}
            error={conflicts.error}
            empty={conflicts.isSuccess && conflicts.data.items.length === 0}
            emptyMessage={t("conflictsEmpty")}
            errorMessage={t("error")}
            retryLabel={t("retry")}
            retry={() => void conflicts.refetch()}
          />
          {conflicts.data && conflicts.data.items.length > 0 ? (
            <ConflictTable items={conflicts.data.items} />
          ) : null}
        </div>
      </Panel>
    </div>
  );
}

export function RunTable({ items }: { items: Run[] }) {
  const t = useTranslations("cabinet.admin");
  const { formatDateTime } = useFormatters();
  return (
    <Table>
      <TableCaption>{t("runsTitle")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.time")}</TableHead>
          <TableHead>{t("columns.trigger")}</TableHead>
          <TableHead>{t("columns.outcome")}</TableHead>
          <TableHead numeric>{t("columns.synced")}</TableHead>
          <TableHead numeric>{t("columns.notFound")}</TableHead>
          <TableHead numeric>{t("columns.mismatched")}</TableHead>
          <TableHead numeric>{t("columns.conflicts")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((run) => (
          <TableRow key={run.id}>
            <TableCell label={t("columns.time")} className="whitespace-nowrap tabular">
              {formatDateTime(run.finished_at)}
            </TableCell>
            <TableCell label={t("columns.trigger")}>{t(`trigger.${run.trigger}`)}</TableCell>
            <TableCell label={t("columns.outcome")}>
              <span className="flex flex-col items-start gap-1">
                <Tag tone={run.outcome === "succeeded" ? "success" : "danger"}>
                  {t(`outcome.${run.outcome}`)}
                </Tag>
                {run.error_code ? (
                  <span className="text-xs text-muted">
                    {run.error_code === "cabinet.unavailable"
                      ? t("errorUnavailable")
                      : t("errorInternal")}
                  </span>
                ) : null}
              </span>
            </TableCell>
            <TableCell label={t("columns.synced")} numeric>
              {run.students_synced}
            </TableCell>
            <TableCell label={t("columns.notFound")} numeric>
              {run.students_not_found}
            </TableCell>
            <TableCell label={t("columns.mismatched")} numeric>
              {run.students_mismatched}
            </TableCell>
            <TableCell label={t("columns.conflicts")} numeric>
              {run.conflicts}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function ConflictTable({ items }: { items: Conflict[] }) {
  const t = useTranslations("cabinet.admin");
  const tTerms = useTranslations("gpa.terms");
  const { formatDateTime } = useFormatters();
  return (
    <Table>
      <TableCaption>{t("conflictsTitle")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.universityId")}</TableHead>
          <TableHead>{t("columns.subject")}</TableHead>
          <TableHead>{t("columns.semester")}</TableHead>
          <TableHead>{t("columns.detected")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((conflict) => (
          <TableRow
            key={`${conflict.university_id}-${conflict.subject_code}-${conflict.semester_year}`}
          >
            <TableCell label={t("columns.universityId")} className="tabular">
              {conflict.university_id}
            </TableCell>
            <TableCell label={t("columns.subject")}>{conflict.subject_code}</TableCell>
            <TableCell label={t("columns.semester")}>
              {conflict.semester_year} {tTerms(conflict.semester_term)}
            </TableCell>
            <TableCell label={t("columns.detected")} className="whitespace-nowrap tabular">
              {formatDateTime(conflict.detected_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

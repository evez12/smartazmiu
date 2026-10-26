"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
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
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { formatDateTime } from "@/lib/format";

import { materialHref } from "./model";

export type MaterialReportItem = components["schemas"]["MaterialReportOut"];
type Status = MaterialReportItem["status"];

const STATUS_TONE = { open: "warning", actioned: "success", dismissed: "neutral" } as const;

/** Material reports for staff (D-071); hiding happens on the material's own page. */
export function MaterialReportTable({
  items,
  canHandle,
}: {
  items: MaterialReportItem[];
  canHandle: boolean;
}) {
  const t = useTranslations("reports.admin");
  const tMaterials = useTranslations("materials");
  return (
    <Table>
      <TableCaption>{tMaterials("admin.tableCaption")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.time")}</TableHead>
          <TableHead>{t("columns.target")}</TableHead>
          <TableHead>{t("columns.reason")}</TableHead>
          <TableHead>{t("columns.reporter")}</TableHead>
          <TableHead>{t("columns.status")}</TableHead>
          {canHandle ? <TableHead>{t("columns.actions")}</TableHead> : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell label={t("columns.time")} className="whitespace-nowrap tabular">
              {formatDateTime(item.created_at)}
            </TableCell>
            <TableCell label={t("columns.target")} className="max-w-md">
              <span className="flex flex-col items-start gap-1">
                <TextLink href={materialHref(item.subject_id, item.material_id)}>
                  {tMaterials("admin.material", {
                    subject: item.subject_name,
                    title: item.material_title,
                  })}
                </TextLink>
                {item.material_hidden ? (
                  <Tag tone="warning">{tMaterials("admin.hiddenTag")}</Tag>
                ) : null}
              </span>
            </TableCell>
            <TableCell label={t("columns.reason")}>
              <span className="flex flex-col">
                <span>{tMaterials(`report.reasons.${item.reason}`)}</span>
                {item.note ? (
                  <span className="text-sm break-words text-muted">
                    {t("note", { note: item.note })}
                  </span>
                ) : null}
              </span>
            </TableCell>
            <TableCell label={t("columns.reporter")}>
              {item.reporter?.display_name ?? t("deletedAccount")}
            </TableCell>
            <TableCell label={t("columns.status")}>
              <span className="flex flex-col items-start gap-1">
                <Tag tone={STATUS_TONE[item.status]}>{t(`status.${item.status}`)}</Tag>
                {item.handled_by && item.handled_at ? (
                  <span className="text-xs text-muted">
                    {t("handledBy", {
                      name: item.handled_by.display_name,
                      time: formatDateTime(item.handled_at),
                    })}
                  </span>
                ) : null}
              </span>
            </TableCell>
            {canHandle ? (
              <TableCell label={t("columns.actions")}>
                <StatusActions item={item} />
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function StatusActions({ item }: { item: MaterialReportItem }) {
  const t = useTranslations("reports.admin");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const change = useMutation({
    mutationFn: async (status: Status) =>
      unwrap(
        await api.PATCH("/api/v1/moderation/material-reports/{report_id}", {
          params: { path: { report_id: item.id } },
          body: { status },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("updated") });
      router.refresh();
    },
    onError: () => toast({ title: t("updateFailed"), tone: "danger" }),
  });
  if (item.status !== "open") {
    return (
      <Button size="dense" variant="tertiary" onClick={() => change.mutate("open")}>
        {t("reopen")}
      </Button>
    );
  }
  return (
    <span className="flex flex-wrap gap-2">
      <Button size="dense" loading={change.isPending} onClick={() => change.mutate("actioned")}>
        {t("markActioned")}
      </Button>
      <Button size="dense" variant="tertiary" onClick={() => change.mutate("dismissed")}>
        {t("dismiss")}
      </Button>
    </span>
  );
}

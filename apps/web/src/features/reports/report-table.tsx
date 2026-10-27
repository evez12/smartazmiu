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
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { formatDateTime } from "@/lib/format";

export type ReportItem = components["schemas"]["ReportOut"];
type Status = ReportItem["status"];

const STATUS_TONE = { open: "warning", actioned: "success", dismissed: "neutral" } as const;

/** Reports for staff (§5.5): what was reported, why, by whom, and the status they set (D-070). */
export function ReportTable({
  items,
  caption,
  canHandle,
}: {
  items: ReportItem[];
  caption: string;
  canHandle: boolean;
}) {
  const t = useTranslations("reports.admin");
  const tReasons = useTranslations("reports.reasons");
  return (
    <Table>
      <TableCaption>{caption}</TableCaption>
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
              <Target item={item} />
            </TableCell>
            <TableCell label={t("columns.reason")}>
              <span className="flex flex-col">
                <span>{tReasons(item.reason)}</span>
                {item.note ? (
                  <span className="text-sm break-words text-muted">
                    {t("note", { note: item.note })}
                  </span>
                ) : null}
              </span>
            </TableCell>
            <TableCell label={t("columns.reporter")}>
              <span className="flex flex-col">
                <span>{item.reporter?.display_name ?? t("deletedAccount")}</span>
                {item.reporters > 1 ? (
                  <span className="text-sm text-muted tabular">
                    {t("reporters", { count: item.reporters })}
                  </span>
                ) : null}
              </span>
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

function Target({ item }: { item: ReportItem }) {
  const t = useTranslations("reports.admin");
  if (item.target_type === "user") {
    return (
      <span className="flex flex-col">
        <span className="text-sm text-muted">{t("person")}</span>
        <span>{item.reported_user?.display_name ?? t("deletedAccount")}</span>
      </span>
    );
  }
  if (item.target_type === "tip") {
    return (
      <span className="flex flex-col gap-1">
        <span className="text-sm text-muted">
          {t("tipIn", { subject: item.tip?.subject_name ?? "—" })} ·{" "}
          {item.reported_user?.display_name ?? t("deletedAccount")}
        </span>
        <span className="line-clamp-4 break-words whitespace-pre-wrap">{item.tip?.excerpt}</span>
      </span>
    );
  }
  const message = item.message;
  if (!message) return <span className="text-muted">{t("deletedMessage")}</span>;
  return (
    <span className="flex flex-col gap-1">
      <span className="text-sm text-muted">
        {t("messageIn", { channel: message.channel_name || "—" })} ·{" "}
        {message.author?.display_name ?? t("deletedAccount")}
      </span>
      {/* Shown as plain text: a reported message is exactly what must not be rendered as markup. */}
      <span className="line-clamp-4 break-words whitespace-pre-wrap">{message.body}</span>
      {message.deleted ? <span className="text-xs text-muted">{t("deletedMessage")}</span> : null}
    </span>
  );
}

function StatusActions({ item }: { item: ReportItem }) {
  const t = useTranslations("reports.admin");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const change = useMutation({
    mutationFn: async (status: Status) =>
      unwrap(
        await api.PATCH("/api/v1/moderation/reports/{report_id}", {
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

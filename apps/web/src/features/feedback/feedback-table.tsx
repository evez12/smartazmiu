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

export type FeedbackItem = components["schemas"]["FeedbackOut"];

const STATUS_TONE = { open: "warning", closed: "neutral" } as const;

/** Feedback for staff (D-074): what was said, where, by whom, and whether it was handled. */
export function FeedbackTable({ items, canHandle }: { items: FeedbackItem[]; canHandle: boolean }) {
  const t = useTranslations("feedback.admin");
  const tCategories = useTranslations("feedback.categories");
  return (
    <Table>
      <TableCaption>{t("tableCaption")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.time")}</TableHead>
          <TableHead>{t("columns.category")}</TableHead>
          <TableHead>{t("columns.message")}</TableHead>
          <TableHead>{t("columns.sender")}</TableHead>
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
            <TableCell label={t("columns.category")}>{tCategories(item.category)}</TableCell>
            <TableCell label={t("columns.message")} className="max-w-md">
              <span className="flex flex-col gap-1">
                {/* Plain text: the sender's own words, never rendered as markup. */}
                <span className="break-words whitespace-pre-wrap">{item.message}</span>
                {item.page ? (
                  <span className="text-sm text-muted">{t("page", { page: item.page })}</span>
                ) : null}
              </span>
            </TableCell>
            <TableCell label={t("columns.sender")}>
              <span className="flex flex-col">
                <span>{item.sender?.display_name ?? t("deletedAccount")}</span>
                {item.contact_ok && item.sender?.email ? (
                  <span className="text-sm break-all text-muted">{item.sender.email}</span>
                ) : null}
                {item.contact_ok ? (
                  <span className="text-xs text-muted">{t("contactOk")}</span>
                ) : null}
              </span>
            </TableCell>
            <TableCell label={t("columns.status")}>
              <span className="flex flex-col items-start gap-1">
                <Tag tone={STATUS_TONE[item.status]}>{t(`status.${item.status}`)}</Tag>
                {item.handled_by && item.handled_at ? (
                  <span className="text-xs text-muted">
                    {t("handledBy", {
                      name: item.handled_by,
                      time: formatDateTime(item.handled_at),
                    })}
                  </span>
                ) : null}
              </span>
            </TableCell>
            {canHandle ? (
              <TableCell label={t("columns.actions")}>
                <StatusAction item={item} />
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function StatusAction({ item }: { item: FeedbackItem }) {
  const t = useTranslations("feedback.admin");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const change = useMutation({
    mutationFn: async (status: FeedbackItem["status"]) =>
      unwrap(
        await api.PATCH("/api/v1/admin/feedback/{feedback_id}", {
          params: { path: { feedback_id: item.id } },
          body: { status },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("updated") });
      router.refresh();
    },
    onError: () => toast({ title: t("updateFailed"), tone: "danger" }),
  });
  return item.status === "open" ? (
    <Button size="dense" loading={change.isPending} onClick={() => change.mutate("closed")}>
      {t("close")}
    </Button>
  ) : (
    <Button size="dense" variant="tertiary" onClick={() => change.mutate("open")}>
      {t("reopen")}
    </Button>
  );
}

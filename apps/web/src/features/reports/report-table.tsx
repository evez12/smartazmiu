"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
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
  canGlobalBan,
}: {
  items: ReportItem[];
  caption: string;
  canHandle: boolean;
  canGlobalBan: boolean;
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
                {item.status === "open" ? (
                  <Tag tone={item.sla_breached ? "danger" : "neutral"}>
                    {item.sla_breached
                      ? t("slaBreached")
                      : t("slaDue", { time: formatDateTime(item.sla_due_at) })}
                  </Tag>
                ) : null}
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
                <span className="flex flex-col gap-3">
                  <StatusActions item={item} />
                  {item.message && item.reported_user ? (
                    <ModerationActions item={item} canGlobalBan={canGlobalBan} />
                  ) : null}
                </span>
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

type Action = components["schemas"]["ModerationActionKind"];

function ModerationActions({ item, canGlobalBan }: { item: ReportItem; canGlobalBan: boolean }) {
  const t = useTranslations("reports.admin");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const [action, setAction] = React.useState<Action>("delete_message");
  const [duration, setDuration] = React.useState("3600");
  const [reason, setReason] = React.useState("");
  const change = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/moderation/actions", {
          body: {
            action,
            channel_id: item.message!.channel_id,
            message_id: ["delete_message", "restore_message", "lock_thread"].includes(action)
              ? item.message!.id
              : null,
            target_user_id: item.reported_user!.id,
            duration_seconds: ["mute", "slow_mode"].includes(action) ? Number(duration) : null,
            reason,
          },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("actionDone") });
      router.refresh();
    },
    onError: () => toast({ title: t("actionFailed"), tone: "danger" }),
  });
  return (
    <form
      className="flex min-w-0 flex-1 flex-col gap-2 md:min-w-52"
      onSubmit={(event) => {
        event.preventDefault();
        change.mutate();
      }}
    >
      <Field label={t("moderationAction")}>
        <Select value={action} onChange={(event) => setAction(event.target.value as Action)}>
          {(
            [
              "delete_message",
              "restore_message",
              "mute",
              "kick",
              "ban",
              "global_ban",
              "lock_thread",
              "slow_mode",
            ] as Action[]
          )
            .filter((value) => value !== "global_ban" || canGlobalBan)
            .map((value) => (
              <option key={value} value={value}>
                {t(`actions.${value}`)}
              </option>
            ))}
        </Select>
      </Field>
      {["mute", "slow_mode"].includes(action) ? (
        <Field label={t("duration")}>
          <Select value={duration} onChange={(event) => setDuration(event.target.value)}>
            {(action === "mute" ? [3600, 86400, 604800] : [0, 10, 30, 60]).map((value) => (
              <option key={value} value={value}>
                {t("seconds", { count: value })}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}
      <Field label={t("reasonLabel")}>
        <Input value={reason} onChange={(event) => setReason(event.target.value)} required />
      </Field>
      <Button type="submit" size="dense" variant="secondary" loading={change.isPending}>
        {t("applyAction")}
      </Button>
    </form>
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

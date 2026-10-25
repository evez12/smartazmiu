"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";

import { KIND_KEYS, type NotificationItem } from "./model";

type NotificationRowProps = {
  notification: NotificationItem;
  onOpen: (notification: NotificationItem) => void;
  dense?: boolean;
};

/** One notification: kind, the item's title and the time; unread rows carry a text tag, not colour alone. */
export function NotificationRow({ notification, onOpen, dense = false }: NotificationRowProps) {
  const t = useTranslations("notifications");
  const unread = notification.read_at === null;
  return (
    <Link
      href={notification.link}
      onClick={() => onOpen(notification)}
      className={cn(
        "flex min-w-0 flex-col gap-0.5 rounded-control px-3 hover:bg-bg-subtle",
        dense ? "py-2" : "py-3",
      )}
    >
      <span className="flex items-center gap-2 text-sm text-muted">
        <span className={cn(unread && "font-medium text-text")}>
          {t(`kinds.${KIND_KEYS[notification.kind]}`)}
        </span>
        {unread ? <Tag tone="info">{t("unread")}</Tag> : null}
      </span>
      <span className="break-words text-text">{notification.title}</span>
      <time dateTime={notification.created_at} className="text-xs text-muted tabular">
        {formatDateTime(notification.created_at)}
      </time>
    </Link>
  );
}

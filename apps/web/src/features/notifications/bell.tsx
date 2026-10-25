"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { CountBadge } from "@/components/ui/count-badge";
import { Icon } from "@/components/ui/icon";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlay";
import { Skeleton } from "@/components/ui/skeleton";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import { notificationKeys, UNREAD_POLL_MS, type NotificationItem } from "./model";
import { NotificationRow } from "./notification-row";

const LATEST = 8;

/** Top-bar bell (§12.4): unread count, the latest notifications and the way to all of them. */
export function NotificationBell() {
  const t = useTranslations("notifications");
  const api = useApi();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const unread = useQuery({
    queryKey: notificationKeys.unread,
    queryFn: async () => unwrap(await api.GET("/api/v1/me/notifications/unread-count")).count,
    refetchInterval: UNREAD_POLL_MS,
  });
  const latest = useQuery({
    queryKey: notificationKeys.latest,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/me/notifications", { params: { query: { limit: LATEST } } }))
        .items,
    enabled: open,
    staleTime: 0,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: notificationKeys.all });
  const markRead = useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/v1/me/notifications/{notification_id}/read", {
          params: { path: { notification_id: id } },
        }),
      ),
    onSettled: refresh,
  });
  const markAll = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/me/notifications/read-all")),
    onSettled: refresh,
  });

  const count = unread.data ?? 0;
  const openNotification = (notification: NotificationItem) => {
    setOpen(false);
    if (notification.read_at === null) markRead.mutate(notification.id);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="tertiary"
          size="icon"
          className="relative text-text"
          aria-label={t("bell", { count })}
        >
          <Icon icon={Bell} size={20} />
          <CountBadge count={count} className="absolute -top-0.5 -right-0.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(360px,calc(100vw-16px))]" aria-label={t("title")}>
        <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <span className="font-medium">{t("title")}</span>
          {count > 0 ? (
            <Button
              variant="tertiary"
              size="dense"
              loading={markAll.isPending}
              onClick={() => markAll.mutate()}
            >
              {t("markAllRead")}
            </Button>
          ) : null}
        </div>
        <div className="max-h-[60dvh] overflow-y-auto p-1">
          {latest.isPending ? (
            <div className="flex flex-col gap-3 p-3" aria-busy="true">
              {Array.from({ length: 3 }, (_, index) => (
                <div key={index} className="flex flex-col gap-1.5">
                  <Skeleton className="h-3.5 w-24" />
                  <Skeleton className="h-4 w-full" />
                </div>
              ))}
            </div>
          ) : latest.isError ? (
            <div className="flex flex-col items-start gap-2 p-3">
              <p className="text-sm text-muted">{t("loadFailed")}</p>
              <Button size="dense" onClick={() => latest.refetch()}>
                {t("retry")}
              </Button>
            </div>
          ) : latest.data.length === 0 ? (
            <p className="p-3 text-sm text-muted">{t("empty")}</p>
          ) : (
            <ul>
              {latest.data.map((notification) => (
                <li key={notification.id}>
                  <NotificationRow notification={notification} onOpen={openNotification} dense />
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex flex-wrap justify-between gap-2 border-t border-border p-2">
          <Link
            href="/notifications"
            onClick={() => setOpen(false)}
            className="rounded-control px-2 py-1 text-sm text-primary hover:underline"
          >
            {t("viewAll")}
          </Link>
          <Link
            href="/notifications/settings"
            onClick={() => setOpen(false)}
            className="rounded-control px-2 py-1 text-sm text-primary hover:underline"
          >
            {t("openSettings")}
          </Link>
        </div>
      </PopoverContent>
    </Popover>
  );
}

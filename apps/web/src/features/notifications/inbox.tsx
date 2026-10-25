"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BellOff, CheckCheck } from "lucide-react";
import { useTranslations } from "next-intl";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Panel } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { notificationKeys, PAGE_SIZE, type NotificationItem } from "./model";
import { NotificationRow } from "./notification-row";

type Page = components["schemas"]["NotificationPageOut"];

/** All notifications, newest first, with cursor paging ("daha çox yüklə", §12.4). */
export function Inbox({ firstPage }: { firstPage: Page }) {
  const t = useTranslations("notifications");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const queryClient = useQueryClient();

  const pages = useInfiniteQuery({
    queryKey: [...notificationKeys.all, "inbox"],
    queryFn: async ({ pageParam }: { pageParam: string | undefined }) =>
      unwrap(
        await api.GET("/api/v1/me/notifications", {
          params: { query: { limit: PAGE_SIZE, ...(pageParam ? { before: pageParam } : {}) } },
        }),
      ),
    initialPageParam: undefined,
    initialData: { pages: [firstPage], pageParams: [undefined] },
    getNextPageParam: (page) => page.next_before ?? undefined,
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
    onSuccess: () => toast({ title: t("markedAllRead") }),
    onSettled: refresh,
  });

  const items = pages.data.pages.flatMap((page) => page.items);
  const anyUnread = items.some((item) => item.read_at === null);
  const open = (notification: NotificationItem) => {
    if (notification.read_at === null) markRead.mutate(notification.id);
  };

  if (items.length === 0) {
    return (
      <Panel className="px-4">
        <EmptyState icon={BellOff} message={t("empty")} />
      </Panel>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {markAll.isError ? (
        <Banner tone="danger" title={t("loadFailed")}>
          {errorMessage(markAll.error)}
        </Banner>
      ) : null}
      {anyUnread ? (
        <div>
          <Button loading={markAll.isPending} onClick={() => markAll.mutate()}>
            <Icon icon={CheckCheck} />
            {t("markAllRead")}
          </Button>
        </div>
      ) : null}
      <Panel>
        <ul className="divide-y divide-border">
          {items.map((notification) => (
            <li key={notification.id} className="p-1">
              <NotificationRow notification={notification} onOpen={open} />
            </li>
          ))}
        </ul>
      </Panel>
      {pages.isFetchNextPageError ? (
        <Banner tone="danger" title={t("loadFailed")}>
          {errorMessage(pages.error)}
        </Banner>
      ) : null}
      {pages.hasNextPage ? (
        <div>
          <Button loading={pages.isFetchingNextPage} onClick={() => pages.fetchNextPage()}>
            {t("loadMore")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

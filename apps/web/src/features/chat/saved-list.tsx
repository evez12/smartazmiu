"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Banner } from "@/components/ui/banner";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import { formatDateTime } from "@/lib/format";

import { MessageMarkdown } from "./markdown";

const SAVED_KEY = ["chat", "saved"] as const;

/** The reader's own bookmarks (§5.3); unreadable ones show a notice instead of their content. */
export function SavedList({ currentUserId }: { currentUserId: string }) {
  const t = useTranslations("saved");
  const tChat = useTranslations("chat");
  const api = useApi();
  const queryClient = useQueryClient();
  const saved = useQuery({
    queryKey: SAVED_KEY,
    queryFn: async () => unwrap(await api.GET("/api/v1/chat/saved")).items,
  });
  const remove = useMutation({
    mutationFn: async (messageId: string) =>
      unwrap(
        await api.DELETE("/api/v1/chat/messages/{message_id}/saved", {
          params: { path: { message_id: messageId } },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: SAVED_KEY }),
  });
  if (saved.isPending) {
    return (
      <div role="status" className="flex flex-col gap-3">
        <span className="sr-only">{t("title")}</span>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (saved.isError) return <Banner tone="danger" title={t("loadFailed")} />;
  if (saved.data.length === 0) {
    return (
      <Panel className="px-4">
        <EmptyState icon={Bookmark} message={t("empty")} />
      </Panel>
    );
  }
  return (
    <Panel>
      <ul aria-label={t("title")} className="divide-y divide-border">
        {saved.data.map((item) => (
          <li key={item.message_id} className="flex flex-col gap-2 p-4">
            <p className="text-sm text-muted">
              {item.channel_name ? `${item.channel_name} · ` : ""}
              <span className="tabular">
                {t("savedAt", { date: formatDateTime(item.saved_at) })}
              </span>
            </p>
            {item.message ? (
              <>
                <p className="text-sm font-medium">
                  {item.message.is_anonymous
                    ? tChat("anonymous")
                    : (item.message.author?.display_name ?? tChat("deletedUser"))}
                </p>
                <MessageMarkdown
                  body={item.message.body}
                  mentions={item.message.mentions}
                  currentUserId={currentUserId}
                />
              </>
            ) : (
              <p className="text-sm text-muted">{t("unavailable")}</p>
            )}
            <div className="flex flex-wrap gap-2">
              {item.message ? (
                <Link
                  href={`/chat/${item.channel_id}`}
                  className={buttonVariants({ variant: "secondary", size: "dense" })}
                >
                  {t("open")}
                </Link>
              ) : null}
              <Button
                variant="tertiary"
                size="dense"
                loading={remove.isPending && remove.variables === item.message_id}
                onClick={() => remove.mutate(item.message_id)}
              >
                {t("remove")}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

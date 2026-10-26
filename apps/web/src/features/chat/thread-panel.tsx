"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import { Composer } from "./composer";
import { MessageRow, PendingRow, type RowContext } from "./message-row";
import { chatKeys, compareIds, newestId, PAGE_SIZE } from "./model";
import { useChatRuntime, useChatState } from "./runtime";

/**
 * A message's thread in the third pane (§12.7): the root, its replies oldest first and a reply composer. Threads
 * are one level deep, so replies have no reply action of their own (D-067).
 */
export function ThreadPanel({
  rootId,
  context,
  blockedIds,
  onClose,
  framed = true,
}: {
  rootId: string;
  context: RowContext;
  blockedIds: ReadonlySet<string>;
  onClose: () => void;
  /** False inside a sheet, which brings its own title and close button. */
  framed?: boolean;
}) {
  const t = useTranslations("chat");
  const api = useApi();
  const runtime = useChatRuntime();
  const [loadingMore, setLoadingMore] = useState(false);
  const thread = useChatState((state) => state.threads[rootId]);
  const allPending = useChatState((state) => state.pending);

  const initial = useQuery({
    queryKey: chatKeys.thread(rootId),
    queryFn: async () => {
      const page = unwrap(
        await api.GET("/api/v1/chat/messages/{message_id}/thread", {
          params: { path: { message_id: rootId }, query: { limit: PAGE_SIZE } },
        }),
      );
      runtime.store.getState().loadThread(rootId, page, "replace");
      return page.replies.length;
    },
    retry: (count, error) =>
      !(error instanceof ApiRequestError && error.status === 404) && count < 1,
    staleTime: Infinity,
    gcTime: 0,
  });

  const replies = useMemo(
    () => Object.values(thread?.replies ?? {}).sort((a, b) => compareIds(a.id, b.id)),
    [thread?.replies],
  );
  const pending = useMemo(
    () =>
      Object.values(allPending)
        .filter((item) => item.parentId === rootId)
        .sort((a, b) => a.createdAt - b.createdAt),
    [allPending, rootId],
  );

  const loadMore = async () => {
    const after = newestId(replies.map((reply) => reply.id));
    if (!after) return;
    setLoadingMore(true);
    try {
      const page = unwrap(
        await api.GET("/api/v1/chat/messages/{message_id}/thread", {
          params: { path: { message_id: rootId }, query: { after, limit: PAGE_SIZE } },
        }),
      );
      runtime.store.getState().loadThread(rootId, page, "append");
    } finally {
      setLoadingMore(false);
    }
  };

  const rootDeleted = thread?.root.deleted_at != null;
  const rowContext: RowContext = { ...context, onOpenThread: undefined, rootDeleted };

  return (
    <section
      aria-labelledby={framed ? "chat-thread-title" : undefined}
      aria-label={framed ? undefined : t("threadTitle")}
      className="flex min-h-0 flex-1 flex-col"
    >
      {framed ? (
        <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
          <h2 id="chat-thread-title" className="font-semibold">
            {t("threadTitle")}
          </h2>
          <Button variant="tertiary" size="icon" aria-label={t("closeThread")} onClick={onClose}>
            <Icon icon={X} size={20} />
          </Button>
        </header>
      ) : null}
      {initial.isPending && !thread ? (
        <div aria-busy="true" className="flex flex-col gap-4 p-4">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="flex gap-3">
              <Skeleton className="size-8 shrink-0 rounded-full" />
              <SkeletonText lines={2} className="flex-1" />
            </div>
          ))}
        </div>
      ) : initial.isError && !thread ? (
        initial.error instanceof ApiRequestError && initial.error.status === 404 ? (
          <div className="p-4">
            <EmptyState className="py-0" message={t("threadNotFound")} />
          </div>
        ) : (
          <div className="flex flex-col items-start gap-2 p-4">
            <p className="text-sm text-muted">{t("threadFailed")}</p>
            <Button size="dense" onClick={() => void initial.refetch()}>
              {t("retry")}
            </Button>
          </div>
        )
      ) : thread ? (
        <div className="min-h-0 flex-1 overflow-y-auto py-2">
          <MessageRow
            message={thread.root}
            showHeader
            collapsedAsBlocked={
              thread.root.author !== null && blockedIds.has(thread.root.author.id)
            }
            context={{ ...context, onOpenThread: undefined }}
          />
          <div role="separator" className="mx-4 my-2 h-px bg-border" />
          {replies.length === 0 && pending.length === 0 ? (
            <p className="px-4 text-sm text-muted">{t("threadEmpty")}</p>
          ) : null}
          <div role="log" aria-label={t("threadTitle")} aria-live="polite">
            {replies.map((reply) => (
              <MessageRow
                key={reply.id}
                message={reply}
                showHeader
                collapsedAsBlocked={reply.author !== null && blockedIds.has(reply.author.id)}
                context={rowContext}
              />
            ))}
            {pending.map((item) => (
              <PendingRow
                key={item.clientMsgId}
                pending={item}
                showHeader
                author={context.currentUser}
                onRetry={runtime.retry}
              />
            ))}
          </div>
          {thread.hasMore ? (
            <div className="flex justify-center py-2">
              <Button
                size="dense"
                variant="tertiary"
                loading={loadingMore}
                onClick={() => void loadMore()}
              >
                {t("loadMoreReplies")}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
      {thread && !rootDeleted ? (
        <Composer
          label={t("replyPlaceholder")}
          placeholder={t("replyPlaceholder")}
          disabled={!context.canPost}
          members={context.members}
          currentUserId={context.currentUser.id}
          attachTo={thread.root.channel_id}
          onSend={(body, attachmentIds) =>
            runtime.send(thread.root.channel_id, body, rootId, attachmentIds)
          }
          onTyping={() => runtime.typing(thread.root.channel_id)}
        />
      ) : null}
    </section>
  );
}

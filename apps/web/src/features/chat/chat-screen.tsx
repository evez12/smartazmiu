"use client";

import { MessagesSquare } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useMemo } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { Sheet } from "@/components/ui/overlay";
import { cn } from "@/lib/cn";
import { HydrationMark } from "@/lib/hydration-mark";
import { useMediaQuery } from "@/lib/use-media-query";

import { ChannelSidebar } from "./channel-sidebar";
import { MessagePane } from "./message-pane";
import { useChannels, useChatRuntime, useMembers } from "./runtime";
import { ThreadPanel } from "./thread-panel";

const MESSAGE_ID = /^[0-9]{1,19}$/;

/**
 * Three-pane layout (§12.7): channels, messages, and the thread panel (`?thread=<id>`, so a notification can link
 * to it). Below `xl` the thread opens as a sheet; below `lg` one pane shows at a time: the channel list, or the
 * open channel with a way back.
 */
export function ChatScreen({
  channelId,
  currentUserName,
}: {
  channelId?: string;
  currentUserName: string;
}) {
  const t = useTranslations("chat");
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const wide = useMediaQuery("(min-width: 1280px)");
  const requested = params.get("thread");
  const threadId = channelId && requested && MESSAGE_ID.test(requested) ? requested : null;
  const openThread = useCallback(
    (rootId: string) => router.replace(`${pathname}?thread=${rootId}`, { scroll: false }),
    [pathname, router],
  );
  const closeThread = useCallback(
    () => router.replace(pathname, { scroll: false }),
    [pathname, router],
  );
  const details =
    channelId && threadId ? (
      <ThreadDetails
        key={threadId}
        channelId={channelId}
        rootId={threadId}
        currentUserName={currentUserName}
        onClose={closeThread}
        framed={wide}
      />
    ) : null;
  return (
    <div className="flex h-[calc(100dvh-56px-48px-64px-env(safe-area-inset-bottom))] min-h-[420px] overflow-hidden rounded-panel border border-border bg-surface lg:h-[calc(100dvh-56px-64px)]">
      <HydrationMark />
      <aside
        className={cn(
          "flex w-full min-w-0 flex-col border-border lg:w-72 lg:shrink-0 lg:border-r",
          channelId && "max-lg:hidden",
        )}
      >
        <ChannelSidebar activeId={channelId} />
      </aside>
      <div className={cn("flex min-w-0 flex-1 flex-col", !channelId && "max-lg:hidden")}>
        {channelId ? (
          <MessagePane
            key={channelId}
            channelId={channelId}
            currentUserName={currentUserName}
            onOpenThread={openThread}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center p-6">
            <EmptyState icon={MessagesSquare} message={t("chooseChannel")} />
          </div>
        )}
      </div>
      {details && wide ? (
        <aside className="flex w-80 shrink-0 flex-col border-l border-border">{details}</aside>
      ) : null}
      {details && !wide ? (
        <Sheet
          open
          onOpenChange={(open) => !open && closeThread()}
          title={t("threadTitle")}
          side="right"
        >
          <div className="flex h-full flex-col">{details}</div>
        </Sheet>
      ) : null}
    </div>
  );
}

function ThreadDetails({
  channelId,
  rootId,
  currentUserName,
  onClose,
  framed,
}: {
  channelId: string;
  rootId: string;
  currentUserName: string;
  onClose: () => void;
  framed: boolean;
}) {
  const runtime = useChatRuntime();
  const channels = useChannels();
  const members = useMembers(channelId);
  const channel = channels.data?.channels.find((item) => item.id === channelId);
  const blockedIds = useMemo(
    () => new Set(channels.data?.blocked_user_ids ?? []),
    [channels.data?.blocked_user_ids],
  );
  return (
    <ThreadPanel
      rootId={rootId}
      blockedIds={blockedIds}
      onClose={onClose}
      framed={framed}
      context={{
        currentUser: { id: runtime.currentUserId, name: currentUserName },
        canPost: channel?.posting.allowed ?? false,
        members: members.data ?? [],
      }}
    />
  );
}

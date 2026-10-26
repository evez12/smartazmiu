"use client";

import { MessagesSquare } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/cn";
import { HydrationMark } from "@/lib/hydration-mark";

import { ChannelSidebar } from "./channel-sidebar";
import { MessagePane } from "./message-pane";

/**
 * Three-pane layout (§12.7): channels, messages, and a details pane that threads fill in Sprint 6. Below `lg` one
 * pane shows at a time: the channel list, or the open channel with a way back.
 */
export function ChatScreen({
  channelId,
  currentUserName,
  details,
}: {
  channelId?: string;
  currentUserName: string;
  details?: ReactNode;
}) {
  const t = useTranslations("chat");
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
          <MessagePane key={channelId} channelId={channelId} currentUserName={currentUserName} />
        ) : (
          <div className="flex flex-1 items-center justify-center p-6">
            <EmptyState icon={MessagesSquare} message={t("chooseChannel")} />
          </div>
        )}
      </div>
      {details ? (
        <aside className="hidden w-80 shrink-0 flex-col border-l border-border xl:flex">
          {details}
        </aside>
      ) : null}
    </div>
  );
}

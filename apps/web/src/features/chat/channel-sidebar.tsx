"use client";

import { Archive, BellOff, Hash, MessagesSquare, Users } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { CountBadge } from "@/components/ui/count-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

import { badgeCounts, isMuted, sidebarGroups, type Channel } from "./model";
import { PresenceDot, PresenceIndicator } from "./presence-dot";
import { useChannels, useChatState } from "./runtime";

/** Channel list grouped as Fənlər / Fənn icmaları / Qrup / Şəxsi with unread badges (§12.7). */
export function ChannelSidebar({ activeId }: { activeId?: string }) {
  const t = useTranslations("chat");
  const channels = useChannels();
  const status = useChatState((state) => state.status);

  return (
    <nav aria-label={t("channelsLabel")} className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
        <h1 className="text-lg font-semibold">{t("title")}</h1>
      </div>
      {status !== "online" ? (
        <p role="status" className="border-b border-border px-4 py-2 text-sm text-muted">
          {t(`connection.${status}`)}
        </p>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {channels.isPending ? (
          <div aria-busy="true" className="flex flex-col gap-2 p-2">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-9 w-full" />
            ))}
          </div>
        ) : channels.isError ? (
          <div className="flex flex-col items-start gap-2 p-2">
            <p className="text-sm text-muted">{t("channelsFailed")}</p>
            <Button size="dense" onClick={() => channels.refetch()}>
              {t("retry")}
            </Button>
          </div>
        ) : channels.data.channels.length === 0 ? (
          <EmptyState className="px-2" icon={MessagesSquare} message={t("noChannels")} />
        ) : (
          <div className="flex flex-col gap-4">
            {sidebarGroups(channels.data.channels).map((group) => (
              <section key={group.key} aria-labelledby={`chat-group-${group.key}`}>
                <h2
                  id={`chat-group-${group.key}`}
                  className="px-2 pb-1 text-xs font-medium text-muted"
                >
                  {t(`groups.${group.key}`)}
                </h2>
                <ul className="flex flex-col gap-0.5">
                  {group.open.map((channel) => (
                    <li key={channel.id}>
                      <ChannelLink channel={channel} active={channel.id === activeId} />
                    </li>
                  ))}
                </ul>
                {group.archived.length ? (
                  <details className="mt-1" open={group.archived.some((c) => c.id === activeId)}>
                    <summary className="flex h-9 cursor-pointer items-center gap-2 rounded-control px-2 text-sm text-muted hover:bg-bg-subtle">
                      <Icon icon={Archive} />
                      {t("archived", { count: group.archived.length })}
                    </summary>
                    <ul className="flex flex-col gap-0.5">
                      {group.archived.map((channel) => (
                        <li key={channel.id}>
                          <ChannelLink channel={channel} active={channel.id === activeId} />
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
              </section>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}

/** One sidebar entry; `presence` is for static previews, otherwise a DM's dot follows the live state. */
export function ChannelLink({
  channel,
  active,
  presence,
}: {
  channel: Channel;
  active: boolean;
  presence?: "online" | "offline";
}) {
  // Fixed for the render; the list re-renders whenever the channel list changes.
  const [now] = useState(() => Date.now());
  const counts = badgeCounts(channel, now);
  const muted = isMuted(channel, now);
  const unread = counts.unread > 0 || counts.mentions > 0;
  return (
    <Link
      href={`/chat/${channel.id}`}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex min-h-11 items-center gap-2 rounded-control px-2 py-1 text-text hover:bg-bg-subtle lg:min-h-9",
        active && "bg-bg-subtle font-medium",
      )}
    >
      {channel.peer ? (
        <span className="relative shrink-0">
          <Avatar
            name={channel.peer.display_name}
            src={channel.peer.photo_url ?? undefined}
            size={24}
            decorative
          />
          {presence ? (
            <PresenceIndicator status={presence} className="absolute -right-0.5 -bottom-0.5" />
          ) : (
            <PresenceDot userId={channel.peer.id} className="absolute -right-0.5 -bottom-0.5" />
          )}
        </span>
      ) : (
        <Icon
          icon={channel.type === "academic_group" || channel.type === "faculty" ? Users : Hash}
          className="shrink-0 text-muted"
        />
      )}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className={cn("truncate", unread && "font-semibold")} title={channel.name}>
          {channel.name}
        </span>
        {channel.context ? (
          <span className="truncate text-xs text-muted tabular">{channel.context}</span>
        ) : null}
      </span>
      {muted ? <MutedMark /> : null}
      <CountBadge count={counts.mentions} kind="mention" />
      <CountBadge count={counts.unread} />
    </Link>
  );
}

/** Muted channels show no counts; the icon says so with a text alternative (§12.7). */
function MutedMark() {
  const t = useTranslations("chat.notify");
  return (
    <span className="shrink-0 text-muted">
      <Icon icon={BellOff} />
      <span className="sr-only">{t("muted")}</span>
    </span>
  );
}

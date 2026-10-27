"use client";

import { useQuery } from "@tanstack/react-query";
import { Pin } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Sheet } from "@/components/ui/overlay";
import { Skeleton } from "@/components/ui/skeleton";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import { formatDateTime } from "@/lib/format";

import { MessageMarkdown } from "./markdown";

/** The channel's "Faydalı" collection: pinned messages, newest pin first (§5.3). */
export function UsefulButton({
  channelId,
  currentUserId,
}: {
  channelId: string;
  currentUserId: string;
}) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="tertiary" size="dense" onClick={() => setOpen(true)}>
        <Icon icon={Pin} />
        <span className="max-sm:sr-only">{t("useful")}</span>
      </Button>
      {open ? (
        <UsefulSheet channelId={channelId} currentUserId={currentUserId} onOpenChange={setOpen} />
      ) : null}
    </>
  );
}

function UsefulSheet({
  channelId,
  currentUserId,
  onOpenChange,
}: {
  channelId: string;
  currentUserId: string;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("chat");
  const api = useApi();
  const pins = useQuery({
    queryKey: ["chat", "pins", channelId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/chat/channels/{channel_id}/pins", {
          params: { path: { channel_id: channelId } },
        }),
      ).messages,
  });
  return (
    <Sheet open onOpenChange={onOpenChange} title={t("usefulTitle")} side="right">
      {pins.isPending ? (
        <div className="flex flex-col gap-3 p-4" role="status">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : pins.isError ? (
        <p className="p-4 text-sm text-muted">{t("usefulFailed")}</p>
      ) : pins.data.length === 0 ? (
        <div className="px-4">
          <EmptyState icon={Pin} message={t("usefulEmpty")} />
        </div>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {pins.data.map((message) => (
            <li key={message.id} className="flex flex-col gap-1 p-4">
              <span className="text-sm text-muted">
                {message.is_anonymous
                  ? t("anonymous")
                  : (message.author?.display_name ?? t("deletedUser"))}{" "}
                · <span className="tabular">{formatDateTime(message.created_at)}</span>
              </span>
              <MessageMarkdown
                body={message.body}
                mentions={message.mentions}
                currentUserId={currentUserId}
              />
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

"use client";

import { CircleAlert, Clock } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/cn";
import { formatDate, formatDateTime, formatTime } from "@/lib/format";

import type { ChatMessage, PendingMessage, TimelineItem } from "./model";
import { useRefusalText } from "./posting";

type RowProps = {
  item: TimelineItem;
  currentUser: { id: string; name: string };
  blockedIds: ReadonlySet<string>;
  onRetry: (clientMsgId: string) => void;
};

/** One row of the message list: left-aligned, no bubbles (§12.7). */
export function TimelineRow({ item, currentUser, blockedIds, onRetry }: RowProps) {
  const t = useTranslations("chat");
  if (item.kind === "day") {
    return (
      <div role="separator" className="flex items-center gap-3 px-4 py-2 text-xs text-muted">
        <span className="h-px flex-1 bg-border" />
        <span className="tabular">{formatDate(`${item.day}T12:00:00+04:00`)}</span>
        <span className="h-px flex-1 bg-border" />
      </div>
    );
  }
  if (item.kind === "unread") {
    return (
      <div
        role="separator"
        className="flex items-center gap-3 px-4 py-2 text-xs font-medium text-primary"
      >
        <span className="h-px flex-1 bg-primary" />
        <span>{t("newMessages")}</span>
        <span className="h-px flex-1 bg-primary" />
      </div>
    );
  }
  if (item.kind === "pending") {
    return (
      <PendingRow
        pending={item.pending}
        showHeader={item.showHeader}
        author={currentUser}
        onRetry={onRetry}
      />
    );
  }
  return (
    <MessageRow
      message={item.message}
      showHeader={item.showHeader}
      collapsedAsBlocked={item.message.author !== null && blockedIds.has(item.message.author.id)}
    />
  );
}

function MessageRow({
  message,
  showHeader,
  collapsedAsBlocked,
}: {
  message: ChatMessage;
  showHeader: boolean;
  collapsedAsBlocked: boolean;
}) {
  const t = useTranslations("chat");
  const [revealed, setRevealed] = useState(false);
  const name = message.author?.display_name ?? t("deletedUser");
  const time = formatTime(message.created_at);
  return (
    <article
      aria-label={`${name}, ${time}`}
      className={cn(
        "group flex gap-3 px-4 hover:bg-bg-subtle",
        showHeader ? "pt-2 pb-0.5" : "py-0.5",
      )}
    >
      <div className="w-8 shrink-0">
        {showHeader ? (
          <Avatar name={name} src={message.author?.photo_url ?? undefined} size={32} decorative />
        ) : null}
      </div>
      <div className="min-w-0 flex-1">
        {showHeader ? (
          <header className="flex flex-wrap items-baseline gap-x-2">
            <span className={cn("font-medium", !message.author && "text-muted")}>{name}</span>
            {message.author?.badge ? (
              <Tag tone="info">{t(`badges.${message.author.badge}`)}</Tag>
            ) : null}
            <time
              dateTime={message.created_at}
              title={formatDateTime(message.created_at)}
              className="text-xs text-muted tabular"
            >
              {time}
            </time>
          </header>
        ) : (
          <time dateTime={message.created_at} className="sr-only">
            {time}
          </time>
        )}
        {collapsedAsBlocked && !revealed ? (
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
            {t("blockedMessage")}
            <Button variant="tertiary" size="dense" onClick={() => setRevealed(true)}>
              {t("showMessage")}
            </Button>
          </p>
        ) : (
          // Plain text until Markdown arrives (Sprint 6): React escapes it, line breaks are kept.
          <p className="break-words whitespace-pre-wrap">{message.body}</p>
        )}
      </div>
    </article>
  );
}

function PendingRow({
  pending,
  showHeader,
  author,
  onRetry,
}: {
  pending: PendingMessage;
  showHeader: boolean;
  author: { id: string; name: string };
  onRetry: (clientMsgId: string) => void;
}) {
  const t = useTranslations("chat");
  const refusal = useRefusalText();
  const failed = pending.state === "failed";
  return (
    <article
      aria-label={`${t("you")}, ${failed ? t("failed") : t("sending")}`}
      className={cn("flex gap-3 px-4", showHeader ? "pt-2 pb-0.5" : "py-0.5")}
    >
      <div className="w-8 shrink-0">
        {showHeader ? <Avatar name={author.name} size={32} decorative /> : null}
      </div>
      <div className="min-w-0 flex-1">
        {showHeader ? (
          <header className="flex items-baseline gap-2">
            <span className="font-medium">{author.name}</span>
          </header>
        ) : null}
        <p className={cn("break-words whitespace-pre-wrap", !failed && "text-muted")}>
          {pending.body}
        </p>
        <p
          className={cn(
            "mt-0.5 flex items-start gap-1 text-xs",
            failed ? "text-danger" : "text-muted",
          )}
          role={failed ? "alert" : undefined}
        >
          <Icon icon={failed ? CircleAlert : Clock} className="mt-px size-3.5 shrink-0" />
          <span>
            {failed
              ? `${t("failed")}. ${refusal(pending.error, pending.errorDetail)}`
              : pending.state === "queued"
                ? t("queued")
                : t("sending")}
          </span>
        </p>
        {failed ? (
          <Button
            variant="tertiary"
            size="dense"
            className="-ml-3"
            onClick={() => onRetry(pending.clientMsgId)}
          >
            {t("resend")}
          </Button>
        ) : null}
      </div>
    </article>
  );
}

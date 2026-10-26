"use client";

import { CircleAlert, Clock, MessagesSquare } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { ApiRequestError } from "@/lib/api/browser";
import { cn } from "@/lib/cn";
import { formatDate, formatDateTime, formatTime } from "@/lib/format";

import { Composer } from "./composer";
import { MessageToolbar, ReactionChips } from "./message-actions";
import { MessageAttachments } from "./message-attachments";
import { MessageBody } from "./message-body";
import {
  canChange,
  CHANGE_ERROR_KEYS,
  decodeMentions,
  type Author,
  type ChatMessage,
  type PendingMessage,
  type TimelineItem,
} from "./model";
import { useRefusalText } from "./posting";
import { useOptionalChatRuntime } from "./runtime";

type RowProps = {
  item: TimelineItem;
  context: RowContext;
  blockedIds: ReadonlySet<string>;
  onRetry: (clientMsgId: string) => void;
};

/** One row of the message list: left-aligned, no bubbles (§12.7). */
export function TimelineRow({ item, context, blockedIds, onRetry }: RowProps) {
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
        author={context.currentUser}
        onRetry={onRetry}
      />
    );
  }
  return (
    <MessageRow
      message={item.message}
      showHeader={item.showHeader}
      collapsedAsBlocked={item.message.author !== null && blockedIds.has(item.message.author.id)}
      context={context}
    />
  );
}

export type RowContext = {
  currentUser: { id: string; name: string };
  /** The channel's posting decision allows writing (ADR 0004); edits and reactions follow it. */
  canPost: boolean;
  members: Author[];
  /** Opens the thread panel; absent inside the panel, where threads are one level deep. */
  onOpenThread?: (rootId: string) => void;
  /** Inside a thread whose root was deleted: replies carry the placeholder (§13.2). */
  rootDeleted?: boolean;
};

export function MessageRow({
  message,
  showHeader,
  collapsedAsBlocked,
  context,
}: {
  message: ChatMessage;
  showHeader: boolean;
  collapsedAsBlocked: boolean;
  context: RowContext;
}) {
  const t = useTranslations("chat");
  const runtime = useOptionalChatRuntime();
  const toast = useToast();
  const refusal = useChangeErrorText();
  const [revealed, setRevealed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // Checked when the menu renders; the server has the final word on the 15-minute window (§13.2).
  const [now, setNow] = useState(() => Date.now());
  const name = message.author?.display_name ?? t("deletedUser");
  const time = formatTime(message.created_at);
  const deleted = message.deleted_at !== null;
  const own = canChange(message, context.currentUser.id, now);
  const canReact = context.canPost && !deleted && runtime !== null;

  const fail = (error: unknown) =>
    toast({ title: t("changeFailed"), description: refusal(error), tone: "danger" });
  const react = (emoji: string, add: boolean) => {
    runtime?.react(message.id, emoji, add).catch(fail);
  };
  const remove = async () => {
    if (!runtime) return;
    setDeleting(true);
    try {
      await runtime.remove(message.id);
      setConfirming(false);
      toast({ title: t("deleted") });
    } catch (error) {
      fail(error);
    } finally {
      setDeleting(false);
    }
  };
  const editable = decodeMentions(message.body, message.mentions);

  return (
    <article
      aria-label={`${name}, ${time}`}
      onPointerEnter={() => setNow(Date.now())}
      onFocus={() => setNow(Date.now())}
      className={cn(
        "group relative flex gap-3 px-4 focus-within:bg-bg-subtle hover:bg-bg-subtle",
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
        {context.rootDeleted ? <p className="text-xs text-muted">{t("deletedParent")}</p> : null}
        {deleted ? (
          <p className="text-sm text-muted italic">{t("deletedMessage")}</p>
        ) : collapsedAsBlocked && !revealed ? (
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
            {t("blockedMessage")}
            <Button variant="tertiary" size="dense" onClick={() => setRevealed(true)}>
              {t("showMessage")}
            </Button>
          </p>
        ) : editing ? (
          <div className="py-1">
            <Composer
              label={t("editLabel")}
              disabled={false}
              members={context.members}
              currentUserId={context.currentUser.id}
              initialText={editable.text}
              initialPicked={editable.picked}
              onCancel={() => setEditing(false)}
              onSend={(body) => {
                runtime
                  ?.edit(message.id, body)
                  .then((notices) => {
                    setEditing(false);
                    runtime?.store.getState().setNotices(message.channel_id, notices);
                  })
                  .catch(fail);
              }}
            />
          </div>
        ) : (
          <>
            <MessageBody
              message={message}
              currentUserId={context.currentUser.id}
              suffix={
                message.edited_at ? (
                  <span
                    className="ml-1 text-xs text-muted"
                    title={t("editedAt", { time: formatDateTime(message.edited_at) })}
                  >
                    ({t("edited")})
                  </span>
                ) : null
              }
            />
            {message.is_verified_answer ? (
              <Tag tone="success" className="ml-2">
                {t("verified")}
              </Tag>
            ) : null}
          </>
        )}
        {!deleted && !(collapsedAsBlocked && !revealed) ? (
          <MessageAttachments attachments={message.attachments} />
        ) : null}
        {!deleted ? (
          <ReactionChips message={message} disabled={!canReact} onToggle={react} />
        ) : null}
        {context.onOpenThread && message.reply_count > 0 ? (
          <Button
            variant="tertiary"
            size="dense"
            className="-ml-3"
            onClick={() => context.onOpenThread!(message.id)}
          >
            <Icon icon={MessagesSquare} />
            {t("replies", { count: message.reply_count })}
          </Button>
        ) : null}
      </div>
      {!editing && !deleted ? (
        <MessageToolbar
          message={message}
          handlers={{
            canReact,
            onReact: react,
            onReply:
              context.onOpenThread && context.canPost
                ? () => context.onOpenThread!(message.id)
                : undefined,
            onEdit: own && context.canPost && runtime ? () => setEditing(true) : undefined,
            onDelete: own && runtime ? () => setConfirming(true) : undefined,
          }}
        />
      ) : null}
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("deleteTitle")}
        consequence={t("deleteConsequence")}
        confirmLabel={t("delete")}
        destructive
        pending={deleting}
        onConfirm={() => void remove()}
      />
    </article>
  );
}

/** Plain-language text for a refused edit, delete or reaction. */
function useChangeErrorText(): (error: unknown) => string {
  const reasons = useTranslations("chat.reasons");
  const refusal = useRefusalText();
  return (error) => {
    if (!(error instanceof ApiRequestError)) return reasons("generic");
    const key = CHANGE_ERROR_KEYS[error.code];
    if (key) return reasons(key as Parameters<typeof reasons>[0]);
    return refusal(error.code, error.details as { until?: string | null });
  };
}

export function PendingRow({
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

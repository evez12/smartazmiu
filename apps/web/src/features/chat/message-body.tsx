"use client";

import { useTranslations } from "next-intl";
import { useMemo, type ReactNode } from "react";

import { cn } from "@/lib/cn";

import { splitMentions, type ChatMessage } from "./model";

/** Message text with mentions shown as names; React escapes everything else (§14). */
export function MessageBody({
  message,
  currentUserId,
  className,
  suffix,
}: {
  message: Pick<ChatMessage, "body" | "mentions">;
  currentUserId: string;
  className?: string;
  /** Inline after the text, e.g. the "redaktə olunub" label. */
  suffix?: ReactNode;
}) {
  const t = useTranslations("chat");
  const parts = useMemo(
    () => splitMentions(message.body, message.mentions),
    [message.body, message.mentions],
  );
  return (
    <p className={cn("break-words whitespace-pre-wrap", className)}>
      {parts.map((part, index) =>
        part.kind === "text" ? (
          part.text
        ) : part.name === null ? (
          // Not a member of the channel: plain text without a name (§13.2).
          <span key={index}>{t("mentionUnknown")}</span>
        ) : (
          <span
            key={index}
            className={cn(
              "rounded-control px-0.5 font-medium text-primary",
              part.id === currentUserId && "bg-bg-subtle",
            )}
          >
            @{part.name}
          </span>
        ),
      )}
      {suffix}
    </p>
  );
}

"use client";

import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";

import { useChatState } from "./runtime";

/**
 * Small presence dot with a text alternative (§12.7). Online is filled, offline an empty ring, so the state
 * does not depend on colour alone.
 */
export function PresenceDot({ userId, className }: { userId: string; className?: string }) {
  const status = useChatState((state) => state.presence[userId] ?? "offline");
  return <PresenceIndicator status={status} className={className} />;
}

export function PresenceIndicator({
  status,
  className,
}: {
  status: "online" | "offline";
  className?: string;
}) {
  const t = useTranslations("chat.presence");
  return (
    <span className={cn("inline-flex items-center", className)}>
      <span
        aria-hidden="true"
        className={cn(
          "size-2.5 rounded-full border-2",
          status === "online" ? "border-success bg-success" : "border-border-control bg-surface",
        )}
      />
      <span className="sr-only">{t(status)}</span>
    </span>
  );
}

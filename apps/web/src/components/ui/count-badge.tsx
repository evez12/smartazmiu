import { AtSign } from "lucide-react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";

type CountBadgeProps = {
  count: number;
  /** Mentions use a distinct style and icon so they differ from plain unread counts without colour (§12.7). */
  kind?: "unread" | "mention";
  className?: string;
};

export const COUNT_BADGE_MAX = 99;

export function CountBadge({ count, kind = "unread", className }: CountBadgeProps) {
  const t = useTranslations("ui");
  if (count <= 0) return null;
  const shown = count > COUNT_BADGE_MAX ? `${COUNT_BADGE_MAX}+` : String(count);
  return (
    <span
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-control px-1 text-xs font-semibold tabular",
        kind === "mention" ? "bg-accent text-primary-contrast" : "bg-primary text-primary-contrast",
        className,
      )}
    >
      {kind === "mention" ? <Icon icon={AtSign} className="size-3" /> : null}
      <span aria-hidden="true">{shown}</span>
      <span className="sr-only">
        {kind === "mention" ? t("mentionCount", { count }) : t("unreadCount", { count })}
      </span>
    </span>
  );
}

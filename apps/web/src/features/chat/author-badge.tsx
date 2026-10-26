"use client";

import { Compass } from "lucide-react";
import { useTranslations } from "next-intl";

import { Tag } from "@/components/ui/tag";
import type { components } from "@/lib/api/schema";

type Author = Pick<components["schemas"]["AuthorOut"], "badge" | "guide_semester">;

/** The text of a person's role in the channel: teacher, curator or "Bələdçi · 2025 Payız" (§5.2, §12.7). */
export function useBadgeLabel(): (author: Author) => string | undefined {
  const t = useTranslations("chat.badges");
  return (author) => {
    if (author.badge === "guide") return t("guide", { semester: author.guide_semester ?? "" });
    return author.badge ? t(author.badge) : undefined;
  };
}

/** Teacher and curator in the info tone; guides in the accent tone with a compass, never an emoji (§12). */
export function AuthorBadge({ author }: { author: Author }) {
  const label = useBadgeLabel()(author);
  if (!label) return null;
  return author.badge === "guide" ? (
    <Tag tone="accent" icon={Compass}>
      {label}
    </Tag>
  ) : (
    <Tag tone="info">{label}</Tag>
  );
}

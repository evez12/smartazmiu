import Link from "next/link";
import { useTranslations } from "next-intl";

import { AudienceLabel } from "@/features/audiences/audience-label";
import { formatDateTime } from "@/lib/format";

import type { Announcement } from "./model";

/** Newest first: title, audience and publication time; the full text is on the announcement's page. */
export function AnnouncementList({
  items,
  compact = false,
}: {
  items: Announcement[];
  compact?: boolean;
}) {
  const t = useTranslations("announcements");
  return (
    <ul className="divide-y divide-border">
      {items.map((item) => (
        <li key={item.id} className={compact ? "py-3 first:pt-0 last:pb-0" : "p-4"}>
          <article className="flex min-w-0 flex-col gap-1">
            <h3 className="font-medium break-words">
              <Link href={`/announcements/${item.id}`} className="text-primary hover:underline">
                {item.title}
              </Link>
            </h3>
            {compact ? null : (
              <p className="line-clamp-2 max-w-[75ch] break-words text-muted">{item.body}</p>
            )}
            <p className="text-sm text-muted">
              <time dateTime={item.published_at} className="tabular">
                {formatDateTime(item.published_at)}
              </time>
              <span aria-hidden="true"> · </span>
              <span className="sr-only">{t("audience")}: </span>
              <AudienceLabel audience={item.audience} />
            </p>
          </article>
        </li>
      ))}
    </ul>
  );
}

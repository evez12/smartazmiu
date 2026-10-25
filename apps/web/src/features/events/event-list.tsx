import Link from "next/link";
import { useTranslations } from "next-intl";

import { formatDateTimeRange } from "@/lib/format";

import { EventTags } from "./event-facts";
import type { EventItem } from "./model";

export function EventList({ items }: { items: EventItem[] }) {
  const t = useTranslations("events");
  return (
    <ul className="divide-y divide-border">
      {items.map((event) => (
        <li key={event.id} className="p-4">
          <article className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-medium break-words">
                <Link href={`/events/${event.id}`} className="text-primary hover:underline">
                  {event.title}
                </Link>
              </h3>
              <EventTags event={event} />
            </div>
            <p className="text-sm text-muted tabular">
              {formatDateTimeRange(event.starts_at, event.ends_at)}
              <span aria-hidden="true"> · </span>
              <span className="sr-only">{t("where")}: </span>
              {event.room ? t("room", { code: event.room.code }) : event.location}
            </p>
          </article>
        </li>
      ))}
    </ul>
  );
}

import { MapPin } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Icon } from "@/components/ui/icon";
import { Tag } from "@/components/ui/tag";
import { AudienceLabel } from "@/features/audiences/audience-label";
import { formatDateTimeRange } from "@/lib/format";

import { hasEnded, type EventItem } from "./model";

/** Time (with the zone, §13.4), place with a map link, places left and audience. */
export function EventFacts({ event }: { event: EventItem }) {
  const t = useTranslations("events");
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      <div className="flex flex-col">
        <dt className="text-sm text-muted">{t("when")}</dt>
        <dd className="tabular">
          {formatDateTimeRange(event.starts_at, event.ends_at)}{" "}
          <span className="text-sm text-muted">({t("bakuTime")})</span>
        </dd>
      </div>
      <div className="flex flex-col">
        <dt className="text-sm text-muted">{t("where")}</dt>
        <dd className="flex flex-col break-words">
          {event.room ? (
            <Link
              href={`/map?room=${encodeURIComponent(event.room.code)}`}
              aria-label={t("showOnMap", { code: event.room.code })}
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              <Icon icon={MapPin} />
              {t("room", { code: event.room.code })}
              {event.room.name ? ` · ${event.room.name}` : ""}
            </Link>
          ) : null}
          {event.location ? <span>{event.location}</span> : null}
        </dd>
      </div>
      <div className="flex flex-col">
        <dt className="text-sm text-muted">{t("places")}</dt>
        <dd className="tabular">
          {event.capacity === null
            ? `${t("unlimited")} · ${t("going", { count: event.going })}`
            : t("spots", {
                left: event.spots_left ?? 0,
                going: event.going,
                capacity: event.capacity,
              })}
        </dd>
      </div>
      <div className="flex flex-col">
        <dt className="text-sm text-muted">{t("audience")}</dt>
        <dd>
          <AudienceLabel audience={event.audience} />
        </dd>
      </div>
    </dl>
  );
}

/** Text tags for the states that matter at a glance; colour is never the only signal (§12.2). */
export function EventTags({ event }: { event: EventItem }) {
  const t = useTranslations("events.status");
  const mine = event.my_registration;
  const tags: { tone: "danger" | "success" | "info" | "neutral"; label: string }[] = [];
  if (event.status === "cancelled") tags.push({ tone: "danger", label: t("cancelled") });
  else if (hasEnded(event)) tags.push({ tone: "neutral", label: t("ended") });
  if (mine?.checked_in_at) tags.push({ tone: "success", label: t("checkedIn") });
  else if (mine?.status === "going") tags.push({ tone: "info", label: t("going") });
  if (event.status === "published" && event.spots_left === 0 && mine?.status !== "going") {
    tags.push({ tone: "neutral", label: t("full") });
  }
  if (tags.length === 0) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Tag key={tag.label} tone={tag.tone}>
          {tag.label}
        </Tag>
      ))}
    </span>
  );
}

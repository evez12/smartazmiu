import { MapPin } from "lucide-react";
import { useTranslations } from "next-intl";

import { Icon } from "@/components/ui/icon";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { cn } from "@/lib/cn";
import { formatWeekdayDate } from "@/lib/format";

import { mapHref, type ClassItem } from "./model";

const STATUS_TONE = {
  cancelled: "danger",
  changed: "warning",
  moved_away: "warning",
  moved_here: "info",
} as const;

function ChangeDetails({ item }: { item: ClassItem }) {
  const t = useTranslations("schedule");
  const lines: string[] = [];
  if (item.moved_to) {
    lines.push(
      t("movedTo", { date: formatWeekdayDate(item.moved_to.date), time: item.moved_to.starts_at }),
    );
  }
  if (item.status === "moved_here") {
    lines.push(
      t("movedFrom", {
        date: formatWeekdayDate(item.original_date),
        time: item.original_starts_at,
      }),
    );
  }
  if (item.room_changed) lines.push(t("roomChanged"));
  if (item.teacher_changed) lines.push(t("teacherChanged"));
  if (item.note) lines.push(item.note);
  if (lines.length === 0) return null;
  return <p className="text-sm text-text">{lines.join(" ")}</p>;
}

function ClassRow({ item }: { item: ClassItem }) {
  const t = useTranslations("schedule");
  const inactive = item.status === "cancelled" || item.status === "moved_away";
  return (
    <li className="flex gap-4 border-b border-border py-3 last:border-b-0">
      <p className="w-24 shrink-0 text-sm text-text tabular">
        {t("time", { start: item.starts_at, end: item.ends_at })}
      </p>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("font-medium break-words", inactive && "text-muted line-through")}>
            {item.subject.name}
          </span>
          <Tag>{t(`classTypes.${item.class_type}`)}</Tag>
          {item.status !== "scheduled" ? (
            <Tag tone={STATUS_TONE[item.status]}>{t(`statuses.${item.status}`)}</Tag>
          ) : null}
        </div>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          {item.room ? (
            <TextLink
              href={mapHref(item.room.code)}
              aria-label={t("showOnMap", { room: item.room.code })}
              className="inline-flex items-center gap-1"
            >
              <Icon icon={MapPin} />
              <span className="tabular">{item.room.code}</span>
            </TextLink>
          ) : (
            <span>{t("noRoom")}</span>
          )}
          {item.room ? <span>{item.room.building}</span> : null}
          {item.teachers.length ? <span>{item.teachers.join(", ")}</span> : null}
          <span>{item.groups.join(", ")}</span>
        </p>
        <ChangeDetails item={item} />
      </div>
    </li>
  );
}

/** Classes of one day in time order; changes are marked with a text tag, never by colour alone. */
export function ClassList({ classes }: { classes: ClassItem[] }) {
  return (
    <ul className="flex flex-col">
      {classes.map((item) => (
        <ClassRow key={`${item.id}:${item.date}`} item={item} />
      ))}
    </ul>
  );
}

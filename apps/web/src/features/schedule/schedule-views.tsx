import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { cn } from "@/lib/cn";
import { formatDayMonth, formatWeekdayDate } from "@/lib/format";

import { ClassList } from "./class-list";
import {
  addDays,
  scheduleHref,
  visibleDays,
  type Schedule,
  type ScheduleDay,
  type ScheduleView,
} from "./model";

function useParityLabel() {
  const t = useTranslations("schedule");
  return (parity: ScheduleDay["parity"]) => t(`parity.${parity ?? "none"}`);
}

/** View switch and previous/next navigation; plain links, so the browser history works as expected. */
export function ScheduleToolbar({
  view,
  day,
  today,
}: {
  view: ScheduleView;
  day: string;
  today: string;
}) {
  const t = useTranslations("schedule");
  const step = view === "week" ? 7 : 1;
  const linkClass = buttonVariants({ variant: "secondary", size: "dense" });
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
      <nav aria-label={t("views.label")} className="flex gap-2">
        {(["week", "day"] as const).map((option) => (
          <Link
            key={option}
            href={scheduleHref(option, day)}
            aria-current={option === view ? "page" : undefined}
            className={cn(linkClass, option === view && "border-primary bg-bg-subtle")}
          >
            {t(`views.${option}`)}
          </Link>
        ))}
      </nav>
      <nav aria-label={t("navigation")} className="flex flex-wrap items-center gap-2">
        <Link
          href={scheduleHref(view, addDays(day, -step))}
          className={buttonVariants({ variant: "secondary", size: "icon-dense" })}
          aria-label={view === "week" ? t("previousWeek") : t("previousDay")}
        >
          <Icon icon={ChevronLeft} />
        </Link>
        <Link href={scheduleHref(view, today)} className={linkClass}>
          {view === "week" ? t("thisWeek") : t("today")}
        </Link>
        <Link
          href={scheduleHref(view, addDays(day, step))}
          className={buttonVariants({ variant: "secondary", size: "icon-dense" })}
          aria-label={view === "week" ? t("nextWeek") : t("nextDay")}
        >
          <Icon icon={ChevronRight} />
        </Link>
      </nav>
    </div>
  );
}

function DayPanel({ day, today }: { day: ScheduleDay; today: string }) {
  const t = useTranslations("schedule");
  const isToday = day.date === today;
  return (
    <Panel aria-current={isToday ? "date" : undefined}>
      <PanelHeader
        headingLevel={3}
        title={formatWeekdayDate(day.date)}
        action={isToday ? <Tag tone="info">{t("today")}</Tag> : undefined}
      />
      <div className="px-4">
        {day.classes.length ? (
          <ClassList classes={day.classes} />
        ) : (
          <p className="py-3 text-sm text-muted">{t("noClasses")}</p>
        )}
      </div>
    </Panel>
  );
}

export function WeekView({ schedule }: { schedule: Schedule }) {
  const t = useTranslations("schedule");
  const parityLabel = useParityLabel();
  const days = visibleDays(schedule.days);
  const empty = schedule.days.every((day) => day.classes.length === 0);
  return (
    <section aria-labelledby="schedule-week" className="flex flex-col gap-4">
      <h2 id="schedule-week" className="text-lg font-semibold">
        {t("weekRange", {
          start: formatDayMonth(schedule.start),
          end: formatDayMonth(schedule.end),
        })}
        <span className="font-normal text-muted"> · {parityLabel(schedule.days[0]!.parity)}</span>
      </h2>
      {empty ? (
        <Panel>
          <PanelBody>
            <EmptyState
              className="py-0"
              icon={CalendarDays}
              message={t("noClassesWeek")}
              action={
                <TextLink href={scheduleHref("week", addDays(schedule.start, 7))}>
                  {t("goToNextWeek")}
                </TextLink>
              }
            />
          </PanelBody>
        </Panel>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {days.map((day) => (
            <DayPanel key={day.date} day={day} today={schedule.today} />
          ))}
        </div>
      )}
    </section>
  );
}

export function DayView({ schedule }: { schedule: Schedule }) {
  const t = useTranslations("schedule");
  const parityLabel = useParityLabel();
  const day = schedule.days[0]!;
  return (
    <Panel>
      <PanelHeader
        title={formatWeekdayDate(day.date)}
        description={parityLabel(day.parity)}
        action={day.date === schedule.today ? <Tag tone="info">{t("today")}</Tag> : undefined}
      />
      <div className="px-4">
        {day.classes.length ? (
          <ClassList classes={day.classes} />
        ) : (
          <EmptyState icon={CalendarDays} message={t("noClassesDay")} />
        )}
      </div>
    </Panel>
  );
}

/** Dashboard widget: today's classes with links to the rooms on the map. */
export function TodayClasses({ schedule }: { schedule: Schedule }) {
  const t = useTranslations("schedule");
  const parityLabel = useParityLabel();
  const day = schedule.days[0]!;
  return (
    <Panel aria-labelledby="today-classes">
      <PanelHeader
        titleId="today-classes"
        title={t("todayTitle")}
        description={`${formatWeekdayDate(day.date)} · ${parityLabel(day.parity)}`}
        action={<TextLink href={scheduleHref("week", day.date)}>{t("openWeek")}</TextLink>}
      />
      <div className="px-4">
        {day.classes.length ? (
          <ClassList classes={day.classes} />
        ) : (
          <EmptyState icon={CalendarDays} message={t("noClassesDay")} />
        )}
      </div>
    </Panel>
  );
}

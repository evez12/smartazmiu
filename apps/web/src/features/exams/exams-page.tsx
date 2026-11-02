"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarPlus, MapPin } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { touchTarget } from "@/components/ui/touch-target";
import { useNow } from "@/features/attendance/attendance-shared";
import { offeringLabel, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import { countdown, mapLink, type ExamSlot } from "./model";
import { useFormatters } from "@/lib/use-format";

/** The student's or teacher's upcoming exams with a countdown in Baku time, the room on the map and a calendar file. */
export function ExamsPage() {
  const t = useTranslations("exams");
  const api = useApi();
  const now = useNow();
  const query = useQuery({
    queryKey: ["exams", "mine"],
    queryFn: async () => unwrap(await api.GET("/api/v1/exams/mine")).items,
  });
  const items = query.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="secondary">
          <Link href="/exams/papers">{t("papersLink")}</Link>
        </Button>
        {items.length > 0 ? (
          <Button asChild variant="tertiary">
            <a href="/api/v1/exams/mine.ics" download>
              <CalendarPlus aria-hidden className="size-4" />
              {t("calendar")}
            </a>
          </Button>
        ) : null}
      </div>
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={!query.isLoading && !query.isError && items.length === 0}
        emptyMessage={t("empty")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
      <ul aria-label={t("listLabel")} className="flex flex-col gap-3">
        {items.map((slot) => (
          <li key={slot.id}>
            <ExamCard slot={slot} now={now} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ExamCard({ slot, now }: { slot: ExamSlot; now: number }) {
  const { formatDateTimeRange } = useFormatters();
  const t = useTranslations("exams");
  const left = countdown(slot.starts_at, slot.ends_at, now);
  return (
    <Panel>
      <PanelBody>
        <article className="flex flex-col gap-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h2 className="text-lg font-semibold break-words">{slot.offering.subject_name}</h2>
            <Tag tone={left.kind === "running" ? "warning" : "info"}>{countdownText(t, left)}</Tag>
          </div>
          <p className="text-sm text-muted">{offeringLabel(slot.offering)}</p>
          <p className="tabular">{formatDateTimeRange(slot.starts_at, slot.ends_at)}</p>
          {slot.room_code ? (
            <p>
              <Link
                href={mapLink(slot.room_code)}
                className={`inline-flex items-center gap-1 text-primary hover:underline ${touchTarget}`}
              >
                <MapPin aria-hidden className="size-4" />
                {t("room", { room: slot.room_code })}
              </Link>
            </p>
          ) : (
            <p className="text-sm text-muted">{t("roomUnknown")}</p>
          )}
        </article>
      </PanelBody>
    </Panel>
  );
}

function countdownText(
  t: ReturnType<typeof useTranslations<"exams">>,
  left: ReturnType<typeof countdown>,
): string {
  switch (left.kind) {
    case "running":
      return t("countdown.running");
    case "days":
      return t("countdown.days", { days: left.days, hours: left.hours });
    case "hours":
      return t("countdown.hours", { hours: left.hours, minutes: left.minutes });
    case "minutes":
      return t("countdown.minutes", { minutes: left.minutes });
  }
}

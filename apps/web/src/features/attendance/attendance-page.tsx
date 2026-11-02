"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, QrCode } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { touchTarget } from "@/components/ui/touch-target";
import { offeringLabel, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { formatRate, rateTone, type AttendanceOffering } from "./attendance-shared";
import { useFormatters } from "@/lib/use-format";

const DURATIONS = [45, 90, 135, 180] as const;

/** A student's own rates, and, for teachers, staff and curators, the offerings they run or read. */
export function AttendancePage() {
  const t = useTranslations("attendance");
  const api = useApi();
  const mine = useQuery({
    queryKey: ["attendance", "my"],
    queryFn: async () => unwrap(await api.GET("/api/v1/attendance/my")).items,
  });
  const offerings = useQuery({
    queryKey: ["attendance", "offerings"],
    queryFn: async () => unwrap(await api.GET("/api/v1/attendance/offerings")).items,
  });
  const runs = offerings.data ?? [];
  const attends = mine.data ?? [];
  const loading = mine.isLoading || offerings.isLoading;
  const failed = mine.error ?? offerings.error;
  return (
    <div className="flex flex-col gap-6">
      <ScreenState
        loading={loading}
        error={failed}
        empty={!loading && !failed && attends.length === 0 && runs.length === 0}
        emptyMessage={t("empty")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => {
          void mine.refetch();
          void offerings.refetch();
        }}
      />
      {attends.length > 0 ? (
        <section aria-labelledby="attendance-mine" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="attendance-mine" className="text-lg font-semibold">
              {t("mineHeading")}
            </h2>
            <Button asChild variant="primary">
              <Link href="/attendance/scan">
                <QrCode aria-hidden className="size-4" />
                {t("scanAction")}
              </Link>
            </Button>
          </div>
          <ul aria-label={t("mineHeading")} className="flex flex-col gap-3">
            {attends.map((item) => (
              <li key={item.offering.id}>
                <Panel>
                  <PanelBody>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link
                        className={`min-w-0 font-medium break-words text-primary hover:underline ${touchTarget}`}
                        href={`/attendance/my/${item.offering.id}`}
                      >
                        {offeringLabel(item.offering)}
                      </Link>
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-muted tabular">
                          {t("attendedOf", { attended: item.attended, total: item.total })}
                        </span>
                        <Tag tone={rateTone(item.rate, item.total)}>
                          {item.total === 0 ? t("noMeetings") : formatRate(item.rate)}
                        </Tag>
                      </div>
                    </div>
                  </PanelBody>
                </Panel>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {runs.length > 0 ? <RunPanel offerings={runs} /> : null}
    </div>
  );
}

/** One offering at a time: its recent meetings, a form to open the next one, and the report. */
function RunPanel({ offerings }: { offerings: AttendanceOffering[] }) {
  const t = useTranslations("attendance");
  const api = useApi();
  const router = useRouter();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [picked, setPicked] = useState("");
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState<number>(90);
  const current = offerings.find((o) => o.id === picked) ?? offerings[0]!;
  const isManager = current.role === "manager";

  const sessions = useQuery({
    queryKey: ["attendance", "sessions", current.id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/attendance/sessions", {
          params: { query: { offering_id: current.id } },
        }),
      ).items,
    enabled: isManager,
  });
  const open = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/attendance/sessions", {
          body: {
            course_offering_id: current.id,
            title: title.trim(),
            duration_minutes: minutes,
          },
        }),
      ),
    onSuccess: (created) => {
      void client.invalidateQueries({ queryKey: ["attendance", "sessions"] });
      router.push(`/attendance/sessions/${created.id}`);
    },
  });
  const openMeeting = sessions.data?.find((s) => s.is_open);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    open.mutate();
  };
  return (
    <section aria-labelledby="attendance-run" className="flex flex-col gap-3">
      <h2 id="attendance-run" className="text-lg font-semibold">
        {t("run")}
      </h2>
      <Panel>
        <PanelBody>
          <div className="flex max-w-2xl flex-col gap-4">
            <Field label={t("offering")}>
              <Select
                value={current.id}
                onChange={(event) => {
                  setPicked(event.target.value);
                  open.reset();
                }}
              >
                {offerings.map((offering) => (
                  <option key={offering.id} value={offering.id}>
                    {offeringLabel(offering)}
                    {offering.role === "curator" ? ` (${t("roleCurator")})` : ""}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex flex-wrap gap-3">
              <Button asChild variant="secondary">
                <Link href={`/attendance/reports/${current.id}`}>{t("reportAction")}</Link>
              </Button>
              <Button asChild variant="tertiary">
                <a href={`/api/v1/attendance/offerings/${current.id}/report.csv`} download>
                  <Download aria-hidden className="size-4" />
                  {t("exportCsv")}
                </a>
              </Button>
              <Button asChild variant="tertiary">
                <a href={`/api/v1/attendance/offerings/${current.id}/report.xlsx`} download>
                  <Download aria-hidden className="size-4" />
                  {t("exportXlsx")}
                </a>
              </Button>
            </div>
            {isManager ? (
              openMeeting ? (
                <Banner
                  tone="info"
                  title={t("alreadyOpen")}
                  action={
                    <Button asChild variant="secondary">
                      <Link href={`/attendance/sessions/${openMeeting.id}`}>{t("continue")}</Link>
                    </Button>
                  }
                />
              ) : (
                <form noValidate onSubmit={submit} className="flex flex-col gap-4">
                  {open.isError ? (
                    <Banner tone="danger" title={t("openFailed")}>
                      {errorMessage(open.error)}
                    </Banner>
                  ) : null}
                  <Field label={t("meetingTitle")} helper={t("meetingTitleHelp")}>
                    <Input
                      value={title}
                      maxLength={120}
                      onChange={(event) => setTitle(event.target.value)}
                    />
                  </Field>
                  <Field label={t("duration")}>
                    <Select
                      value={String(minutes)}
                      onChange={(event) => setMinutes(Number(event.target.value))}
                    >
                      {DURATIONS.map((value) => (
                        <option key={value} value={value}>
                          {t("minutes", { count: value })}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <div>
                    <Button type="submit" variant="primary" loading={open.isPending}>
                      {t("open")}
                    </Button>
                  </div>
                </form>
              )
            ) : null}
          </div>
        </PanelBody>
      </Panel>
      {isManager ? (
        <MeetingList
          items={sessions.data ?? []}
          loading={sessions.isLoading}
          error={sessions.error}
          retry={() => void sessions.refetch()}
        />
      ) : (
        <Banner tone="info" title={t("curatorNote")} />
      )}
    </section>
  );
}

function MeetingList({
  items,
  loading,
  error,
  retry,
}: {
  items: {
    id: string;
    title: string;
    opened_at: string;
    is_open: boolean;
    present: number;
    enrolled: number;
  }[];
  loading: boolean;
  error: unknown;
  retry: () => void;
}) {
  const { formatDateTime } = useFormatters();
  const t = useTranslations("attendance");
  return (
    <>
      <ScreenState
        loading={loading}
        error={error}
        empty={!loading && !error && items.length === 0}
        emptyMessage={t("noMeetingsYet")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={retry}
      />
      {items.length > 0 ? (
        <ul aria-label={t("meetings")} className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={item.id}>
              <Panel>
                <PanelBody>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Link
                      className={`min-w-0 font-medium break-words text-primary hover:underline ${touchTarget}`}
                      href={`/attendance/sessions/${item.id}`}
                    >
                      {item.title || formatDateTime(item.opened_at)}
                    </Link>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-muted tabular">
                        {t("presentOf", { present: item.present, enrolled: item.enrolled })}
                      </span>
                      <Tag tone={item.is_open ? "success" : "neutral"}>
                        {item.is_open ? t("statusOpen") : t("statusClosed")}
                      </Tag>
                    </div>
                  </div>
                  {item.title ? (
                    <p className="mt-1 text-sm text-muted">{formatDateTime(item.opened_at)}</p>
                  ) : null}
                </PanelBody>
              </Panel>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

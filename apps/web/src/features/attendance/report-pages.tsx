"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { offeringLabel, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { formatDateTime } from "@/lib/format";

import { formatRate, rateTone } from "./attendance-shared";

/** Attendance of every student of an offering, for its teacher, the dean's office and a group curator. */
export function ReportPage({ offeringId }: { offeringId: string }) {
  const t = useTranslations("attendance.report");
  const api = useApi();
  const query = useQuery({
    queryKey: ["attendance", "report", offeringId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/attendance/offerings/{offering_id}/report", {
          params: { path: { offering_id: offeringId } },
        }),
      ),
  });
  const report = query.data;
  if (!report) {
    return (
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="min-w-0 break-words text-muted">
          {offeringLabel(report.offering)} · {t("meetings", { count: report.sessions.length })}
        </p>
        <div className="flex gap-3">
          <Button asChild variant="secondary">
            <a href={`/api/v1/attendance/offerings/${offeringId}/report.csv`} download>
              <Download aria-hidden className="size-4" />
              {t("exportCsv")}
            </a>
          </Button>
          <Button asChild variant="secondary">
            <a href={`/api/v1/attendance/offerings/${offeringId}/report.xlsx`} download>
              <Download aria-hidden className="size-4" />
              {t("exportXlsx")}
            </a>
          </Button>
        </div>
      </div>
      {report.rows.length === 0 ? (
        <Panel>
          <PanelBody>
            <p className="text-muted">{t("empty")}</p>
          </PanelBody>
        </Panel>
      ) : (
        <ReportTable rows={report.rows} />
      )}
    </div>
  );
}

export type ReportRow = components["schemas"]["AttendanceReportRowOut"];

export function ReportTable({ rows }: { rows: ReportRow[] }) {
  const t = useTranslations("attendance.report");
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.student")}</TableHead>
          <TableHead>{t("columns.group")}</TableHead>
          <TableHead numeric>{t("columns.attended")}</TableHead>
          <TableHead numeric>{t("columns.rate")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.student_id}>
            <TableCell label={t("columns.student")}>{row.display_name}</TableCell>
            <TableCell label={t("columns.group")}>{row.group ?? "—"}</TableCell>
            <TableCell label={t("columns.attended")} numeric>
              {t("attendedOf", { attended: row.attended, total: row.total })}
            </TableCell>
            <TableCell label={t("columns.rate")} numeric>
              <Tag tone={rateTone(row.rate, row.total)}>
                {row.total === 0 ? t("noMeetings") : formatRate(row.rate)}
              </Tag>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** One course, meeting by meeting: what a student sees of their own attendance. */
export function MyCoursePage({ offeringId }: { offeringId: string }) {
  const t = useTranslations("attendance.mine");
  const api = useApi();
  const query = useQuery({
    queryKey: ["attendance", "my", offeringId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/attendance/my/{offering_id}", {
          params: { path: { offering_id: offeringId } },
        }),
      ),
  });
  const course = query.data;
  if (!course) {
    return (
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelBody>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="min-w-0 font-medium break-words">{offeringLabel(course.offering)}</p>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted tabular">
                {t("attendedOf", { attended: course.attended, total: course.total })}
              </span>
              <Tag tone={rateTone(course.rate, course.total)}>
                {course.total === 0 ? t("noMeetings") : formatRate(course.rate)}
              </Tag>
            </div>
          </div>
        </PanelBody>
      </Panel>
      {course.sessions.length === 0 ? (
        <Panel>
          <PanelBody>
            <p className="text-muted">{t("empty")}</p>
          </PanelBody>
        </Panel>
      ) : (
        <ul aria-label={t("list")} className="flex flex-col gap-2">
          {course.sessions.map((meeting) => (
            <li key={meeting.id}>
              <Panel>
                <PanelBody>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="min-w-0 break-words">
                      {meeting.title || formatDateTime(meeting.opened_at)}
                      {meeting.title ? (
                        <span className="block text-sm text-muted">
                          {formatDateTime(meeting.opened_at)}
                        </span>
                      ) : null}
                    </span>
                    <Tag tone={meeting.present ? "success" : "danger"}>
                      {meeting.present ? t("present") : t("absent")}
                    </Tag>
                  </div>
                </PanelBody>
              </Panel>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

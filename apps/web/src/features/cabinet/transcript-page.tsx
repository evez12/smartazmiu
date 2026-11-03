"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { useFormatters } from "@/lib/use-format";

import { SourceNotice } from "./source-notice";

type Transcript = components["schemas"]["TranscriptOut"];
type Semester = Transcript["semesters"][number];
type Appeal = components["schemas"]["AppealOut"];

const TERMS = { fall: "fall", spring: "spring", summer: "summer" } as const;
const APPEAL_TONE = {
  submitted: "info",
  under_review: "warning",
  upheld: "success",
  rejected: "danger",
} as const;

/** Two decimals with a comma, as the cabinet prints them; the figure is the cabinet's own, not recalculated. */
export function formatAverage(value: number | null): string {
  return value === null ? "–" : value.toFixed(2).replace(".", ",");
}

export function useTranscript() {
  const api = useApi();
  return useQuery({
    queryKey: ["cabinet", "transcript"],
    queryFn: async () => unwrap(await api.GET("/api/v1/me/transcript")),
  });
}

/** The student's transcript and appeals from the nightly mirror of the personal cabinet (D-126). */
export function TranscriptPage() {
  const t = useTranslations("cabinet.transcript");
  const query = useTranscript();
  const data = query.data;
  const empty = data !== undefined && data.student === null && data.semesters.length === 0;
  return (
    <div className="flex flex-col gap-4">
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
      {data ? <SourceNotice source={data.source} /> : null}
      {empty ? (
        <Panel>
          <PanelBody>
            <p data-testid="cabinet-empty">
              {data?.source.state === "unavailable" ? t("emptyUnavailable") : t("empty")}
            </p>
          </PanelBody>
        </Panel>
      ) : null}
      {data && !empty ? (
        <>
          <Summary data={data} />
          {data.semesters.map((semester) => (
            <SemesterPanel
              key={`${semester.semester_year}-${semester.semester_term}`}
              semester={semester}
            />
          ))}
          <Appeals />
        </>
      ) : null}
    </div>
  );
}

export function Summary({ data }: { data: Transcript }) {
  const t = useTranslations("cabinet.transcript");
  if (!data.student) return null;
  const conflicts = data.semesters.reduce(
    (sum, semester) => sum + semester.courses.filter((course) => course.differs).length,
    0,
  );
  return (
    <Panel aria-labelledby="cabinet-summary">
      <PanelHeader
        title={t("summaryTitle")}
        titleId="cabinet-summary"
        description={t("summaryDescription")}
      />
      <PanelBody className="flex flex-col gap-3">
        <dl className="grid gap-3 sm:grid-cols-3">
          <div>
            <dt className="text-sm text-muted">{t("specialty")}</dt>
            <dd>{data.student.specialty_name}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted">{t("creditsEarned")}</dt>
            <dd className="tabular" data-testid="cabinet-credits">
              {data.student.credits_earned}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-muted">{t("cumulativeAverage")}</dt>
            <dd className="tabular" data-testid="cabinet-average">
              {formatAverage(data.student.cumulative_average)}
            </dd>
          </div>
        </dl>
        {conflicts > 0 ? <p className="text-sm">{t("differsHelp", { count: conflicts })}</p> : null}
      </PanelBody>
    </Panel>
  );
}

export function SemesterPanel({ semester }: { semester: Semester }) {
  const t = useTranslations("cabinet.transcript");
  const tTerms = useTranslations("gpa.terms");
  const name = t("semesterName", {
    year: semester.semester_year,
    term: tTerms(TERMS[semester.semester_term]),
  });
  const id = `cabinet-${semester.semester_year}-${semester.semester_term}`;
  return (
    <Panel aria-labelledby={id}>
      <PanelHeader
        title={name}
        titleId={id}
        description={
          semester.credits_attempted === null
            ? undefined
            : t("semesterFigures", {
                average: formatAverage(semester.average),
                earned: semester.credits_earned ?? 0,
                attempted: semester.credits_attempted,
              })
        }
      />
      <div className="px-4 pb-2">
        <Table>
          <TableCaption>{name}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("subject")}</TableHead>
              <TableHead numeric>{t("credits")}</TableHead>
              <TableHead numeric>{t("score")}</TableHead>
              <TableHead>{t("status")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {semester.courses.map((course) => (
              <TableRow key={course.subject_code}>
                <TableCell label={t("subject")}>
                  <div className="min-w-0 max-md:text-right">
                    <span className="break-words">{course.subject_name}</span>
                    <span className="block text-sm text-muted">{course.subject_code}</span>
                  </div>
                </TableCell>
                <TableCell label={t("credits")} numeric>
                  {course.credits}
                </TableCell>
                <TableCell label={t("score")} numeric>
                  {course.score}
                </TableCell>
                <TableCell label={t("status")}>
                  <span className="flex flex-wrap gap-1">
                    {course.passed ? (
                      <Tag tone="success">{t("passed")}</Tag>
                    ) : (
                      <Tag tone="danger">{t("failed")}</Tag>
                    )}
                    {course.differs ? <Tag tone="warning">{t("differs")}</Tag> : null}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Panel>
  );
}

function Appeals() {
  const t = useTranslations("cabinet.transcript");
  const api = useApi();
  const query = useQuery({
    queryKey: ["cabinet", "appeals"],
    queryFn: async () => unwrap(await api.GET("/api/v1/me/transcript/appeals")),
  });
  const items = query.data?.items ?? [];
  return (
    <Panel aria-labelledby="cabinet-appeals">
      <PanelHeader
        title={t("appealsTitle")}
        titleId="cabinet-appeals"
        description={t("appealsDescription")}
      />
      <div className="px-4 pb-2">
        <ScreenState
          loading={query.isLoading}
          error={query.error}
          empty={query.isSuccess && items.length === 0}
          emptyMessage={t("appealsEmpty")}
          errorMessage={t("error")}
          retryLabel={t("retry")}
          retry={() => void query.refetch()}
        />
        {items.length > 0 ? <AppealTable items={items} /> : null}
      </div>
    </Panel>
  );
}

export function AppealTable({ items }: { items: Appeal[] }) {
  const t = useTranslations("cabinet.transcript");
  const { formatDate } = useFormatters();
  return (
    <Table>
      <TableCaption>{t("appealsTitle")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("reference")}</TableHead>
          <TableHead>{t("subject")}</TableHead>
          <TableHead>{t("submittedOn")}</TableHead>
          <TableHead>{t("decidedOn")}</TableHead>
          <TableHead>{t("status")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((appeal) => (
          <TableRow key={appeal.reference}>
            <TableCell label={t("reference")} className="tabular">
              {appeal.reference}
            </TableCell>
            <TableCell label={t("subject")}>
              <div className="min-w-0 max-md:text-right">
                <span className="break-words">{appeal.subject_name ?? appeal.subject_code}</span>
                <span className="block text-sm text-muted">{appeal.subject_code}</span>
              </div>
            </TableCell>
            <TableCell label={t("submittedOn")} className="tabular">
              {formatDate(appeal.submitted_on)}
            </TableCell>
            <TableCell label={t("decidedOn")} className="tabular">
              {appeal.decided_on ? formatDate(appeal.decided_on) : "–"}
            </TableCell>
            <TableCell label={t("status")}>
              <Tag tone={APPEAL_TONE[appeal.status]}>{t(`appealStatus.${appeal.status}`)}</Tag>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

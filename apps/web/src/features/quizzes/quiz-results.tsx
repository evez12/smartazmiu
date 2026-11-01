"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
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
import { formatPoints, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import { formatDateTime } from "@/lib/format";

/** Statistics and every attempt of one quiz, for the people who manage its offering (§8 Sprint 13). */
export function QuizResults({ quizId }: { quizId: string }) {
  const t = useTranslations("quizzes");
  const api = useApi();
  const stats = useQuery({
    queryKey: ["quiz-stats", quizId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/quizzes/{quiz_id}/stats", { params: { path: { quiz_id: quizId } } }),
      ),
  });
  const attempts = useQuery({
    queryKey: ["quiz-attempts", quizId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/quizzes/{quiz_id}/attempts", {
          params: { path: { quiz_id: quizId } },
        }),
      ).items,
  });
  const rows = attempts.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelHeader title={t("results.stats")} />
        <PanelBody>
          {stats.data ? (
            <div className="flex flex-col gap-4">
              <dl className="grid gap-4 sm:grid-cols-4">
                <Figure
                  label={t("results.statsAttempts")}
                  value={String(stats.data.submitted_attempts)}
                />
                <Figure label={t("results.statsStudents")} value={String(stats.data.students)} />
                <Figure
                  label={t("results.statsAverage")}
                  value={
                    stats.data.average_percent === null
                      ? t("results.noAverage")
                      : `${stats.data.average_percent}%`
                  }
                />
                <Figure
                  label={t("results.statsPending")}
                  value={String(stats.data.pending_review)}
                />
              </dl>
              <section aria-label={t("results.distribution")}>
                <h3 className="mb-2 font-medium">{t("results.distribution")}</h3>
                <ul className="flex flex-col gap-1">
                  {stats.data.distribution.map((bucket) => (
                    <li key={bucket.label} className="flex items-center gap-3">
                      <span className="w-20 text-sm tabular">{bucket.label}%</span>
                      <progress
                        className="h-3 flex-1"
                        value={bucket.count}
                        max={Math.max(1, stats.data.submitted_attempts)}
                        aria-label={`${bucket.label}%`}
                      />
                      <span className="w-8 text-right text-sm tabular">{bucket.count}</span>
                    </li>
                  ))}
                </ul>
              </section>
              <section aria-label={t("results.questions")}>
                <h3 className="mb-2 font-medium">{t("results.questions")}</h3>
                <ol className="flex flex-col gap-2">
                  {stats.data.questions.map((question) => (
                    <li key={question.question_id} className="flex flex-wrap justify-between gap-2">
                      <span className="min-w-0 break-words">
                        {question.position}. {question.prompt}
                      </span>
                      <span className="text-sm text-muted tabular">
                        {question.correct_percent === null
                          ? t("results.openQuestion")
                          : t("results.correctPercent", { percent: question.correct_percent })}
                      </span>
                    </li>
                  ))}
                </ol>
              </section>
            </div>
          ) : (
            <ScreenState
              loading={stats.isLoading}
              error={stats.error}
              empty={false}
              emptyMessage=""
              errorMessage={t("error")}
              retryLabel={t("retry")}
              retry={() => void stats.refetch()}
            />
          )}
        </PanelBody>
      </Panel>
      <Panel>
        <PanelHeader title={t("results.attempts")} />
        <PanelBody>
          <ScreenState
            loading={attempts.isLoading}
            error={attempts.error}
            empty={!attempts.isLoading && !attempts.isError && rows.length === 0}
            emptyMessage={t("results.empty")}
            errorMessage={t("error")}
            retryLabel={t("retry")}
            retry={() => void attempts.refetch()}
          />
          {rows.length ? (
            <Table>
              <TableCaption>{t("results.attemptsCaption")}</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("results.student")}</TableHead>
                  <TableHead numeric>{t("results.attemptNumber")}</TableHead>
                  <TableHead>{t("results.submittedAt")}</TableHead>
                  <TableHead numeric>{t("results.score")}</TableHead>
                  <TableHead>{t("results.status")}</TableHead>
                  <TableHead>
                    <span className="sr-only">{t("results.review")}</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell label={t("results.student")}>{row.student.display_name}</TableCell>
                    <TableCell label={t("results.attemptNumber")} numeric>
                      {row.attempt_number}
                    </TableCell>
                    <TableCell label={t("results.submittedAt")} className="tabular">
                      {row.submitted_at ? formatDateTime(row.submitted_at) : "—"}
                    </TableCell>
                    <TableCell label={t("results.score")} numeric>
                      {row.score !== null && row.max_score !== null
                        ? `${formatPoints(row.score)} / ${formatPoints(row.max_score)}`
                        : "—"}
                    </TableCell>
                    <TableCell label={t("results.status")}>
                      {row.status === "in_progress" ? (
                        <Tag>{t("results.inProgress")}</Tag>
                      ) : row.pending_review ? (
                        <Tag tone="warning">{t("results.needsScoring")}</Tag>
                      ) : (
                        <Tag tone="success">{t("results.scored")}</Tag>
                      )}
                    </TableCell>
                    <TableCell label={t("results.review")}>
                      {row.status !== "in_progress" ? (
                        <Link
                          className="text-primary hover:underline"
                          href={`/quizzes/${quizId}/results/${row.id}`}
                        >
                          {t("results.review")}
                        </Link>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </PanelBody>
      </Panel>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-2xl font-semibold tabular">{value}</dd>
    </div>
  );
}

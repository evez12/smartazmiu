"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { offeringLabel, ScreenState, useManagedOfferings } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { useFormatters } from "@/lib/use-format";

export type QuizSummary = components["schemas"]["QuizSummaryOut"];

/** Facts shown under a quiz title in the list and on its page. */
export function QuizFacts({ quiz }: { quiz: QuizSummary }) {
  const { formatDateTime } = useFormatters();
  const t = useTranslations("quizzes");
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted tabular">
      <span>{t("questionCount", { count: quiz.question_count })}</span>
      <span>
        {quiz.time_limit_seconds
          ? t("timeLimit", { minutes: Math.round(quiz.time_limit_seconds / 60) })
          : t("noTimeLimit")}
      </span>
      <span>{t("attemptsAllowed", { count: quiz.max_attempts })}</span>
      {quiz.deadline ? (
        <span>{t("deadlineAt", { time: formatDateTime(quiz.deadline) })}</span>
      ) : null}
      {quiz.available_from ? (
        <span>{t("opensAt", { time: formatDateTime(quiz.available_from) })}</span>
      ) : null}
    </div>
  );
}

/** One quiz in the list: its facts, and the manager's or the student's own progress. */
export function QuizCard({ quiz }: { quiz: QuizSummary }) {
  const t = useTranslations("quizzes");
  return (
    <Panel>
      <PanelBody>
        <article className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold break-words">
            <Link className="text-primary hover:underline" href={`/quizzes/${quiz.id}`}>
              {quiz.title}
            </Link>
          </h2>
          <p className="text-sm text-muted">{offeringLabel(quiz.offering)}</p>
          <QuizFacts quiz={quiz} />
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted tabular">
            {quiz.can_manage ? (
              <>
                <Tag tone={quiz.published ? "success" : "neutral"}>
                  {quiz.published ? t("published") : t("draft")}
                </Tag>
                <span>{t("studentsAttempted", { count: quiz.students_attempted ?? 0 })}</span>
              </>
            ) : (
              <>
                <span>
                  {t("attemptsUsed", {
                    used: quiz.attempts_used ?? 0,
                    max: quiz.max_attempts,
                  })}
                </span>
                {quiz.best_percent !== null ? (
                  <span>{t("bestResult", { percent: quiz.best_percent })}</span>
                ) : null}
              </>
            )}
          </div>
        </article>
      </PanelBody>
    </Panel>
  );
}

export function QuizzesPage() {
  const t = useTranslations("quizzes");
  const api = useApi();
  const offerings = useManagedOfferings();
  const query = useQuery({
    queryKey: ["quizzes"],
    queryFn: async () => unwrap(await api.GET("/api/v1/quizzes")).items,
  });
  const canCreate = (offerings.data?.length ?? 0) > 0;
  const items = query.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      {canCreate ? (
        <div>
          <Button asChild variant="primary">
            <Link href="/quizzes/new">{t("create")}</Link>
          </Button>
        </div>
      ) : null}
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={!query.isLoading && !query.isError && items.length === 0}
        emptyMessage={canCreate ? t("emptyManager") : t("empty")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
      <ul aria-label={t("listLabel")} className="flex flex-col gap-3">
        {items.map((quiz) => (
          <li key={quiz.id}>
            <QuizCard quiz={quiz} />
          </li>
        ))}
      </ul>
    </div>
  );
}

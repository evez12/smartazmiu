"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

/** One attempt with its answers; the teacher gives points to the open questions (D-092). */
export function QuizReview({ quizId, attemptId }: { quizId: string; attemptId: string }) {
  const t = useTranslations("quizzes");
  const tReview = useTranslations("quizzes.review");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const query = useQuery({
    queryKey: ["quiz-review", attemptId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/quiz-attempts/{attempt_id}/review", {
          params: { path: { attempt_id: attemptId } },
        }),
      ),
  });
  const [edited, setEdited] = useState<Record<string, string>>({});
  const [problems, setProblems] = useState<Record<string, string>>({});
  const saved = query.data?.manual_scores ?? {};
  // A typed value wins over the score already saved.
  const scores = (id: string) => edited[id] ?? (id in saved ? String(saved[id]) : "");

  const save = useMutation({
    mutationFn: async (value: Record<string, number>) =>
      unwrap(
        await api.PUT("/api/v1/quiz-attempts/{attempt_id}/open-question-scores", {
          params: { path: { attempt_id: attemptId } },
          body: { scores: value },
        }),
      ),
    onSuccess: async () => {
      toast({ title: tReview("saved") });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["quiz-review", attemptId] }),
        queryClient.invalidateQueries({ queryKey: ["quiz-attempts", quizId] }),
        queryClient.invalidateQueries({ queryKey: ["quiz-stats", quizId] }),
      ]);
    },
  });

  if (!query.data) {
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
  const review = query.data;
  const open = review.questions.filter((question) => question.type === "short_answer");

  const submit = () => {
    const found: Record<string, string> = {};
    const payload: Record<string, number> = {};
    for (const question of open) {
      const raw = scores(question.id).trim();
      if (raw === "") continue;
      const value = Number(raw);
      if (!(Number.isInteger(value) && value >= 0 && value <= question.points)) {
        found[question.id] = tReview("openScoreInvalid", { max: question.points });
      } else {
        payload[question.id] = value;
      }
    }
    setProblems(found);
    if (Object.keys(found).length === 0 && Object.keys(payload).length > 0) save.mutate(payload);
  };

  return (
    <div className="flex flex-col gap-4">
      <Link className="text-primary hover:underline" href={`/quizzes/${quizId}/results`}>
        {tReview("back")}
      </Link>
      <Panel>
        <PanelHeader
          title={review.student.display_name}
          action={
            review.score !== null && review.max_score !== null ? (
              <span className="font-semibold tabular">
                {t("attempt.resultScore", { score: review.score, max: review.max_score })}
              </span>
            ) : undefined
          }
        />
      </Panel>
      {save.isError ? (
        <Banner tone="danger" title={tReview("failed")}>
          {errorMessage(save.error)}
        </Banner>
      ) : null}
      <ol className="flex flex-col gap-4">
        {review.questions.map((question) => {
          const answer = review.answers[question.id];
          const options = Object.fromEntries(question.options.map((o) => [o.id, o.text]));
          const given = Array.isArray(answer)
            ? answer.map((id: string) => options[id] ?? id).join(", ")
            : typeof answer === "string"
              ? (options[answer] ?? answer)
              : "";
          const right = Array.isArray(question.correct_answer)
            ? question.correct_answer.map((id: string) => options[id] ?? id).join(", ")
            : (options[String(question.correct_answer)] ?? String(question.correct_answer ?? ""));
          const correct =
            JSON.stringify(Array.isArray(answer) ? [...answer].sort() : answer) ===
            JSON.stringify(
              Array.isArray(question.correct_answer)
                ? [...question.correct_answer].sort()
                : question.correct_answer,
            );
          return (
            <li key={question.id}>
              <Panel>
                <PanelHeader
                  title={t("attempt.question", {
                    number: question.position,
                    total: review.questions.length,
                  })}
                  action={
                    question.type === "short_answer" ? undefined : (
                      <Tag tone={correct ? "success" : "danger"}>
                        {correct ? tReview("wasRight") : tReview("wasWrong")}
                      </Tag>
                    )
                  }
                />
                <PanelBody>
                  <div className="flex flex-col gap-3">
                    <p className="break-words whitespace-pre-wrap">{question.prompt}</p>
                    <p className="break-words">
                      <span className="font-medium">{tReview("yourAnswer")}: </span>
                      {given || <span className="text-muted">{tReview("noAnswer")}</span>}
                    </p>
                    {question.type !== "short_answer" ? (
                      <p className="text-sm break-words text-muted">
                        {tReview("correct")}: {right}
                      </p>
                    ) : (
                      <>
                        {question.correct_answer ? (
                          <p className="text-sm break-words text-muted">
                            {t("builder.modelAnswer")}: {String(question.correct_answer)}
                          </p>
                        ) : null}
                        <Field
                          label={tReview("openScore", { max: question.points })}
                          error={problems[question.id]}
                        >
                          <Input
                            inputMode="numeric"
                            className="w-24 tabular"
                            value={scores(question.id)}
                            onChange={(event) =>
                              setEdited({ ...edited, [question.id]: event.target.value })
                            }
                          />
                        </Field>
                      </>
                    )}
                  </div>
                </PanelBody>
              </Panel>
            </li>
          );
        })}
      </ol>
      {open.length > 0 ? (
        <div>
          <Button variant="primary" loading={save.isPending} onClick={submit}>
            {tReview("save")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

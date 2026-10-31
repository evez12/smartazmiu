"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox, RadioGroup } from "@/components/ui/choice";
import { Field, Textarea } from "@/components/ui/field";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { ScreenState } from "@/features/coursework/coursework";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

type Attempt = components["schemas"]["AttemptOut"];
type Question = components["schemas"]["QuestionOut"];
type Answers = Record<string, string | string[]>;

const AUTOSAVE_MS = 1500;

function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function isAnswered(value: string | string[] | undefined): boolean {
  return Array.isArray(value) ? value.length > 0 : Boolean(value?.trim());
}

export function QuizAttemptPage({ quizId, attemptId }: { quizId: string; attemptId: string }) {
  const t = useTranslations("quizzes");
  const api = useApi();
  const query = useQuery({
    queryKey: ["quiz-attempt", attemptId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/quiz-attempts/{attempt_id}", {
          params: { path: { attempt_id: attemptId } },
        }),
      ),
    // Nothing here is stale-while-answering: a refetch would race the autosave.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  if (!query.data) {
    return (
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("attempt.loadFailed")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
    );
  }
  return query.data.status === "in_progress" ? (
    <TakeAttempt attempt={query.data} quizId={quizId} />
  ) : (
    <Result attempt={query.data} quizId={quizId} />
  );
}

function TakeAttempt({ attempt, quizId }: { attempt: Attempt; quizId: string }) {
  const t = useTranslations("quizzes.attempt");
  const api = useApi();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const questions = attempt.questions ?? [];
  const [answers, setAnswers] = useState<Answers>(attempt.answers as Answers);
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "failed">("idle");
  const [confirming, setConfirming] = useState(false);
  const [timeUp, setTimeUp] = useState(false);
  // The countdown runs from the server's clock, so a wrong device clock changes nothing (§13.2).
  const [offset] = useState(() => Date.parse(attempt.server_time) - Date.now());
  const expiresAt = attempt.expires_at ? Date.parse(attempt.expires_at) : null;
  const remaining = useCountdown(expiresAt, offset);

  const store = useCallback(
    (data: Attempt) => queryClient.setQueryData(["quiz-attempt", attempt.id], data),
    [queryClient, attempt.id],
  );
  const refetch = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["quiz-attempt", attempt.id] }),
    [queryClient, attempt.id],
  );

  const save = useMutation({
    mutationFn: async (value: Answers) =>
      unwrap(
        await api.PATCH("/api/v1/quiz-attempts/{attempt_id}", {
          params: { path: { attempt_id: attempt.id } },
          body: { answers: value },
        }),
      ),
    onSuccess: () => setSaveState("saved"),
    onError: (error) => {
      // A 409 means the server already closed the attempt (time ran out): show its result instead.
      if (error instanceof ApiRequestError && error.status === 409) void refetch();
      else setSaveState("failed");
    },
  });
  const submit = useMutation({
    mutationFn: async (value: Answers) =>
      unwrap(
        await api.POST("/api/v1/quiz-attempts/{attempt_id}/submit", {
          params: { path: { attempt_id: attempt.id } },
          body: { answers: value },
        }),
      ),
    onSuccess: (result) => {
      setConfirming(false);
      store(result);
    },
    onError: (error) => {
      setConfirming(false);
      if (error instanceof ApiRequestError && error.status === 409) {
        setTimeUp(true);
        void refetch();
      }
    },
  });

  useEffect(() => {
    if (!dirty) return;
    const timer = window.setTimeout(() => {
      setSaveState("saving");
      setDirty(false);
      save.mutate(answers);
    }, AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
    // `save` is a stable mutation object; the effect restarts only when the answers change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answers, dirty]);

  const expired = remaining !== null && remaining <= 0;
  const finishedByTime = useRef(false);
  useEffect(() => {
    if (expired && !finishedByTime.current) {
      finishedByTime.current = true;
      submit.mutate(answers);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expired]);

  const change = (id: string, value: string | string[]) => {
    setAnswers((old) => ({ ...old, [id]: value }));
    setDirty(true);
    setSaveState("idle");
  };
  const unanswered = questions.filter((question) => !isAnswered(answers[question.id])).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="sticky top-14 z-10 flex flex-wrap items-center justify-between gap-2 rounded-panel border border-border bg-surface p-3">
        <p role="timer" className="font-semibold tabular">
          {remaining === null
            ? t("noLimit")
            : t("remaining", { time: clock(Math.max(0, remaining)) })}
        </p>
        <p className="text-sm text-muted" aria-live="polite">
          {saveState === "saving" ? t("saving") : null}
          {saveState === "saved" ? t("saved") : null}
          {saveState === "failed" ? t("saveFailed") : null}
        </p>
      </div>
      {timeUp ? <Banner tone="warning" title={t("timeUp")} /> : null}
      {submit.isError && !timeUp ? (
        <Banner tone="danger" title={t("submitFailed")}>
          {errorMessage(submit.error)}
        </Banner>
      ) : null}
      <ol className="flex flex-col gap-4">
        {questions.map((question, index) => (
          <li key={question.id}>
            <QuestionBlock
              question={question}
              number={index + 1}
              total={questions.length}
              value={answers[question.id]}
              onChange={(value) => change(question.id, value)}
            />
          </li>
        ))}
      </ol>
      <div>
        <Button variant="primary" onClick={() => setConfirming(true)}>
          {t("submit")}
        </Button>
      </div>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("submitTitle")}
        consequence={[
          unanswered > 0 ? t("unanswered", { count: unanswered }) : null,
          t("submitConsequence"),
        ]
          .filter(Boolean)
          .join(" ")}
        confirmLabel={t("submit")}
        pending={submit.isPending}
        onConfirm={() => submit.mutate(answers)}
      />
      <Link className="text-sm text-primary hover:underline" href={`/quizzes/${quizId}`}>
        {t("back")}
      </Link>
    </div>
  );
}

function useCountdown(expiresAt: number | null, offset: number): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (expiresAt === null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);
  return expiresAt === null ? null : Math.ceil((expiresAt - (now + offset)) / 1000);
}

function QuestionBlock({
  question,
  number,
  total,
  value,
  onChange,
}: {
  question: Question;
  number: number;
  total: number;
  value: string | string[] | undefined;
  onChange: (value: string | string[]) => void;
}) {
  const t = useTranslations("quizzes.attempt");
  const chosen = Array.isArray(value) ? value : [];
  return (
    <Panel>
      <PanelHeader
        title={t("question", { number, total })}
        action={
          <span className="text-sm text-muted tabular">
            {t("points", { count: question.points })}
          </span>
        }
      />
      <PanelBody>
        <div className="flex flex-col gap-3">
          <p className="break-words whitespace-pre-wrap">{question.prompt}</p>
          {question.type === "mcq" ? (
            <RadioGroup
              legend={t("answerLabel")}
              value={typeof value === "string" ? value : ""}
              onValueChange={onChange}
              options={question.options.map((option) => ({ value: option.id, label: option.text }))}
            />
          ) : null}
          {question.type === "multi_select" ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="font-medium">{t("answerLabel")}</legend>
              {question.options.map((option) => (
                <Checkbox
                  key={option.id}
                  label={option.text}
                  checked={chosen.includes(option.id)}
                  onCheckedChange={(checked) =>
                    onChange(
                      checked === true
                        ? [...chosen, option.id]
                        : chosen.filter((id) => id !== option.id),
                    )
                  }
                />
              ))}
            </fieldset>
          ) : null}
          {question.type === "short_answer" ? (
            <Field label={t("answerLabel")}>
              <Textarea
                rows={4}
                maxLength={2000}
                value={typeof value === "string" ? value : ""}
                onChange={(event) => onChange(event.target.value)}
              />
            </Field>
          ) : null}
        </div>
      </PanelBody>
    </Panel>
  );
}

function Result({ attempt, quizId }: { attempt: Attempt; quizId: string }) {
  const t = useTranslations("quizzes.attempt");
  const status = attempt.status as "submitted" | "auto_submitted";
  const percent =
    attempt.score !== null && attempt.max_score
      ? Math.round((100 * attempt.score) / attempt.max_score)
      : null;
  return (
    <Panel>
      <PanelHeader title={t("resultHeading")} />
      <PanelBody>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t(`resultStatus.${status}`)}</p>
          {attempt.score !== null && attempt.max_score !== null ? (
            <p className="text-2xl font-semibold tabular">
              {t("resultScore", { score: attempt.score, max: attempt.max_score })}
              {percent !== null ? ` · ${t("resultPercent", { percent })}` : ""}
            </p>
          ) : null}
          {attempt.pending_review ? <Banner tone="info" title={t("resultPending")} /> : null}
          <div>
            <Link className="text-primary hover:underline" href={`/quizzes/${quizId}`}>
              {t("back")}
            </Link>
          </div>
        </div>
      </PanelBody>
    </Panel>
  );
}

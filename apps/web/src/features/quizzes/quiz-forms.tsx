"use client";

import { useMutation } from "@tanstack/react-query";
import { Clock3, Plus, Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

export function QuizBuilder({ courseOfferingId }: { courseOfferingId: string }) {
  const t = useTranslations("quizzes");
  const api = useApi();
  const errorMessage = useErrorMessage();
  const [quizId, setQuizId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [type, setType] = useState<"mcq" | "multi_select" | "short_answer">("mcq");
  const [answer, setAnswer] = useState("");
  const create = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/quizzes", {
          body: {
            course_offering_id: courseOfferingId,
            title,
            instructions: "",
            available_from: null,
            deadline: null,
            time_limit_seconds: 900,
            max_attempts: 1,
          },
        }),
      ),
    onSuccess: (quiz) => setQuizId(quiz.id),
  });
  const add = useMutation({
    mutationFn: async () => {
      if (!quizId) throw new Error(t("createFirst"));
      return unwrap(
        await api.POST("/api/v1/quizzes/{quiz_id}/questions", {
          params: { path: { quiz_id: quizId }, query: { position: 1 } },
          body: {
            type,
            prompt: question,
            points: 1,
            options: type === "short_answer" ? [] : [{ id: "a", label: answer }],
            correct_answer: answer,
            is_required: true,
          },
        }),
      );
    },
  });
  return (
    <Panel>
      <PanelBody>
        <div className="flex flex-col gap-4">
          {create.isError || add.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(create.error ?? add.error)}
            </Banner>
          ) : null}
          <Field label={t("title")} required>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Button variant="primary" onClick={() => create.mutate()} loading={create.isPending}>
            <Icon icon={Plus} />
            {t("create")}
          </Button>
          <Field label={t("question")} required>
            <Textarea value={question} onChange={(e) => setQuestion(e.target.value)} />
          </Field>
          <Field label={t("questionType")}>
            <Select value={type} onChange={(e) => setType(e.target.value as typeof type)}>
              <option value="mcq">{t("mcq")}</option>
              <option value="multi_select">{t("multiSelect")}</option>
              <option value="short_answer">{t("shortAnswer")}</option>
            </Select>
          </Field>
          <Field label={t("correctAnswer")}>
            <Input value={answer} onChange={(e) => setAnswer(e.target.value)} />
          </Field>
          <Button onClick={() => add.mutate()} disabled={!quizId} loading={add.isPending}>
            <Icon icon={Plus} />
            {t("addQuestion")}
          </Button>
        </div>
      </PanelBody>
    </Panel>
  );
}

export function QuizAttempt({ quizId }: { quizId: string }) {
  const t = useTranslations("quizzes");
  const api = useApi();
  const errorMessage = useErrorMessage();
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const start = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/quizzes/{quiz_id}/attempts", {
          params: { path: { quiz_id: quizId } },
        }),
      ),
    onSuccess: (attempt) => {
      setAttemptId(attempt.id);
      setExpiresAt(attempt.expires_at);
    },
  });
  const submit = useMutation({
    mutationFn: async () => {
      if (!attemptId) throw new Error(t("notStarted"));
      return unwrap(
        await api.POST("/api/v1/quiz-attempts/{attempt_id}/submit", {
          params: { path: { attempt_id: attemptId } },
          body: { answers: {} },
        }),
      );
    },
  });
  const [seconds, setSeconds] = useState<number | null>(null);
  useEffect(() => {
    if (!expiresAt) return;
    const tick = () =>
      setSeconds(Math.max(0, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 1000)));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);
  return (
    <Panel>
      <PanelBody>
        <div className="flex flex-col gap-4">
          {start.isError || submit.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(start.error ?? submit.error)}
            </Banner>
          ) : null}
          {!attemptId ? (
            <Button variant="primary" onClick={() => start.mutate()} loading={start.isPending}>
              <Icon icon={Clock3} />
              {t("start")}
            </Button>
          ) : (
            <>
              <p className="text-sm text-muted tabular">
                {t("remaining", { seconds: seconds ?? 0 })}
              </p>
              <Field label={t("answer")}>
                <Input value={answer} onChange={(e) => setAnswer(e.target.value)} />
              </Field>
              <Button variant="primary" onClick={() => submit.mutate()} loading={submit.isPending}>
                <Icon icon={Send} />
                {t("submit")}
              </Button>
            </>
          )}
        </div>
      </PanelBody>
    </Panel>
  );
}

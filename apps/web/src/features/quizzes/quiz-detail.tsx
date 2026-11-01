"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox, RadioGroup } from "@/components/ui/choice";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { formatPoints, offeringLabel, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

import { QuizFacts } from "./quizzes-list";

type Detail = components["schemas"]["QuizDetailOut"];
type Question = components["schemas"]["ManagerQuestionOut"];
type QuestionType = components["schemas"]["QuestionType"];

const TYPES: readonly QuestionType[] = ["mcq", "multi_select", "short_answer"] as const;
const LETTERS = "abcdefghij";

export function QuizPage({ id }: { id: string }) {
  const t = useTranslations("quizzes");
  const api = useApi();
  const query = useQuery({
    queryKey: ["quiz", id],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/quizzes/{quiz_id}", { params: { path: { quiz_id: id } } })),
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
  const quiz = query.data;
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelBody>
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-xl font-semibold break-words">{quiz.title}</h2>
              {quiz.can_manage ? (
                <Tag tone={quiz.published ? "success" : "neutral"}>
                  {quiz.published ? t("published") : t("draft")}
                </Tag>
              ) : null}
            </div>
            <p className="text-sm text-muted">{offeringLabel(quiz.offering)}</p>
            <QuizFacts quiz={quiz} />
            {quiz.instructions ? (
              <p className="break-words whitespace-pre-wrap">{quiz.instructions}</p>
            ) : null}
          </div>
        </PanelBody>
      </Panel>
      {quiz.can_manage ? <ManageQuiz quiz={quiz} /> : <StudentQuiz quiz={quiz} />}
    </div>
  );
}

function StudentQuiz({ quiz }: { quiz: Detail }) {
  const t = useTranslations("quizzes.student");
  const api = useApi();
  const router = useRouter();
  const errorMessage = useErrorMessage();
  const running = quiz.my_attempts.find((attempt) => attempt.status === "in_progress");
  const start = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/quizzes/{quiz_id}/attempts", {
          params: { path: { quiz_id: quiz.id } },
        }),
      ),
    onSuccess: (attempt) => router.push(`/quizzes/${quiz.id}/attempt/${attempt.id}`),
  });
  return (
    <Panel>
      <PanelHeader title={t("attempts")} />
      <PanelBody>
        <div className="flex flex-col gap-4">
          {start.isError ? (
            <Banner tone="danger" title={t("startFailed")}>
              {errorMessage(start.error)}
            </Banner>
          ) : null}
          {quiz.start_blocked ? (
            <Banner tone="info" title={t(`blocked.${quiz.start_blocked as "closed"}`)} />
          ) : null}
          <ul className="flex flex-col gap-2">
            {quiz.my_attempts.map((attempt) => (
              <li
                key={attempt.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-panel border border-border p-3"
              >
                <span className="font-medium">
                  {t("attemptRow", { number: attempt.attempt_number })}
                </span>
                <span className="flex flex-wrap items-center gap-3 text-sm tabular">
                  {attempt.score !== null && attempt.max_score !== null
                    ? t("score", {
                        score: formatPoints(attempt.score),
                        max: formatPoints(attempt.max_score),
                      })
                    : null}
                  {attempt.pending_review ? <Tag tone="warning">{t("pending")}</Tag> : null}
                  <Link
                    className="text-primary hover:underline"
                    href={`/quizzes/${quiz.id}/attempt/${attempt.id}`}
                  >
                    {t("open")}
                  </Link>
                </span>
              </li>
            ))}
          </ul>
          {quiz.can_start ? (
            <div>
              <Button variant="primary" loading={start.isPending} onClick={() => start.mutate()}>
                {running ? t("resume") : t("start")}
              </Button>
            </div>
          ) : null}
        </div>
      </PanelBody>
    </Panel>
  );
}

function ManageQuiz({ quiz }: { quiz: Detail }) {
  const t = useTranslations("quizzes");
  const questions = quiz.questions ?? [];
  return (
    <>
      <Panel>
        <PanelHeader
          title={t("builder.heading")}
          action={
            quiz.published ? (
              <Link className="text-primary hover:underline" href={`/quizzes/${quiz.id}/results`}>
                {t("results.link")}
              </Link>
            ) : undefined
          }
        />
        <PanelBody>
          <div className="flex flex-col gap-3">
            {questions.length === 0 ? <p className="text-muted">{t("builder.empty")}</p> : null}
            <ol className="flex flex-col gap-3">
              {questions.map((question) => (
                <li key={question.id}>
                  <QuestionCard quiz={quiz} question={question} />
                </li>
              ))}
            </ol>
            {!quiz.published ? <PublishButton quiz={quiz} /> : null}
          </div>
        </PanelBody>
      </Panel>
      {!quiz.published ? <AddQuestion quizId={quiz.id} /> : null}
    </>
  );
}

function QuestionCard({ quiz, question }: { quiz: Detail; question: Question }) {
  const t = useTranslations("quizzes.builder");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [removing, setRemoving] = useState(false);
  const remove = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE("/api/v1/quizzes/{quiz_id}/questions/{question_id}", {
          params: { path: { quiz_id: quiz.id, question_id: question.id } },
        }),
      ),
    onSuccess: async () => {
      setRemoving(false);
      await queryClient.invalidateQueries({ queryKey: ["quiz", quiz.id] });
    },
    onError: (error) => toast({ title: errorMessage(error), tone: "danger" }),
  });
  const correct = new Set(
    Array.isArray(question.correct_answer) ? question.correct_answer : [question.correct_answer],
  );
  return (
    <article className="flex flex-col gap-2 rounded-panel border border-border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-medium break-words">
          {question.position}. {question.prompt}
        </p>
        <span className="text-sm text-muted tabular">
          {t("points", { count: question.points })}
        </span>
      </div>
      {question.type === "short_answer" ? (
        <>
          <p className="text-sm text-muted">{t("openNote")}</p>
          {question.correct_answer ? (
            <p className="text-sm break-words">
              <span className="font-medium">{t("modelAnswer")}: </span>
              {String(question.correct_answer)}
            </p>
          ) : null}
        </>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">
          {question.options.map((option) => (
            <li key={option.id} className="flex flex-wrap items-center gap-2">
              <span className="break-words">{option.text}</span>
              {correct.has(option.id) ? <Tag tone="success">{t("correct")}</Tag> : null}
            </li>
          ))}
        </ul>
      )}
      {!quiz.published ? (
        <div>
          <Button size="dense" variant="tertiary" onClick={() => setRemoving(true)}>
            <Icon icon={Trash2} />
            {t("remove")}
          </Button>
          <ConfirmDialog
            open={removing}
            onOpenChange={setRemoving}
            title={t("removeTitle")}
            consequence={t("removeConsequence")}
            confirmLabel={t("remove")}
            destructive
            pending={remove.isPending}
            onConfirm={() => remove.mutate()}
          />
        </div>
      ) : null}
    </article>
  );
}

function PublishButton({ quiz }: { quiz: Detail }) {
  const t = useTranslations("quizzes.builder");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [confirming, setConfirming] = useState(false);
  const publish = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/quizzes/{quiz_id}/publish", {
          params: { path: { quiz_id: quiz.id } },
        }),
      ),
    onSuccess: async () => {
      setConfirming(false);
      toast({ title: t("publishDone") });
      await queryClient.invalidateQueries({ queryKey: ["quiz", quiz.id] });
      await queryClient.invalidateQueries({ queryKey: ["quizzes"] });
    },
  });
  const empty = (quiz.questions ?? []).length === 0;
  return (
    <div className="flex flex-col gap-2 border-t border-border pt-3">
      {publish.isError ? (
        <Banner tone="danger" title={t("publishFailed")}>
          {errorMessage(publish.error)}
        </Banner>
      ) : null}
      {empty ? <p className="text-sm text-muted">{t("needQuestion")}</p> : null}
      <div>
        <Button variant="primary" disabled={empty} onClick={() => setConfirming(true)}>
          {t("publish")}
        </Button>
      </div>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("publishTitle")}
        consequence={t("publishConsequence")}
        confirmLabel={t("publish")}
        pending={publish.isPending}
        onConfirm={() => publish.mutate()}
      />
    </div>
  );
}

function AddQuestion({ quizId }: { quizId: string }) {
  const t = useTranslations("quizzes.builder");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [type, setType] = useState<QuestionType>("mcq");
  const [prompt, setPrompt] = useState("");
  const [points, setPoints] = useState("1");
  const [options, setOptions] = useState(["", ""]);
  const [correct, setCorrect] = useState<number[]>([]);
  const [model, setModel] = useState("");
  const [errors, setErrors] = useState<
    Partial<Record<"prompt" | "points" | "options" | "correct", string>>
  >({});

  const add = useMutation({
    mutationFn: async () => {
      const closed = type !== "short_answer";
      const filled = options.map((text, index) => ({ id: LETTERS[index]!, text: text.trim() }));
      return unwrap(
        await api.POST("/api/v1/quizzes/{quiz_id}/questions", {
          params: { path: { quiz_id: quizId } },
          body: {
            type,
            prompt: prompt.trim(),
            points: Number(points),
            is_required: true,
            options: closed ? filled : [],
            correct_answer: !closed
              ? model.trim() || null
              : type === "mcq"
                ? LETTERS[correct[0]!]
                : correct.map((index) => LETTERS[index]!),
          },
        }),
      );
    },
    onSuccess: async () => {
      toast({ title: t("added") });
      setPrompt("");
      setOptions(["", ""]);
      setCorrect([]);
      setModel("");
      await queryClient.invalidateQueries({ queryKey: ["quiz", quizId] });
    },
  });

  const validate = () => {
    const found: typeof errors = {};
    if (!prompt.trim()) found.prompt = t("promptRequired");
    const value = Number(points);
    if (!(Number.isInteger(value) && value >= 1 && value <= 100)) found.points = t("pointsInvalid");
    if (type !== "short_answer") {
      if (options.some((text) => !text.trim())) found.options = t("optionsRequired");
      if (correct.length === 0) found.correct = t("correctRequired");
    }
    setErrors(found);
    return Object.keys(found).length === 0;
  };

  return (
    <Panel>
      <PanelHeader title={t("addHeading")} />
      <PanelBody>
        <form
          noValidate
          className="flex max-w-2xl flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (validate()) add.mutate();
          }}
        >
          {add.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(add.error)}
            </Banner>
          ) : null}
          <RadioGroup
            legend={t("type")}
            value={type}
            onValueChange={(value) => {
              setType(value as QuestionType);
              setCorrect([]);
            }}
            options={TYPES.map((value) => ({ value, label: t(`types.${value}`) }))}
          />
          <Field label={t("prompt")} error={errors.prompt} required>
            <Textarea
              rows={3}
              value={prompt}
              maxLength={5000}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </Field>
          <Field label={t("questionPoints")} error={errors.points} required>
            <Input
              inputMode="numeric"
              className="w-24 tabular"
              value={points}
              onChange={(e) => setPoints(e.target.value)}
            />
          </Field>
          {type === "short_answer" ? (
            <Field label={t("modelAnswer")} helper={t("modelHelp")}>
              <Textarea
                rows={2}
                value={model}
                maxLength={2000}
                onChange={(e) => setModel(e.target.value)}
              />
            </Field>
          ) : (
            <fieldset className="flex flex-col gap-3">
              <legend className="font-medium">{t("options")}</legend>
              {options.map((text, index) => (
                <div key={LETTERS[index]} className="flex flex-wrap items-center gap-2">
                  <Checkbox
                    label={t("correctOption", { number: index + 1 })}
                    checked={correct.includes(index)}
                    onCheckedChange={(checked) =>
                      setCorrect(
                        type === "mcq"
                          ? checked === true
                            ? [index]
                            : []
                          : checked === true
                            ? [...correct, index]
                            : correct.filter((item) => item !== index),
                      )
                    }
                  />
                  <Input
                    className="min-w-0 flex-1"
                    aria-label={t("optionText", { number: index + 1 })}
                    value={text}
                    maxLength={500}
                    onChange={(e) =>
                      setOptions(options.map((old, i) => (i === index ? e.target.value : old)))
                    }
                  />
                  {options.length > 2 ? (
                    <Button
                      size="icon-dense"
                      variant="tertiary"
                      aria-label={t("removeOption", { number: index + 1 })}
                      onClick={() => {
                        setOptions(options.filter((_, i) => i !== index));
                        setCorrect(
                          correct
                            .filter((item) => item !== index)
                            .map((item) => (item > index ? item - 1 : item)),
                        );
                      }}
                    >
                      <Icon icon={Trash2} />
                    </Button>
                  ) : null}
                </div>
              ))}
              {errors.options ? <p className="text-sm text-danger">{errors.options}</p> : null}
              {errors.correct ? <p className="text-sm text-danger">{errors.correct}</p> : null}
              {options.length < 10 ? (
                <div>
                  <Button
                    size="dense"
                    variant="secondary"
                    onClick={() => setOptions([...options, ""])}
                  >
                    <Icon icon={Plus} />
                    {t("addOption")}
                  </Button>
                </div>
              ) : null}
            </fieldset>
          )}
          <div>
            <Button type="submit" variant="primary" loading={add.isPending}>
              {t("add")}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

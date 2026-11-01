"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, CheckCircle2, ChevronDown, ChevronUp, MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag as TagLabel } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import {
  AuthorLine,
  ContentActions,
  ListState,
  TagFilter,
  TagList,
  TagPicker,
} from "./community-shared";
import type { ForumAnswer, ForumQuestion, QuestionDetail } from "./model";

const MAX_TITLE = 200;
const MAX_BODY = 20_000;
const MAX_ANSWER = 10_000;

function useAttemptKey() {
  const key = useRef(crypto.randomUUID());
  return { current: () => key.current, renew: () => (key.current = crypto.randomUUID()) };
}

export function QuestionsPage({ tag }: { tag?: string }) {
  const t = useTranslations("community");
  const api = useApi();
  const questions = useInfiniteQuery({
    queryKey: ["questions", tag ?? ""],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/forum/questions", {
          params: { query: { cursor: pageParam, tag } },
        }),
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const items = questions.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <div className="flex flex-col gap-4">
      <AskQuestion />
      <TagFilter base="/forum" active={tag} />
      <ListState
        loading={questions.isLoading}
        error={questions.error}
        empty={!questions.isLoading && !questions.isError && items.length === 0}
        emptyMessage={t("forumEmpty")}
        retry={() => void questions.refetch()}
      />
      <ul className="flex flex-col gap-4">
        {items.map((question) => (
          <li key={question.id}>
            <QuestionCard question={question} />
          </li>
        ))}
      </ul>
      {questions.hasNextPage ? (
        <Button
          variant="secondary"
          loading={questions.isFetchingNextPage}
          onClick={() => void questions.fetchNextPage()}
        >
          {t("loadMore")}
        </Button>
      ) : null}
    </div>
  );
}

function AskQuestion() {
  const t = useTranslations("community");
  const api = useApi();
  const router = useRouter();
  const errorMessage = useErrorMessage();
  const attempt = useAttemptKey();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [missing, setMissing] = useState<"title" | "body" | null>(null);

  const ask = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/forum/questions", {
          params: { header: { "Idempotency-Key": attempt.current() } },
          body: { title: title.trim(), body: body.trim(), tag_ids: tagIds },
        }),
      ),
    onSuccess: (question) => {
      attempt.renew();
      router.push(`/forum/questions/${question.id}`);
    },
  });

  if (!open) {
    return (
      <div>
        <Button variant="primary" onClick={() => setOpen(true)}>
          <Icon icon={MessageSquarePlus} />
          {t("askQuestion")}
        </Button>
      </div>
    );
  }
  return (
    <Panel>
      <PanelBody>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (title.trim().length < 3) return setMissing("title");
            if (!body.trim()) return setMissing("body");
            ask.mutate();
          }}
        >
          {ask.isError ? (
            <Banner tone="danger" title={t("askFailed")}>
              {errorMessage(ask.error)}
            </Banner>
          ) : null}
          <Field
            label={t("questionTitleLabel")}
            error={missing === "title" ? t("questionTitleRequired") : undefined}
            required
          >
            <Input
              value={title}
              maxLength={MAX_TITLE}
              onChange={(event) => {
                setTitle(event.target.value);
                setMissing(null);
              }}
            />
          </Field>
          <Field
            label={t("questionBodyLabel")}
            error={missing === "body" ? t("questionBodyRequired") : undefined}
            required
          >
            <Textarea
              value={body}
              rows={5}
              maxLength={MAX_BODY}
              onChange={(event) => {
                setBody(event.target.value);
                setMissing(null);
              }}
            />
          </Field>
          <TagPicker selected={tagIds} onChange={setTagIds} />
          <div className="flex gap-2">
            <Button type="submit" variant="primary" loading={ask.isPending}>
              {t("askSubmit")}
            </Button>
            <Button variant="tertiary" onClick={() => setOpen(false)}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

export function QuestionCard({ question }: { question: ForumQuestion }) {
  const t = useTranslations("community");
  return (
    <Panel>
      <PanelBody>
        <article className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">
            <Link className="text-primary hover:underline" href={`/forum/questions/${question.id}`}>
              {question.title}
            </Link>
          </h2>
          <p className="line-clamp-2 break-words text-muted">{question.excerpt}</p>
          <TagList tags={question.tags} base="/forum" />
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
            <span>{question.author?.display_name ?? t("deletedUser")}</span>
            <span className="tabular">{t("answerCount", { count: question.answer_count })}</span>
            {question.accepted ? (
              <TagLabel tone="success" icon={CheckCircle2}>
                {t("accepted")}
              </TagLabel>
            ) : null}
            {question.teacher_verified ? (
              <TagLabel tone="info" icon={BadgeCheck}>
                {t("teacherVerified")}
              </TagLabel>
            ) : null}
            {question.hidden ? <TagLabel tone="warning">{t("hiddenTag")}</TagLabel> : null}
          </div>
        </article>
      </PanelBody>
    </Panel>
  );
}

export function QuestionPage({ id, canModerate }: { id: string; canModerate: boolean }) {
  const t = useTranslations("community");
  const api = useApi();
  const query = useQuery({
    queryKey: ["question", id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/forum/questions/{question_id}", {
          params: { path: { question_id: id } },
        }),
      ),
  });
  if (!query.data) {
    return (
      <ListState
        loading={query.isLoading}
        error={query.error}
        empty={false}
        emptyMessage={t("forumEmpty")}
        retry={() => void query.refetch()}
      />
    );
  }
  return <QuestionDetailView question={query.data} canModerate={canModerate} />;
}

function QuestionDetailView({
  question,
  canModerate,
}: {
  question: QuestionDetail;
  canModerate: boolean;
}) {
  const t = useTranslations("community");
  const router = useRouter();
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelBody>
          <article className="flex flex-col gap-3">
            <h2 className="text-xl font-semibold break-words">{question.title}</h2>
            <AuthorLine
              author={question.author}
              createdAt={question.created_at}
              hidden={question.hidden}
            />
            <p className="break-words whitespace-pre-wrap">{question.body}</p>
            <TagList tags={question.tags} base="/forum" />
            {question.teacher_verified ? (
              <div>
                <TagLabel tone="info" icon={BadgeCheck}>
                  {t("teacherVerified")}
                </TagLabel>
              </div>
            ) : null}
            <ContentActions
              kind="question"
              id={question.id}
              mine={question.mine}
              hidden={question.hidden}
              canModerate={canModerate}
              invalidate={["question", "questions"]}
              onDeleted={() => router.push("/forum")}
            />
          </article>
        </PanelBody>
      </Panel>
      <section className="flex flex-col gap-3" aria-labelledby="answers-heading">
        <h2 id="answers-heading" className="text-lg font-semibold">
          {t("answersHeading", { count: question.answers.length })}
        </h2>
        {question.answers.length === 0 ? <p className="text-muted">{t("answersEmpty")}</p> : null}
        <ul className="flex flex-col gap-3">
          {question.answers.map((answer) => (
            <li key={answer.id}>
              <AnswerCard answer={answer} question={question} canModerate={canModerate} />
            </li>
          ))}
        </ul>
      </section>
      <AnswerComposer questionId={question.id} />
    </div>
  );
}

export function AnswerCard({
  answer,
  question,
  canModerate,
}: {
  answer: ForumAnswer;
  question: QuestionDetail;
  canModerate: boolean;
}) {
  const t = useTranslations("community");
  const api = useApi();
  const queryClient = useQueryClient();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["question", question.id] });
  const fail = (error: unknown) => toast({ title: errorMessage(error), tone: "danger" });

  const vote = useMutation({
    mutationFn: async (value: -1 | 0 | 1) =>
      unwrap(
        await api.PUT("/api/v1/forum/answers/{answer_id}/vote", {
          params: { path: { answer_id: answer.id }, query: { value } },
        }),
      ),
    onSuccess: refresh,
    onError: fail,
  });
  const accept = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/forum/questions/{question_id}/accepted-answer", {
          params: { path: { question_id: question.id } },
          body: { answer_id: answer.accepted ? null : answer.id },
        }),
      ),
    onSuccess: refresh,
    onError: fail,
  });
  const verify = useMutation({
    mutationFn: async () => {
      const params = { path: { answer_id: answer.id } };
      return unwrap(
        answer.verified_by
          ? await api.DELETE("/api/v1/forum/answers/{answer_id}/verification", { params })
          : await api.PUT("/api/v1/forum/answers/{answer_id}/verification", { params }),
      );
    },
    onSuccess: refresh,
    onError: fail,
  });

  return (
    <Panel>
      <PanelBody>
        <article className="flex gap-3">
          <div
            className="flex shrink-0 flex-col items-center gap-1"
            role="group"
            aria-label={t("voteGroup")}
          >
            <Button
              size="icon-dense"
              variant={answer.my_vote === 1 ? "primary" : "secondary"}
              aria-label={t("voteUp")}
              aria-pressed={answer.my_vote === 1}
              disabled={answer.mine || vote.isPending}
              onClick={() => vote.mutate(answer.my_vote === 1 ? 0 : 1)}
            >
              <Icon icon={ChevronUp} />
            </Button>
            <span className="font-medium tabular" aria-label={t("score", { score: answer.score })}>
              {answer.score}
            </span>
            <Button
              size="icon-dense"
              variant={answer.my_vote === -1 ? "primary" : "secondary"}
              aria-label={t("voteDown")}
              aria-pressed={answer.my_vote === -1}
              disabled={answer.mine || vote.isPending}
              onClick={() => vote.mutate(answer.my_vote === -1 ? 0 : -1)}
            >
              <Icon icon={ChevronDown} />
            </Button>
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <AuthorLine
              author={answer.author}
              createdAt={answer.created_at}
              hidden={answer.hidden}
            />
            <p className="break-words whitespace-pre-wrap">{answer.body}</p>
            <div className="flex flex-wrap items-center gap-2">
              {answer.accepted ? (
                <TagLabel tone="success" icon={CheckCircle2}>
                  {t("accepted")}
                </TagLabel>
              ) : null}
              {answer.verified_by ? (
                <TagLabel tone="info" icon={BadgeCheck}>
                  {t("verifiedBy", { name: answer.verified_by.display_name })}
                </TagLabel>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {question.mine ? (
                <Button
                  size="dense"
                  variant="secondary"
                  loading={accept.isPending}
                  onClick={() => accept.mutate()}
                >
                  {answer.accepted ? t("unaccept") : t("accept")}
                </Button>
              ) : null}
              {question.can_verify ? (
                <Button
                  size="dense"
                  variant="secondary"
                  loading={verify.isPending}
                  onClick={() => verify.mutate()}
                >
                  {answer.verified_by ? t("unverify") : t("verify")}
                </Button>
              ) : null}
              <ContentActions
                kind="answer"
                id={answer.id}
                mine={answer.mine}
                hidden={answer.hidden}
                canModerate={canModerate}
                invalidate={["question", "questions"]}
              />
            </div>
          </div>
        </article>
      </PanelBody>
    </Panel>
  );
}

function AnswerComposer({ questionId }: { questionId: string }) {
  const t = useTranslations("community");
  const api = useApi();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const attempt = useAttemptKey();
  const [body, setBody] = useState("");
  const [missing, setMissing] = useState(false);
  const send = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/forum/questions/{question_id}/answers", {
          params: {
            path: { question_id: questionId },
            header: { "Idempotency-Key": attempt.current() },
          },
          body: { body: body.trim() },
        }),
      ),
    onSuccess: async () => {
      attempt.renew();
      setBody("");
      await queryClient.invalidateQueries({ queryKey: ["question", questionId] });
    },
  });
  return (
    <Panel>
      <PanelBody>
        <form
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!body.trim()) return setMissing(true);
            send.mutate();
          }}
        >
          {send.isError ? (
            <Banner tone="danger" title={t("answerFailed")}>
              {errorMessage(send.error)}
            </Banner>
          ) : null}
          <Field label={t("answerLabel")} error={missing ? t("answerRequired") : undefined}>
            <Textarea
              value={body}
              rows={4}
              maxLength={MAX_ANSWER}
              onChange={(event) => {
                setBody(event.target.value);
                setMissing(false);
              }}
            />
          </Field>
          <div>
            <Button type="submit" variant="primary" loading={send.isPending}>
              {t("answerSubmit")}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

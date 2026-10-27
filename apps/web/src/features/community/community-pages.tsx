"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, MessageCircle, ThumbsUp, TriangleAlert, Users } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { communityApi } from "./api";
import type { FeedPost, ForumQuestion, QuestionDetail } from "./model";

function State({
  loading,
  error,
  forbidden = false,
  empty,
  retry,
}: {
  loading: boolean;
  error: boolean;
  forbidden?: boolean;
  empty: boolean;
  retry: () => void;
}) {
  const t = useTranslations("community");
  if (loading)
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    );
  if (forbidden) return <ForbiddenState />;
  if (error)
    return (
      <Panel>
        <EmptyState
          icon={TriangleAlert}
          message={t("error")}
          action={<Button onClick={retry}>{t("retry")}</Button>}
        />
      </Panel>
    );
  if (empty)
    return (
      <Panel>
        <EmptyState icon={Users} message={t("empty")} />
      </Panel>
    );
  return null;
}

function Tags({ tags }: { tags: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Link key={tag} href={`/forum/tags/${encodeURIComponent(tag)}`}>
          <Tag>{tag}</Tag>
        </Link>
      ))}
    </div>
  );
}

export function FeedPage() {
  const t = useTranslations("community");
  const query = useQuery({ queryKey: ["feed"], queryFn: communityApi.feed });
  const state = (
    <State
      loading={query.isLoading}
      error={query.isError && (query.error as { status?: number } | null)?.status !== 403}
      forbidden={(query.error as { status?: number } | null)?.status === 403}
      empty={!query.isLoading && !query.isError && !query.data?.items.length}
      retry={() => void query.refetch()}
    />
  );
  return (
    <div className="flex flex-col gap-4">
      {state}
      {query.data?.items.map((post) => (
        <FeedCard key={post.id} post={post} />
      ))}
      {query.data?.next_cursor ? <TextLink href="/feed">{t("loadMore")}</TextLink> : null}
    </div>
  );
}

function FeedCard({ post }: { post: FeedPost }) {
  const t = useTranslations("community");
  return (
    <Panel>
      <PanelBody>
        <article className="flex flex-col gap-3">
          <div className="flex flex-wrap justify-between gap-2">
            <p className="font-medium">{post.author_name ?? t("user")}</p>
            <time className="text-sm text-muted" dateTime={post.created_at}>
              {new Date(post.created_at).toLocaleDateString("az-AZ")}
            </time>
          </div>
          <p className="break-words whitespace-pre-wrap">{post.body}</p>
          <Tags tags={post.tags} />
          <div className="flex flex-wrap gap-4 text-sm text-muted">
            <span>
              <Icon icon={ThumbsUp} /> {post.useful_count} {t("useful")}
            </span>
            <span>
              <Icon icon={MessageCircle} /> {post.comment_count} {t("comments")}
            </span>
          </div>
        </article>
      </PanelBody>
    </Panel>
  );
}

export function QuestionsPage({ tag }: { tag?: string }) {
  const t = useTranslations("community");
  const query = useQuery({
    queryKey: ["questions", tag],
    queryFn: () => communityApi.questions(tag),
  });
  const state = (
    <State
      loading={query.isLoading}
      error={query.isError && (query.error as { status?: number } | null)?.status !== 403}
      forbidden={(query.error as { status?: number } | null)?.status === 403}
      empty={!query.isLoading && !query.isError && !query.data?.items.length}
      retry={() => void query.refetch()}
    />
  );
  return (
    <div className="flex flex-col gap-4">
      {state}
      {query.data?.items.map((question) => (
        <QuestionCard key={question.id} question={question} />
      ))}
      {query.data?.next_cursor ? (
        <TextLink href={tag ? `/forum/tags/${tag}` : "/forum"}>{t("loadMore")}</TextLink>
      ) : null}
    </div>
  );
}

function QuestionCard({ question }: { question: ForumQuestion }) {
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
          <p className="line-clamp-2 text-muted">{question.excerpt ?? question.body}</p>
          <Tags tags={question.tags} />
          <div className="flex flex-wrap gap-3 text-sm text-muted">
            <span>
              {question.vote_count ?? 0} {t("votes")}
            </span>
            <span>
              {question.answer_count ?? 0} {t("answers")}
            </span>
            {question.accepted ? (
              <span className="inline-flex items-center gap-1 text-success">
                <Icon icon={CheckCircle2} />
                {t("accepted")}
              </span>
            ) : null}
            {question.teacher_verified ? <Tag>{t("teacherVerified")}</Tag> : null}
          </div>
        </article>
      </PanelBody>
    </Panel>
  );
}

export function QuestionPage({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["question", id], queryFn: () => communityApi.question(id) });
  if (query.isLoading)
    return <State loading error={false} empty={false} retry={() => void query.refetch()} />;
  if (query.isError || !query.data)
    return (
      <State
        loading={false}
        error={(query.error as { status?: number } | null)?.status !== 403}
        forbidden={(query.error as { status?: number } | null)?.status === 403}
        empty={false}
        retry={() => void query.refetch()}
      />
    );
  return <QuestionDetailView question={query.data} />;
}

function QuestionDetailView({ question }: { question: QuestionDetail }) {
  const t = useTranslations("community");
  const [promoting, setPromoting] = useState(false);
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelBody>
          <article className="flex flex-col gap-3">
            <h1 className="text-2xl font-semibold">{question.title}</h1>
            <p className="break-words whitespace-pre-wrap">{question.body}</p>
            <Tags tags={question.tags} />
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
              <span>{question.author_name ?? t("user")}</span>
              {question.teacher_verified ? <Tag>{t("teacherVerified")}</Tag> : null}
            </div>
            <Button variant="secondary" onClick={() => setPromoting(!promoting)}>
              {t("promoteFromChat")}
            </Button>
            {promoting ? <p className="text-sm text-muted">{t("promoteHint")}</p> : null}
          </article>
        </PanelBody>
      </Panel>
      <section className="flex flex-col gap-3" aria-labelledby="answers-heading">
        <h2 id="answers-heading" className="text-xl font-semibold">
          {t("answers")}
        </h2>
        {question.answers.map((answer) => (
          <Panel key={answer.id}>
            <PanelHeader
              title={answer.author_name ?? t("user")}
              action={answer.accepted ? <Tag>{t("accepted")}</Tag> : undefined}
            />
            <PanelBody>
              <p className="break-words whitespace-pre-wrap">{answer.body}</p>
            </PanelBody>
          </Panel>
        ))}
      </section>
    </div>
  );
}

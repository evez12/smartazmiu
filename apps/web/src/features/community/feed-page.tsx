"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, Send, ThumbsUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
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
import type { FeedComment, FeedPost } from "./model";

const MAX_POST = 10_000;
const MAX_COMMENT = 4_000;

/** One Idempotency-Key per attempt: a double click or a retry returns the first result, a new text gets a new key. */
function useAttemptKey() {
  const key = useRef(crypto.randomUUID());
  return { current: () => key.current, renew: () => (key.current = crypto.randomUUID()) };
}

export function FeedPage({ canModerate, tag }: { canModerate: boolean; tag?: string }) {
  const t = useTranslations("community");
  const api = useApi();
  const posts = useInfiniteQuery({
    queryKey: ["feed", tag ?? ""],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/feed/posts", {
          params: { query: { cursor: pageParam, tag } },
        }),
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const items = posts.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <div className="flex flex-col gap-4">
      <PostComposer />
      <TagFilter base="/feed" active={tag} />
      <ListState
        loading={posts.isLoading}
        error={posts.error}
        empty={!posts.isLoading && !posts.isError && items.length === 0}
        emptyMessage={t("feedEmpty")}
        retry={() => void posts.refetch()}
      />
      <ul className="flex flex-col gap-4">
        {items.map((post) => (
          <li key={post.id}>
            <PostCard post={post} canModerate={canModerate} />
          </li>
        ))}
      </ul>
      {posts.hasNextPage ? (
        <Button
          variant="secondary"
          loading={posts.isFetchingNextPage}
          onClick={() => void posts.fetchNextPage()}
        >
          {t("loadMore")}
        </Button>
      ) : null}
    </div>
  );
}

function PostComposer() {
  const t = useTranslations("community");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const attempt = useAttemptKey();
  const [body, setBody] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [missing, setMissing] = useState(false);

  const publish = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/feed/posts", {
          params: { header: { "Idempotency-Key": attempt.current() } },
          body: { body: body.trim(), tag_ids: tagIds },
        }),
      ),
    onSuccess: async () => {
      attempt.renew();
      setBody("");
      setTagIds([]);
      toast({ title: t("postPublished") });
      await queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
  });

  return (
    <Panel>
      <PanelBody>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!body.trim()) {
              setMissing(true);
              return;
            }
            publish.mutate();
          }}
        >
          {publish.isError ? (
            <Banner tone="danger" title={t("postFailed")}>
              {errorMessage(publish.error)}
            </Banner>
          ) : null}
          <Field
            label={t("postLabel")}
            helper={t("postHelper", { max: MAX_POST })}
            error={missing ? t("postRequired") : undefined}
          >
            <Textarea
              value={body}
              rows={3}
              maxLength={MAX_POST}
              onChange={(event) => {
                setBody(event.target.value);
                setMissing(false);
              }}
            />
          </Field>
          <TagPicker selected={tagIds} onChange={setTagIds} />
          <div>
            <Button type="submit" variant="primary" loading={publish.isPending}>
              <Icon icon={Send} />
              {t("publish")}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

function PostCard({ post, canModerate }: { post: FeedPost; canModerate: boolean }) {
  const t = useTranslations("community");
  const api = useApi();
  const queryClient = useQueryClient();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [open, setOpen] = useState(false);

  const helpful = useMutation({
    mutationFn: async () => {
      const params = { path: { post_id: post.id } };
      return unwrap(
        post.my_helpful
          ? await api.DELETE("/api/v1/feed/posts/{post_id}/helpful", { params })
          : await api.PUT("/api/v1/feed/posts/{post_id}/helpful", { params }),
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feed"] }),
    onError: (error) => toast({ title: errorMessage(error), tone: "danger" }),
  });

  return (
    <Panel>
      <PanelBody>
        <article
          className="flex flex-col gap-3"
          aria-label={t("postBy", { name: post.author?.display_name ?? t("deletedUser") })}
        >
          <AuthorLine author={post.author} createdAt={post.created_at} hidden={post.hidden} />
          <p className="break-words whitespace-pre-wrap">{post.body}</p>
          <TagList tags={post.tags} base="/feed" />
          <div className="flex flex-wrap items-center gap-2">
            {post.mine ? (
              <span className="inline-flex items-center gap-1 text-sm text-muted tabular">
                <Icon icon={ThumbsUp} /> {t("helpfulCount", { count: post.helpful_count })}
              </span>
            ) : (
              <Button
                size="dense"
                variant={post.my_helpful ? "primary" : "secondary"}
                aria-pressed={post.my_helpful}
                loading={helpful.isPending}
                onClick={() => helpful.mutate()}
              >
                <Icon icon={ThumbsUp} />
                {t("helpfulButton")} · <span className="tabular">{post.helpful_count}</span>
              </Button>
            )}
            <Button
              size="dense"
              variant="secondary"
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              <Icon icon={MessageCircle} />
              {t("commentsButton", { count: post.comment_count })}
            </Button>
            <ContentActions
              kind="post"
              id={post.id}
              mine={post.mine}
              hidden={post.hidden}
              canModerate={canModerate}
              invalidate={["feed"]}
            />
          </div>
          {open ? <Comments postId={post.id} canModerate={canModerate} /> : null}
        </article>
      </PanelBody>
    </Panel>
  );
}

function Comments({ postId, canModerate }: { postId: string; canModerate: boolean }) {
  const t = useTranslations("community");
  const api = useApi();
  const comments = useInfiniteQuery({
    queryKey: ["feed-comments", postId],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/feed/posts/{post_id}/comments", {
          params: { path: { post_id: postId }, query: { after: pageParam } },
        }),
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const items = comments.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section
      aria-label={t("commentsLabel")}
      className="flex flex-col gap-3 border-t border-border pt-3"
    >
      {comments.isLoading ? <Skeleton className="h-12 w-full" /> : null}
      {comments.isError ? (
        <Banner tone="danger" title={t("commentsFailed")}>
          <Button size="dense" onClick={() => void comments.refetch()}>
            {t("retry")}
          </Button>
        </Banner>
      ) : null}
      {!comments.isLoading && !comments.isError && items.length === 0 ? (
        <p className="text-muted">{t("commentsEmpty")}</p>
      ) : null}
      <ul className="flex flex-col gap-3">
        {items.map((comment) => (
          <li key={comment.id}>
            <CommentRow comment={comment} canModerate={canModerate} />
          </li>
        ))}
      </ul>
      {comments.hasNextPage ? (
        <Button
          size="dense"
          variant="secondary"
          loading={comments.isFetchingNextPage}
          onClick={() => void comments.fetchNextPage()}
        >
          {t("loadMore")}
        </Button>
      ) : null}
      <CommentComposer postId={postId} />
    </section>
  );
}

function CommentRow({ comment, canModerate }: { comment: FeedComment; canModerate: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <AuthorLine author={comment.author} createdAt={comment.created_at} hidden={comment.hidden} />
      <p className="break-words whitespace-pre-wrap">{comment.body}</p>
      <ContentActions
        kind="comment"
        id={comment.id}
        mine={comment.mine}
        hidden={comment.hidden}
        canModerate={canModerate}
        invalidate={["feed-comments", "feed"]}
      />
    </div>
  );
}

function CommentComposer({ postId }: { postId: string }) {
  const t = useTranslations("community");
  const api = useApi();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const attempt = useAttemptKey();
  const [body, setBody] = useState("");
  const send = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/feed/posts/{post_id}/comments", {
          params: { path: { post_id: postId }, header: { "Idempotency-Key": attempt.current() } },
          body: { body: body.trim() },
        }),
      ),
    onSuccess: async () => {
      attempt.renew();
      setBody("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["feed-comments", postId] }),
        queryClient.invalidateQueries({ queryKey: ["feed"] }),
      ]);
    },
  });
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (body.trim()) send.mutate();
      }}
    >
      {send.isError ? (
        <Banner tone="danger" title={t("commentFailed")}>
          {errorMessage(send.error)}
        </Banner>
      ) : null}
      <Field label={t("commentLabel")}>
        <Textarea
          value={body}
          rows={2}
          maxLength={MAX_COMMENT}
          onChange={(event) => setBody(event.target.value)}
        />
      </Field>
      <div>
        <Button type="submit" variant="secondary" loading={send.isPending} disabled={!body.trim()}>
          {t("commentSend")}
        </Button>
      </div>
    </form>
  );
}

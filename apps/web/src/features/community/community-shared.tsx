"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff, Flag, Trash2, TriangleAlert, Users } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/choice";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag as TagLabel } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { ReportDialog } from "@/features/reports/report-dialog";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { formatDateTime } from "@/lib/format";

import { MAX_TAGS, type ContentKind, type Tag } from "./model";

type Author = components["schemas"]["AuthorOut"] | null;

export function isForbidden(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 403;
}

/** Loading, forbidden, error (with retry) and empty states shared by every list and detail screen (§13.6). */
export function ListState({
  loading,
  error,
  empty,
  emptyMessage,
  retry,
}: {
  loading: boolean;
  error: unknown;
  empty: boolean;
  emptyMessage: string;
  retry: () => void;
}) {
  const t = useTranslations("community");
  if (loading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    );
  }
  if (error) {
    if (isForbidden(error)) return <ForbiddenState />;
    return (
      <Panel>
        <EmptyState
          icon={TriangleAlert}
          message={t("error")}
          action={<Button onClick={retry}>{t("retry")}</Button>}
        />
      </Panel>
    );
  }
  if (empty) {
    return (
      <Panel>
        <EmptyState icon={Users} message={emptyMessage} />
      </Panel>
    );
  }
  return null;
}

function useTags() {
  const api = useApi();
  return useQuery({
    queryKey: ["community-tags"],
    queryFn: async () => unwrap(await api.GET("/api/v1/community/tags")).items,
    staleTime: 5 * 60_000,
  });
}

export function TagList({ tags, base }: { tags: Tag[]; base: string }) {
  const t = useTranslations("community");
  if (!tags.length) return null;
  return (
    <ul className="flex flex-wrap gap-1" aria-label={t("tagsLabel")}>
      {tags.map((tag) => (
        <li key={tag.id}>
          <Link href={`${base}?tag=${encodeURIComponent(tag.slug)}`}>
            <TagLabel>{tag.name}</TagLabel>
          </Link>
        </li>
      ))}
    </ul>
  );
}

const FILTER_LINK =
  "inline-flex min-h-8 items-center rounded-control border border-border px-2 text-sm aria-[current=page]:border-primary aria-[current=page]:font-medium pointer-coarse:min-h-11";

/** Filters a list by one tag; the same control clears the filter. */
export function TagFilter({ base, active }: { base: string; active?: string }) {
  const t = useTranslations("community");
  const tags = useTags();
  if (!tags.data?.length) return null;
  return (
    <nav aria-label={t("tagFilter")} className="flex flex-wrap gap-2">
      <Link href={base} aria-current={active ? undefined : "page"} className={FILTER_LINK}>
        {t("allTags")}
      </Link>
      {tags.data.map((tag) => (
        <Link
          key={tag.id}
          href={`${base}?tag=${encodeURIComponent(tag.slug)}`}
          aria-current={tag.slug === active ? "page" : undefined}
          className={FILTER_LINK}
        >
          {tag.name}
        </Link>
      ))}
    </nav>
  );
}

/** Up to five tags from the fixed catalogue, as checkboxes: nobody invents tags. */
export function TagPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const t = useTranslations("community");
  const tags = useTags();
  if (!tags.data?.length) return null;
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="font-medium">{t("tagsLegend", { max: MAX_TAGS })}</legend>
      <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
        {tags.data.map((tag) => {
          const checked = selected.includes(tag.id);
          return (
            <Checkbox
              key={tag.id}
              label={tag.name}
              checked={checked}
              disabled={!checked && selected.length >= MAX_TAGS}
              onCheckedChange={(next) =>
                onChange(
                  next === true ? [...selected, tag.id] : selected.filter((id) => id !== tag.id),
                )
              }
            />
          );
        })}
      </div>
    </fieldset>
  );
}

export function AuthorLine({
  author,
  createdAt,
  hidden,
}: {
  author: Author;
  createdAt: string;
  hidden: boolean;
}) {
  const t = useTranslations("community");
  const name = author?.display_name ?? t("deletedUser");
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Avatar name={name} src={author?.photo_url ?? undefined} size={32} decorative />
      <span className="font-medium">{name}</span>
      {author?.badge === "teacher" ? <TagLabel tone="info">{t("teacher")}</TagLabel> : null}
      <time className="text-sm text-muted tabular" dateTime={createdAt}>
        {formatDateTime(createdAt)}
      </time>
      {hidden ? (
        <TagLabel tone="warning" icon={EyeOff}>
          {t("hiddenTag")}
        </TagLabel>
      ) : null}
    </div>
  );
}

const DELETE_PATHS = {
  post: "/api/v1/feed/posts/{post_id}",
  comment: "/api/v1/feed/comments/{comment_id}",
  question: "/api/v1/forum/questions/{question_id}",
  answer: "/api/v1/forum/answers/{answer_id}",
} as const;

/** Report, delete (own) and hide or restore (staff) for one item; each is a separate, explained step. */
export function ContentActions({
  kind,
  id,
  mine,
  hidden,
  canModerate,
  invalidate,
  onDeleted,
}: {
  kind: ContentKind;
  id: string;
  mine: boolean;
  hidden: boolean;
  canModerate: boolean;
  /** Query keys to refetch after a change. */
  invalidate: string[];
  /** Called after a delete, so a detail page can leave the removed question. */
  onDeleted?: () => void;
}) {
  const t = useTranslations("community");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [reporting, setReporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const refresh = () =>
    Promise.all(invalidate.map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
  const remove = useMutation({
    mutationFn: async () => {
      // The four delete routes differ only in the name of the path parameter.
      const result = await api.DELETE(DELETE_PATHS[kind] as "/api/v1/feed/posts/{post_id}", {
        params: { path: { [`${kind}_id`]: id } as { post_id: string } },
      });
      return unwrap(result);
    },
    onSuccess: async () => {
      setDeleting(false);
      toast({ title: t("deleted") });
      await refresh();
      onDeleted?.();
    },
  });
  const visibility = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/community/{kind}/{item_id}/visibility", {
          params: { path: { kind, item_id: id } },
          body: { hidden: !hidden },
        }),
      ),
    onSuccess: async () => {
      toast({ title: hidden ? t("shownDone") : t("hiddenDone") });
      await refresh();
    },
    onError: (error) => toast({ title: errorMessage(error), tone: "danger" }),
  });

  return (
    <div className="flex flex-wrap items-center gap-2">
      {mine ? (
        <Button size="dense" variant="tertiary" onClick={() => setDeleting(true)}>
          <Icon icon={Trash2} />
          {t("delete")}
        </Button>
      ) : (
        <Button size="dense" variant="tertiary" onClick={() => setReporting(true)}>
          <Icon icon={Flag} />
          {t("report")}
        </Button>
      )}
      {canModerate ? (
        <Button
          size="dense"
          variant="tertiary"
          loading={visibility.isPending}
          onClick={() => visibility.mutate()}
        >
          <Icon icon={EyeOff} />
          {hidden ? t("show") : t("hide")}
        </Button>
      ) : null}
      {remove.isError ? (
        <Banner tone="danger" title={t("deleteFailed")}>
          {errorMessage(remove.error)}
        </Banner>
      ) : null}
      <ReportDialog open={reporting} onOpenChange={setReporting} targetType={kind} targetId={id} />
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t("deleteTitle")}
        consequence={t("deleteConsequence")}
        confirmLabel={t("delete")}
        destructive
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

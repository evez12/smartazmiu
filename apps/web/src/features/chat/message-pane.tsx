"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Users, X } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Checkbox } from "@/components/ui/choice";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import { Composer } from "./composer";
import { MemberSheet } from "./member-sheet";
import { MessageList } from "./message-list";
import { buildTimeline, chatKeys, newestId, PAGE_SIZE } from "./model";
import { NotifyMenu } from "./notify-menu";
import { StudentAdviceDisclaimer } from "@/features/mentorship/disclaimer";
import { ChannelRequests } from "@/features/mentorship/request-list";

import { PollButton } from "./poll-dialog";
import { PostingBanner } from "./posting";
import { UsefulButton } from "./useful-sheet";
import { FALLBACK_POLL_MS, useChannels, useChatRuntime, useChatState, useMembers } from "./runtime";
import type { PageDirection } from "./store";

/** One channel: header, history, typing line, the posting banner and the composer (§12.7). */
export function MessagePane({
  channelId,
  currentUserName,
  onOpenThread,
}: {
  channelId: string;
  currentUserName: string;
  onOpenThread: (rootId: string) => void;
}) {
  const t = useTranslations("chat");
  const tGuides = useTranslations("guides");
  const api = useApi();
  const runtime = useChatRuntime();
  const channels = useChannels();
  const [membersOpen, setMembersOpen] = useState(false);
  const [loading, setLoading] = useState<Exclude<PageDirection, "latest"> | null>(null);
  const [historyFailed, setHistoryFailed] = useState(false);
  // Course and community channels have topics (§5.1); null shows every message.
  const [topicId, setTopicId] = useState<string | null>(null);
  const [anonymous, setAnonymous] = useState(false);
  const atBottom = useRef(true);

  const detail = useQuery({
    queryKey: chatKeys.channel(channelId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/chat/channels/{channel_id}", {
          params: { path: { channel_id: channelId } },
        }),
      ),
    retry: (count, error) =>
      !(error instanceof ApiRequestError && error.status === 404) && count < 1,
  });
  const status = useChatState((state) => state.status);
  const history = useChatState((state) => state.windows[channelId]);
  const allPending = useChatState((state) => state.pending);
  const typing = useChatState((state) => state.typing[channelId]);
  const revoked = useChatState((state) => state.revoked === channelId);
  const notices = useChatState((state) => state.notices[channelId]);
  const members = useMembers(channelId);
  const listed = channels.data?.channels.find((channel) => channel.id === channelId);
  const channel = detail.data ?? listed;

  const load = useCallback(
    async (direction: Exclude<PageDirection, "latest">) => {
      const current = runtime.store.getState().windows[channelId];
      const ids = Object.keys(current?.messages ?? {});
      const query: { limit: number; before?: string; after?: string } = { limit: PAGE_SIZE };
      if (direction === "older") {
        const oldest = ids.reduce<string | null>(
          (min, id) => (min === null || BigInt(id) < BigInt(min) ? id : min),
          null,
        );
        if (!oldest) return;
        query.before = oldest;
      }
      if (direction === "newer") {
        const newest = newestId(ids);
        if (!newest) return;
        query.after = newest;
      }
      if (direction === "unread") {
        const marker = listed?.last_read_message_id;
        if (!marker) return;
        query.after = marker;
      }
      setLoading(direction);
      try {
        const page = unwrap(
          await api.GET("/api/v1/chat/channels/{channel_id}/messages", {
            params: { path: { channel_id: channelId }, query },
          }),
        );
        runtime.store.getState().loadPage(channelId, page, direction);
        setHistoryFailed(false);
      } catch {
        setHistoryFailed(true);
      } finally {
        setLoading(null);
      }
    },
    [api, channelId, listed?.last_read_message_id, runtime.store],
  );

  useEffect(() => {
    runtime.setActiveChannel(channelId);
    return () => runtime.setActiveChannel(null);
  }, [channelId, runtime]);

  const truncated = history?.truncated ?? false;
  const needsLatest = !history || (truncated && Object.keys(history.messages).length === 0);
  // The newest page, once per channel and again after a reconnect gap too large to replay (§13.2).
  const latest = useQuery({
    queryKey: [...chatKeys.channel(channelId), "latest", truncated],
    queryFn: async () => {
      const page = unwrap(
        await api.GET("/api/v1/chat/channels/{channel_id}/messages", {
          params: { path: { channel_id: channelId }, query: { limit: PAGE_SIZE } },
        }),
      );
      runtime.store.getState().loadPage(channelId, page, "latest");
      return page.messages.length;
    },
    enabled: needsLatest,
    staleTime: Infinity,
    gcTime: 0,
  });
  const loaded = !needsLatest;

  // Without the socket the open channel is polled through REST (§13.5).
  useEffect(() => {
    if (status === "online") return;
    const timer = setInterval(() => {
      if (!runtime.store.getState().windows[channelId]?.hasNewer) void load("newer");
    }, FALLBACK_POLL_MS);
    return () => clearInterval(timer);
  }, [channelId, load, runtime.store, status]);

  const messages = useMemo(
    () =>
      Object.values(history?.messages ?? {}).filter(
        (message) => topicId === null || message.topic_id === topicId,
      ),
    [history?.messages, topicId],
  );
  const pending = useMemo(
    () =>
      Object.values(allPending).filter(
        (item) => item.channelId === channelId && (topicId === null || item.topicId === topicId),
      ),
    [allPending, channelId, topicId],
  );
  const topics = detail.data?.topics ?? [];
  const activeTopic = topics.find((topic) => topic.id === topicId);
  // Anonymous questions only as new posts in #suallar (§5.3); the server checks the channel type too.
  const anonymousAllowed = activeTopic?.slug === "suallar";
  const asAnonymous = anonymousAllowed && anonymous;
  // The divider stays where the read marker was when the channel opened, even after it moves on (§12.7).
  const [frozenMarker, setFrozenMarker] = useState<string | null | undefined>(undefined);
  if (frozenMarker === undefined && listed) setFrozenMarker(listed.last_read_message_id);
  const items = useMemo(
    () =>
      buildTimeline(messages, pending, {
        lastReadId: frozenMarker ?? null,
        currentUserId: runtime.currentUserId,
      }),
    [frozenMarker, messages, pending, runtime.currentUserId],
  );
  const blockedIds = useMemo(
    () => new Set(channels.data?.blocked_user_ids ?? []),
    [channels.data?.blocked_user_ids],
  );

  const newest = newestId(messages.map((message) => message.id));
  const markRead = useCallback(() => {
    if (
      newest &&
      atBottom.current &&
      !history?.hasNewer &&
      document.visibilityState === "visible"
    ) {
      runtime.markRead(channelId, newest);
    }
  }, [channelId, newest, runtime, history?.hasNewer]);
  useEffect(() => {
    markRead();
    document.addEventListener("visibilitychange", markRead);
    return () => document.removeEventListener("visibilitychange", markRead);
  }, [markRead]);

  if (revoked) {
    return (
      <div className="flex flex-1 flex-col items-start gap-3 p-6">
        <Banner tone="info" title={t("revoked")}>
          <Link href="/chat" className={buttonVariants({ size: "dense" })}>
            {t("revokedAction")}
          </Link>
        </Banner>
      </div>
    );
  }
  if (detail.isError && detail.error instanceof ApiRequestError && detail.error.status === 404) {
    return (
      <div className="flex-1 p-6">
        <EmptyState
          message={t("notFound")}
          action={
            <Link href="/chat" className={buttonVariants({ size: "dense" })}>
              {t("back")}
            </Link>
          }
        />
      </div>
    );
  }

  const typists = Object.values(typing ?? {}).map((typist) => typist.name);
  return (
    <section aria-labelledby="chat-channel-title" className="flex min-h-0 min-w-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-2 lg:px-4">
        <Link
          href="/chat"
          aria-label={t("back")}
          className={buttonVariants({
            variant: "tertiary",
            size: "icon",
            className: "text-text lg:hidden",
          })}
        >
          <Icon icon={ArrowLeft} size={20} />
        </Link>
        <div className="flex min-w-0 flex-1 flex-col">
          {channel ? (
            <>
              <h2 id="chat-channel-title" className="truncate font-semibold" title={channel.name}>
                {channel.name}
              </h2>
              {channel.context ? (
                <p className="truncate text-xs text-muted tabular">{channel.context}</p>
              ) : null}
            </>
          ) : (
            <Skeleton className="h-4 w-40" />
          )}
        </div>
        <UsefulButton channelId={channelId} currentUserId={runtime.currentUserId} />
        {listed ? <NotifyMenu channel={listed} /> : null}
        <Button variant="tertiary" size="dense" onClick={() => setMembersOpen(true)}>
          <Icon icon={Users} />
          <span className="max-sm:sr-only">{t("members")}</span>
        </Button>
      </header>

      {topics.length > 0 ? (
        <nav
          aria-label={t("topics.label")}
          className="flex shrink-0 gap-1 overflow-x-auto border-b border-border px-2 py-1 lg:px-4"
        >
          {[{ id: null, name: t("topics.all") }, ...topics].map((topic) => (
            <button
              key={topic.id ?? "all"}
              type="button"
              aria-pressed={topicId === topic.id}
              onClick={() => setTopicId(topic.id)}
              className={buttonVariants({
                variant: topicId === topic.id ? "secondary" : "tertiary",
                size: "dense",
                className: "shrink-0",
              })}
            >
              {topic.id ? `#${topic.name}` : topic.name}
            </button>
          ))}
        </nav>
      ) : null}
      {activeTopic?.slug === "materiallar" && detail.data?.subject_id ? (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-bg-subtle px-4 py-2 text-sm">
          <span>{tGuides("materialsHint")}</span>
          <Link
            href={`/materials/${detail.data.subject_id}`}
            className={buttonVariants({ size: "dense" })}
          >
            {tGuides("materialsLink")}
          </Link>
        </div>
      ) : null}
      {activeTopic?.slug === "meslehet" ? (
        <div className="border-b border-border px-4 py-2">
          <StudentAdviceDisclaimer />
        </div>
      ) : null}
      {channel?.type === "dm" ? <ChannelRequests channelId={channelId} /> : null}

      {truncated && listed?.last_read_message_id ? (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-bg-subtle px-4 py-2 text-sm">
          <span>{t("gapTooLarge")}</span>
          <Button size="dense" onClick={() => void load("unread")}>
            {t("jumpToUnread")}
          </Button>
        </div>
      ) : null}

      {!loaded && !latest.isError ? (
        <div aria-busy="true" className="flex flex-1 flex-col justify-end gap-4 p-4">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index} className="flex gap-3">
              <Skeleton className="size-8 shrink-0 rounded-full" />
              <SkeletonText lines={2} className="flex-1" />
            </div>
          ))}
        </div>
      ) : (latest.isError || historyFailed) && messages.length === 0 ? (
        <div className="flex flex-1 flex-col items-start gap-2 p-4">
          <p className="text-sm text-muted">{t("historyFailed")}</p>
          <Button size="dense" onClick={() => void latest.refetch()}>
            {t("retry")}
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-1 items-end p-4">
          <EmptyState className="py-0" message={t("emptyChannel")} />
        </div>
      ) : (
        <MessageList
          label={t("messagesLabel", { channel: channel?.name ?? "" })}
          items={items}
          hasOlder={history?.hasOlder ?? false}
          hasNewer={history?.hasNewer ?? false}
          loadingOlder={loading === "older"}
          onLoadOlder={() => void load("older")}
          onLoadNewer={() => void load("newer")}
          onBottomChange={(bottom) => {
            atBottom.current = bottom;
            if (bottom) markRead();
          }}
          context={{
            currentUser: { id: runtime.currentUserId, name: currentUserName },
            canPost: channel?.posting.allowed ?? false,
            members: members.data ?? [],
            onOpenThread,
            capabilities: detail.data
              ? {
                  canPin: detail.data.can_pin,
                  canVerify: detail.data.can_verify,
                  canSeeAnonymous: detail.data.can_see_anonymous,
                }
              : undefined,
          }}
          blockedIds={blockedIds}
          onRetry={runtime.retry}
        />
      )}

      <p aria-live="polite" className="h-5 shrink-0 px-4 text-xs text-muted">
        {typists.length === 0
          ? null
          : typists.length > 2
            ? t("typingMany")
            : t("typing", { names: typists.join(", ") })}
      </p>
      {notices?.includes("chat.channel_mention_not_allowed") ? (
        <div
          role="status"
          className="flex items-start justify-between gap-2 border-t border-border bg-bg-subtle px-4 py-2 text-sm"
        >
          <span>{t("notices.channelMention")}</span>
          <Button
            variant="tertiary"
            size="icon-dense"
            aria-label={t("cancel")}
            onClick={() => runtime.store.getState().setNotices(channelId, [])}
          >
            <Icon icon={X} />
          </Button>
        </div>
      ) : null}
      {channel ? <PostingBanner posting={channel.posting} /> : null}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 pt-1">
        <PollButton channelId={channelId} topicId={topicId} disabled={!channel?.posting.allowed} />
        {anonymousAllowed ? (
          <Checkbox
            checked={anonymous}
            onCheckedChange={(checked) => setAnonymous(checked === true)}
            label={t("anonymousToggle")}
            description={t("anonymousHint")}
          />
        ) : null}
      </div>
      <Composer
        label={t("composerLabel")}
        placeholder={t("composerPlaceholder", { channel: channel?.name ?? "" })}
        disabled={!channel?.posting.allowed}
        members={members.data}
        currentUserId={runtime.currentUserId}
        attachTo={channelId}
        onSend={(body, attachmentIds) => {
          atBottom.current = true;
          runtime.send(
            channelId,
            body,
            undefined,
            attachmentIds,
            topicId ?? undefined,
            asAnonymous,
          );
        }}
        // An anonymous question must not announce who is typing it.
        onTyping={() => (asAnonymous ? undefined : runtime.typing(channelId))}
      />
      <MemberSheet channelId={channelId} open={membersOpen} onOpenChange={setMembersOpen} />
    </section>
  );
}

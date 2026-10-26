"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HandHelping } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button, buttonVariants } from "@/components/ui/button";
import { RadioGroup } from "@/components/ui/choice";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Textarea } from "@/components/ui/field";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { formatDateTime } from "@/lib/format";

import { StudentAdviceDisclaimer } from "./disclaimer";
import { mentorshipKeys, STATUS_TONE, type MentorRequest } from "./model";

/** Every request I sent, received or could take (the "Məsləhət sorğuları" page). */
export function RequestList() {
  const t = useTranslations("guides");
  const api = useApi();
  const requests = useQuery({
    queryKey: mentorshipKeys.requests,
    queryFn: async () => unwrap(await api.GET("/api/v1/mentor-requests")).items,
  });
  if (requests.isPending) {
    return (
      <div role="status" className="flex flex-col gap-4">
        <span className="sr-only">{t("requestsTitle")}</span>
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (requests.isError) return <Banner tone="danger" title={t("loadFailed")} />;
  if (requests.data.length === 0) {
    return (
      <Panel className="px-4">
        <EmptyState
          icon={HandHelping}
          message={t("requestsEmpty")}
          action={
            <Link href="/guides" className={buttonVariants({ variant: "secondary" })}>
              {t("findTitle")}
            </Link>
          }
        />
      </Panel>
    );
  }
  return (
    <ul className="flex flex-col gap-4" aria-label={t("requestsTitle")}>
      {requests.data.map((request) => (
        <li key={request.id}>
          <RequestCard request={request} />
        </li>
      ))}
    </ul>
  );
}

/** The request header of a DM opened by an accepted request (§5.2); nothing for other DMs. */
export function ChannelRequests({ channelId }: { channelId: string }) {
  const api = useApi();
  const requests = useQuery({
    queryKey: mentorshipKeys.channel(channelId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/mentor-requests", { params: { query: { channel_id: channelId } } }),
      ).items,
  });
  const live = (requests.data ?? []).filter(
    (request) => request.status === "accepted" || request.can_give_feedback,
  );
  if (live.length === 0) return null;
  return (
    <div className="flex flex-col gap-2 border-b border-border p-3">
      {live.map((request) => (
        <RequestCard key={request.id} request={request} compact />
      ))}
    </div>
  );
}

function RequestCard({ request, compact = false }: { request: MentorRequest; compact?: boolean }) {
  const t = useTranslations("guides.request");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const act = useMutation({
    mutationFn: async (action: "accept" | "decline" | "resolve") => {
      const path = `/api/v1/mentor-requests/{request_id}/${action}` as const;
      return unwrap(await api.POST(path, { params: { path: { request_id: request.id } } }));
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["mentorship"] }),
    onError: (error) =>
      toast({ title: t("actionFailed"), description: errorMessage(error), tone: "danger" }),
  });
  const counterpart =
    request.role === "requester"
      ? request.mentor
        ? t("guide", { name: request.mentor.display_name })
        : t("anyGuide")
      : t("from", { name: request.requester.display_name });
  return (
    <Panel aria-label={t("cardLabel", { subject: request.subject_name })}>
      <PanelBody className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{request.subject_name}</span>
          <Tag tone="neutral">{t(`topics.${request.topic}`)}</Tag>
          <Tag tone={STATUS_TONE[request.status]}>{t(`status.${request.status}`)}</Tag>
        </div>
        <p className="text-sm text-muted">{counterpart}</p>
        {compact ? null : <p className="break-words whitespace-pre-wrap">{request.body}</p>}
        {request.expires_at ? (
          <p className="text-sm text-muted">
            {t("expires", { date: formatDateTime(request.expires_at) })}
          </p>
        ) : null}
        <StudentAdviceDisclaimer />
        <div className="flex flex-wrap gap-2">
          {request.can_accept ? (
            <Button variant="primary" loading={act.isPending} onClick={() => act.mutate("accept")}>
              {t("accept")}
            </Button>
          ) : null}
          {request.can_decline ? (
            <Button variant="secondary" onClick={() => act.mutate("decline")}>
              {t("decline")}
            </Button>
          ) : null}
          {request.can_resolve ? (
            <Button variant="secondary" onClick={() => act.mutate("resolve")}>
              {t("resolve")}
            </Button>
          ) : null}
          {!compact && request.dm_channel_id && request.status === "accepted" ? (
            <Link
              href={`/chat/${request.dm_channel_id}`}
              className={buttonVariants({ variant: "tertiary" })}
            >
              {t("openChat")}
            </Link>
          ) : null}
        </div>
        {request.can_give_feedback ? <FeedbackForm requestId={request.id} /> : null}
        {request.feedback ? (
          <p className="text-sm text-muted">
            {t("feedbackGiven", {
              feedback: t(request.feedback === "helpful" ? "helpful" : "notHelpful"),
            })}
          </p>
        ) : null}
      </PanelBody>
    </Panel>
  );
}

function FeedbackForm({ requestId }: { requestId: string }) {
  const t = useTranslations("guides.request");
  const api = useApi();
  const errorMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState<"helpful" | "not_helpful">("helpful");
  const [note, setNote] = useState("");
  const send = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/mentor-requests/{request_id}/feedback", {
          params: { path: { request_id: requestId } },
          body: { feedback, note: note.trim() },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["mentorship"] }),
  });
  return (
    <div className="flex flex-col gap-3 border-t border-border pt-3">
      {send.isError ? (
        <Banner tone="danger" title={t("actionFailed")}>
          {errorMessage(send.error)}
        </Banner>
      ) : null}
      <RadioGroup
        legend={t("feedbackTitle")}
        value={feedback}
        onValueChange={(value) => setFeedback(value as "helpful" | "not_helpful")}
        options={[
          { value: "helpful", label: t("helpful") },
          { value: "not_helpful", label: t("notHelpful") },
        ]}
      />
      <Field label={t("feedbackNote")}>
        <Textarea
          value={note}
          maxLength={1000}
          rows={2}
          onChange={(event) => setNote(event.target.value)}
        />
      </Field>
      <div>
        <Button variant="primary" loading={send.isPending} onClick={() => send.mutate()}>
          {t("feedbackSend")}
        </Button>
      </div>
    </div>
  );
}

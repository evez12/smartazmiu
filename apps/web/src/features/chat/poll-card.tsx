"use client";

import { useMutation } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { formatDateTime } from "@/lib/format";

import type { ChatMessage } from "./model";
import { useOptionalChatRuntime } from "./runtime";

type Poll = NonNullable<ChatMessage["poll"]>;

/** Results as bars with counts in text (colour is never the only carrier, §12), and the vote form. */
export function PollCard({
  message,
  poll,
  canVote,
}: {
  message: ChatMessage;
  poll: Poll;
  canVote: boolean;
}) {
  const t = useTranslations("chat.poll");
  const tChat = useTranslations("chat");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const runtime = useOptionalChatRuntime();
  const mine = poll.my_votes ?? [];
  const [chosen, setChosen] = useState<string[]>(mine);
  const vote = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/chat/polls/{poll_id}/votes", {
          params: { path: { poll_id: poll.id } },
          body: { option_ids: chosen },
        }),
      ),
    onSuccess: (updated) => runtime?.store.getState().update(updated),
    onError: (error) =>
      toast({ title: tChat("actionFailed"), description: errorMessage(error), tone: "danger" }),
  });
  const total = poll.options.reduce((sum, option) => sum + option.votes, 0);
  const open = !poll.closed && canVote;
  return (
    <fieldset
      className="mt-2 flex max-w-md flex-col gap-2 rounded-control border border-border p-3"
      aria-label={t("label", { question: message.body })}
    >
      <legend className="sr-only">{message.body}</legend>
      {poll.options.map((option) => {
        const share = total ? Math.round((option.votes / total) * 100) : 0;
        const selected = chosen.includes(option.id);
        return (
          <label key={option.id} className="flex flex-col gap-1 text-sm">
            <span className="flex items-center gap-2">
              {open ? (
                <input
                  type={poll.multi ? "checkbox" : "radio"}
                  name={`poll-${poll.id}`}
                  checked={selected}
                  onChange={(event) =>
                    setChosen((current) =>
                      poll.multi
                        ? event.target.checked
                          ? [...current, option.id]
                          : current.filter((id) => id !== option.id)
                        : [option.id],
                    )
                  }
                  className="size-4 accent-primary"
                />
              ) : null}
              <span className="flex flex-1 items-center gap-1 break-words">
                {option.text}
                {mine.includes(option.id) ? (
                  <Icon icon={Check} label={t("myChoice")} className="text-primary" />
                ) : null}
              </span>
              <span className="text-muted tabular">
                {t("votes", { count: option.votes })} · {share}%
              </span>
            </span>
            <span aria-hidden className="h-1.5 w-full rounded-control bg-bg-subtle">
              <span
                className="block h-full rounded-control bg-primary"
                style={{ width: `${share}%` }}
              />
            </span>
          </label>
        );
      })}
      <p className="flex flex-wrap gap-x-3 text-xs text-muted tabular">
        <span>{t("voters", { count: poll.voters })}</span>
        {poll.closed ? (
          <span>{t("closed")}</span>
        ) : poll.closes_at ? (
          <span>{t("closesOn", { date: formatDateTime(poll.closes_at) })}</span>
        ) : null}
      </p>
      {open ? (
        <div>
          <Button
            size="dense"
            variant="secondary"
            loading={vote.isPending}
            disabled={chosen.length === 0}
            onClick={() => vote.mutate()}
          >
            {t("vote")}
          </Button>
        </div>
      ) : null}
    </fieldset>
  );
}

"use client";

import { useMutation } from "@tanstack/react-query";
import { BarChart3, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/choice";
import { Field, Input } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { useOptionalChatRuntime } from "./runtime";

const MAX_OPTIONS = 10;

/** Creates a poll in the channel (and topic) the person is looking at (§5.3). */
export function PollButton({
  channelId,
  topicId,
  disabled,
}: {
  channelId: string;
  topicId: string | null;
  disabled: boolean;
}) {
  const t = useTranslations("chat.poll");
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="tertiary" size="dense" disabled={disabled} onClick={() => setOpen(true)}>
        <Icon icon={BarChart3} />
        {t("create")}
      </Button>
      {open ? <PollDialog channelId={channelId} topicId={topicId} onOpenChange={setOpen} /> : null}
    </>
  );
}

function PollDialog({
  channelId,
  topicId,
  onOpenChange,
}: {
  channelId: string;
  topicId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("chat.poll");
  const api = useApi();
  const runtime = useOptionalChatRuntime();
  const errorMessage = useErrorMessage();
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState(["", ""]);
  const [multi, setMulti] = useState(false);
  const [closesAt, setClosesAt] = useState("");
  const [invalid, setInvalid] = useState(false);
  const cleaned = options.map((option) => option.trim()).filter(Boolean);
  const valid =
    question.trim() !== "" && cleaned.length >= 2 && new Set(cleaned).size === cleaned.length;
  const create = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/chat/channels/{channel_id}/polls", {
          params: { path: { channel_id: channelId } },
          body: {
            question: question.trim(),
            client_msg_id: crypto.randomUUID(),
            topic_id: topicId,
            options: cleaned,
            multi,
            closes_at: closesAt ? new Date(closesAt).toISOString() : null,
          },
        }),
      ),
    onSuccess: (message) => {
      runtime?.store.getState().receive(message);
      onOpenChange(false);
    },
  });
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent
        title={t("title")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={create.isPending}
              onClick={() => {
                if (!valid) {
                  setInvalid(true);
                  return;
                }
                create.mutate();
              }}
            >
              {t("submit")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {create.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(create.error)}
            </Banner>
          ) : null}
          {invalid && !valid ? <Banner tone="warning" title={t("invalid")} /> : null}
          <Field label={t("question")} required>
            <Input value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} />
          </Field>
          {options.map((option, index) => (
            <div key={index} className="flex items-end gap-2">
              <Field label={t("option", { n: index + 1 })} className="flex-1">
                <Input
                  value={option}
                  maxLength={200}
                  onChange={(e) =>
                    setOptions((current) =>
                      current.map((value, i) => (i === index ? e.target.value : value)),
                    )
                  }
                />
              </Field>
              {options.length > 2 ? (
                <Button
                  variant="tertiary"
                  size="icon"
                  aria-label={t("removeOption", { n: index + 1 })}
                  onClick={() => setOptions((current) => current.filter((_, i) => i !== index))}
                >
                  <Icon icon={X} />
                </Button>
              ) : null}
            </div>
          ))}
          {options.length < MAX_OPTIONS ? (
            <div>
              <Button variant="secondary" size="dense" onClick={() => setOptions([...options, ""])}>
                {t("addOption")}
              </Button>
            </div>
          ) : null}
          <Checkbox
            checked={multi}
            onCheckedChange={(checked) => setMulti(checked === true)}
            label={t("multi")}
          />
          <Field label={t("closesAt")} helper={t("closesAtHelper")}>
            <Input
              type="datetime-local"
              value={closesAt}
              onChange={(e) => setClosesAt(e.target.value)}
            />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

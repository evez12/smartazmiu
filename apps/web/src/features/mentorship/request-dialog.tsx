"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { StudentAdviceDisclaimer } from "./disclaimer";
import { MAX_REQUEST_BODY, mentorshipKeys, TOPICS, type RequestTopic } from "./model";

type Guide = { id: string; display_name: string };

/** Asks one guide, or every available guide of the subject when ``guide`` is absent (D-004). */
export function RequestButton({
  subjectId,
  guide,
  variant = "secondary",
}: {
  subjectId: string;
  guide?: Guide;
  variant?: "primary" | "secondary";
}) {
  const t = useTranslations("guides");
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant={variant} onClick={() => setOpen(true)}>
        {guide ? t("directory.ask") : t("directory.askAny")}
      </Button>
      {open ? <RequestDialog subjectId={subjectId} guide={guide} onOpenChange={setOpen} /> : null}
    </>
  );
}

function RequestDialog({
  subjectId,
  guide,
  onOpenChange,
}: {
  subjectId: string;
  guide?: Guide;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("guides.request");
  const tCommon = useTranslations("feedback");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [topic, setTopic] = useState<RequestTopic>("exam");
  const [body, setBody] = useState("");
  const [missing, setMissing] = useState(false);
  const send = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/mentor-requests", {
          body: { subject_id: subjectId, mentor_id: guide?.id ?? null, topic, body: body.trim() },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: mentorshipKeys.requests });
      onOpenChange(false);
      toast({ title: t("sent") });
    },
  });
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent
        title={t("title")}
        description={guide ? t("toGuide", { name: guide.display_name }) : t("toAny")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{tCommon("cancel")}</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={send.isPending}
              onClick={() => {
                if (!body.trim()) {
                  setMissing(true);
                  return;
                }
                send.mutate();
              }}
            >
              {t("send")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <StudentAdviceDisclaimer />
          {send.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(send.error)}
            </Banner>
          ) : null}
          <Field label={t("topic")} required>
            <Select
              value={topic}
              onChange={(event) => setTopic(event.target.value as RequestTopic)}
            >
              {TOPICS.map((value) => (
                <option key={value} value={value}>
                  {t(`topics.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label={t("body")}
            helper={t("bodyHelper")}
            error={missing ? t("bodyRequired") : undefined}
            required
          >
            <Textarea
              value={body}
              maxLength={MAX_REQUEST_BODY}
              rows={5}
              onChange={(event) => {
                setBody(event.target.value);
                setMissing(false);
              }}
            />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { TagPicker } from "./community-shared";

const MAX_TITLE = 200;

/**
 * Republishes the author's own chat question in the forum, where it stays searchable (§8 Sprint 12). The server
 * accepts only the author's visible, non-anonymous top-level message (D-090), so this is offered for those only.
 */
export function PromoteDialog({
  open,
  onOpenChange,
  channelId,
  messageId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channelId: string;
  messageId: string;
}) {
  const t = useTranslations("community");
  const api = useApi();
  const router = useRouter();
  const errorMessage = useErrorMessage();
  const [title, setTitle] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [missing, setMissing] = useState(false);

  const promote = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/chat/channels/{channel_id}/messages/{message_id}/promote", {
          params: { path: { channel_id: channelId, message_id: Number(messageId) } },
          body: { title: title.trim(), tag_ids: tagIds },
        }),
      ),
    onSuccess: (question) => {
      onOpenChange(false);
      router.push(`/forum/questions/${question.id}`);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={t("promoteTitle")}
        description={t("promoteDescription")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={promote.isPending}
              onClick={() => {
                if (title.trim().length < 3) return setMissing(true);
                promote.mutate();
              }}
            >
              {t("promoteSubmit")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {promote.isError ? (
            <Banner tone="danger" title={t("promoteFailed")}>
              {errorMessage(promote.error)}
            </Banner>
          ) : null}
          <Field
            label={t("questionTitleLabel")}
            error={missing ? t("questionTitleRequired") : undefined}
            required
          >
            <Input
              value={title}
              maxLength={MAX_TITLE}
              onChange={(event) => {
                setTitle(event.target.value);
                setMissing(false);
              }}
            />
          </Field>
          <TagPicker selected={tagIds} onChange={setTagIds} />
        </div>
      </DialogContent>
    </Dialog>
  );
}

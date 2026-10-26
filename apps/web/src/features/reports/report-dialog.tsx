"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { RadioGroup } from "@/components/ui/choice";
import { Field, Textarea } from "@/components/ui/field";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

export type ReportTarget = components["schemas"]["ReportIn"]["target_type"];
type Reason = components["schemas"]["ReportIn"]["reason"];

export const REASONS: readonly Reason[] = [
  "spam",
  "harassment",
  "hate",
  "exam_leak",
  "privacy",
  "other",
] as const;
const MAX_NOTE = 500;

/** Report a message or a person (§5.4); a second report of the same target changes nothing (§5.5). */
export function ReportDialog({
  open,
  onOpenChange,
  targetType,
  targetId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetType: ReportTarget;
  targetId: string;
}) {
  const t = useTranslations("reports");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [reason, setReason] = useState<Reason | "">("");
  const [note, setNote] = useState("");
  const [missingReason, setMissingReason] = useState(false);

  const send = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/reports", {
          body: { target_type: targetType, target_id: targetId, reason: reason as Reason, note },
        }),
      ),
    onSuccess: (result) => {
      onOpenChange(false);
      toast({ title: result.duplicate ? t("alreadyReported") : t("sent") });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={targetType === "message" ? t("titleMessage") : t("titleUser")}
        description={t("description")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={send.isPending}
              onClick={() => {
                if (!reason) {
                  setMissingReason(true);
                  return;
                }
                send.mutate();
              }}
            >
              {t("submit")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {send.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(send.error)}
            </Banner>
          ) : null}
          <RadioGroup
            legend={t("reasonLegend")}
            value={reason}
            onValueChange={(value) => {
              setReason(value as Reason);
              setMissingReason(false);
            }}
            options={REASONS.map((value) => ({
              value,
              label: t(`reasons.${value}`),
              description: value === "exam_leak" ? t("examLeakHint") : undefined,
            }))}
            aria-invalid={missingReason || undefined}
          />
          {missingReason ? (
            <p role="alert" className="text-sm text-danger">
              {t("reasonRequired")}
            </p>
          ) : null}
          <Field label={t("note")} helper={t("noteHelper", { max: MAX_NOTE })}>
            <Textarea
              value={note}
              maxLength={MAX_NOTE}
              rows={3}
              onChange={(event) => setNote(event.target.value)}
            />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

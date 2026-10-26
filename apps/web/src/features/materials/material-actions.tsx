"use client";

import { useMutation } from "@tanstack/react-query";
import { Flag } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { RadioGroup } from "@/components/ui/choice";
import { Field, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog, Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

type Reason = components["schemas"]["MaterialReportIn"]["reason"];

const REASONS: readonly Reason[] = [
  "copyright",
  "wrong_content",
  "inappropriate",
  "other",
] as const;
const MAX_NOTE = 500;

/** Report a material, and for staff hide or show it again (§6.1, D-071). */
export function MaterialActions({
  materialId,
  hidden,
  canManage,
}: {
  materialId: string;
  hidden: boolean;
  canManage: boolean;
}) {
  const t = useTranslations("materials");
  const [reporting, setReporting] = useState(false);
  return (
    <span className="flex flex-wrap gap-2">
      <Button variant="tertiary" onClick={() => setReporting(true)}>
        <Icon icon={Flag} />
        {t("report.action")}
      </Button>
      {canManage ? <VisibilityButton materialId={materialId} hidden={hidden} /> : null}
      {reporting ? (
        <MaterialReportDialog
          materialId={materialId}
          open={reporting}
          onOpenChange={setReporting}
        />
      ) : null}
    </span>
  );
}

function VisibilityButton({ materialId, hidden }: { materialId: string; hidden: boolean }) {
  const t = useTranslations("materials");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const change = useMutation({
    mutationFn: async (hide: boolean) =>
      unwrap(
        await api.PATCH("/api/v1/materials/{material_id}/visibility", {
          params: { path: { material_id: materialId } },
          body: { hidden: hide },
        }),
      ),
    onSuccess: (_, hide) => {
      setConfirming(false);
      toast({ title: hide ? t("hiddenToast") : t("shownToast") });
      router.refresh();
    },
    onError: () => toast({ title: t("visibilityFailed"), tone: "danger" }),
  });
  if (hidden) {
    return (
      <Button loading={change.isPending} onClick={() => change.mutate(false)}>
        {t("show")}
      </Button>
    );
  }
  return (
    <>
      <Button variant="destructive" onClick={() => setConfirming(true)}>
        {t("hide")}
      </Button>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("hideTitle")}
        consequence={t("hideConsequence")}
        confirmLabel={t("hide")}
        onConfirm={() => change.mutate(true)}
        destructive
        pending={change.isPending}
      />
    </>
  );
}

function MaterialReportDialog({
  materialId,
  open,
  onOpenChange,
}: {
  materialId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("materials.report");
  const tReports = useTranslations("reports");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [reason, setReason] = useState<Reason | "">("");
  const [note, setNote] = useState("");
  const [missingReason, setMissingReason] = useState(false);

  const send = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/materials/{material_id}/reports", {
          params: { path: { material_id: materialId } },
          body: { reason: reason as Reason, note },
        }),
      ),
    onSuccess: (result) => {
      onOpenChange(false);
      toast({ title: result.duplicate ? tReports("alreadyReported") : tReports("sent") });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={t("title")}
        description={t("description")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{tReports("cancel")}</Button>
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
              {tReports("submit")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {send.isError ? (
            <Banner tone="danger" title={tReports("failed")}>
              {errorMessage(send.error)}
            </Banner>
          ) : null}
          <RadioGroup
            legend={tReports("reasonLegend")}
            value={reason}
            onValueChange={(value) => {
              setReason(value as Reason);
              setMissingReason(false);
            }}
            options={REASONS.map((value) => ({ value, label: t(`reasons.${value}`) }))}
            aria-invalid={missingReason || undefined}
          />
          {missingReason ? (
            <p role="alert" className="text-sm text-danger">
              {tReports("reasonRequired")}
            </p>
          ) : null}
          <Field label={tReports("note")} helper={tReports("noteHelper", { max: MAX_NOTE })}>
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

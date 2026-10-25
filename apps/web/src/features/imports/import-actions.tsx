"use client";

import { useMutation } from "@tanstack/react-query";
import { CircleCheck, Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { useIssueText } from "./issue-text";
import { issueReport, type ImportDetail, type ImportIssue } from "./model";

/** The single primary action of a ready preview; confirms with the exact consequence first (§12.4). */
export function ApplyImportButton({ record }: { record: ImportDetail }) {
  const t = useTranslations("imports.detail");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [open, setOpen] = useState(false);

  const apply = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/admin/imports/{import_id}/apply", {
          params: { path: { import_id: record.id } },
        }),
      ),
    onSuccess: (result) => {
      setOpen(false);
      if (result.status === "applied") toast({ title: t("appliedToast") });
      router.refresh();
    },
    onError: () => setOpen(false),
  });

  return (
    <div className="flex flex-col items-end gap-2">
      <Button variant="primary" onClick={() => setOpen(true)} loading={apply.isPending}>
        <Icon icon={CircleCheck} />
        {t("apply")}
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={t("confirmTitle")}
        consequence={t("confirmConsequence", record.summary)}
        confirmLabel={t("apply")}
        pending={apply.isPending}
        onConfirm={() => apply.mutate()}
      />
      {apply.isError ? (
        <Banner tone="danger" title={errorMessage(apply.error)} className="max-w-md" />
      ) : null}
    </div>
  );
}

export function DownloadReportButton({
  fileName,
  issues,
}: {
  fileName: string;
  issues: ImportIssue[];
}) {
  const t = useTranslations("imports");
  const issueText = useIssueText();
  const download = () => {
    const report = issueReport(
      issues,
      {
        row: t("detail.row"),
        column: t("detail.column"),
        problem: t("detail.problem"),
        wholeFile: t("detail.wholeFile"),
      },
      issueText,
    );
    const url = URL.createObjectURL(new Blob([report], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${fileName.replace(/\.[^.]+$/, "")}-xetalar.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <Button size="dense" onClick={download}>
      <Icon icon={Download} />
      {t("detail.downloadReport")}
    </Button>
  );
}

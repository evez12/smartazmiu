"use client";

import { useMutation } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { formatDateTime } from "@/lib/format";
import { formatSize } from "@/lib/uploads";

export type SubmissionFile = components["schemas"]["SubmissionFileOut"];

const TONE = {
  pending: "neutral",
  clean: "success",
  infected: "danger",
  failed: "danger",
} as const;

/** The files of one submission, newest first; only a scanned file can be downloaded (§14, D-092). */
export function SubmissionFiles({ files }: { files: SubmissionFile[] }) {
  const t = useTranslations("assignments.submission");
  const api = useApi();
  const toast = useToast();
  const open = useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.GET("/api/v1/assignment-files/{file_id}/download", {
          params: { path: { file_id: id } },
        }),
      ),
    onSuccess: (link) => window.location.assign(link.url),
    onError: () => toast({ title: t("downloadFailed"), tone: "danger" }),
  });
  return (
    <section aria-label={t("versions")}>
      <ul className="flex flex-col gap-2">
        {files.map((file) => (
          <li
            key={file.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-panel border border-border p-3"
          >
            <div className="flex min-w-0 flex-col gap-1">
              <span className="font-medium break-all">{file.filename}</span>
              <span className="text-sm text-muted tabular">
                {t("version", { number: file.version })} · {formatSize(file.size_bytes)} ·{" "}
                {formatDateTime(file.created_at)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Tag tone={TONE[file.status]}>{t(`fileStatus.${file.status}`)}</Tag>
              {file.status === "clean" ? (
                <Button
                  size="dense"
                  variant="secondary"
                  aria-label={t("download", { name: file.filename })}
                  loading={open.isPending && open.variables === file.id}
                  onClick={() => open.mutate(file.id)}
                >
                  <Icon icon={Download} />
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, FileArchive, FileText, Loader, Presentation, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useOptionalApi } from "@/lib/api/provider";

import type { ChatMessage } from "./model";
import { formatSize } from "@/lib/uploads";

export type Attachment = ChatMessage["attachments"][number];

// Download links live one minute on the server; they are re-requested a little before that.
const LINK_STALE_MS = 45_000;

type ErrorKey = Parameters<ReturnType<typeof useTranslations<"chat.attachments.errors">>>[0];

const ERROR_KEYS: Record<string, ErrorKey> = {
  "chat.attachment_type_not_allowed": "typeNotAllowed",
  "chat.attachment_too_large": "tooLarge",
  "chat.attachments_not_allowed": "notAllowed",
  "chat.attachments_unavailable": "unavailable",
  "chat.too_many_attachments": "tooMany",
  "chat.attachment_not_found": "notFound",
  "chat.attachment_not_uploaded": "notUploaded",
  "chat.attachment_size_mismatch": "sizeMismatch",
  "chat.exam_mode": "examMode",
  "request.rate_limited": "rateLimited",
};

export function useAttachmentErrorText(): (code: string | undefined) => string {
  const t = useTranslations("chat.attachments.errors");
  return (code) => t((code && ERROR_KEYS[code]) || "generic");
}

function useLink(attachment: Attachment, inline: boolean, enabled: boolean) {
  const api = useOptionalApi();
  return useQuery({
    queryKey: ["chat", "attachment", attachment.id, inline],
    queryFn: async () =>
      unwrap(
        await api!.GET("/api/v1/chat/attachments/{attachment_id}/download", {
          params: { path: { attachment_id: attachment.id }, query: { inline } },
        }),
      ).url,
    enabled: enabled && api !== null && attachment.status === "clean",
    staleTime: LINK_STALE_MS,
    gcTime: LINK_STALE_MS,
  });
}

/**
 * A message's files: image previews, a PDF preview dialog, downloads for the rest. Others only ever receive
 * clean files; the uploader also sees "scanning" and "rejected" states (§13.2, D-068).
 */
export function MessageAttachments({ attachments }: { attachments: Attachment[] }) {
  if (!attachments.length) return null;
  return (
    <ul className="mt-1 flex flex-col gap-2">
      {attachments.map((attachment) => (
        <li key={attachment.id} className="max-w-md">
          {attachment.status === "clean" && attachment.mime.startsWith("image/") ? (
            <ImagePreview attachment={attachment} />
          ) : (
            <FileRow attachment={attachment} />
          )}
        </li>
      ))}
    </ul>
  );
}

function ImagePreview({ attachment }: { attachment: Attachment }) {
  const t = useTranslations("chat.attachments");
  const link = useLink(attachment, true, true);
  const ratio =
    attachment.width && attachment.height ? attachment.width / attachment.height : 4 / 3;
  return (
    <figure className="flex flex-col gap-1">
      {link.data ? (
        // Presigned, short-lived URL on the app's origin (D-068); next/image would cache it past its life.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={link.data}
          alt={t("imageAlt", { name: attachment.filename })}
          width={attachment.width ?? undefined}
          height={attachment.height ?? undefined}
          style={{ aspectRatio: ratio }}
          className="max-h-80 w-auto max-w-full rounded-control border border-border object-contain"
        />
      ) : (
        <span
          aria-busy={link.isPending || undefined}
          style={{ aspectRatio: ratio }}
          className="flex max-h-80 w-64 max-w-full items-center justify-center rounded-control border border-border bg-bg-subtle text-sm text-muted"
        >
          {link.isError ? t("previewFailed") : null}
        </span>
      )}
      <figcaption className="flex items-center gap-2 text-xs text-muted">
        <span className="truncate" title={attachment.filename}>
          {attachment.filename}
        </span>
        <span className="tabular">{formatSize(attachment.size_bytes)}</span>
        <DownloadButton attachment={attachment} />
      </figcaption>
    </figure>
  );
}

function FileRow({ attachment }: { attachment: Attachment }) {
  const t = useTranslations("chat.attachments");
  const [previewing, setPreviewing] = useState(false);
  const clean = attachment.status === "clean";
  const pending = attachment.status === "pending";
  const icon = pending
    ? Loader
    : !clean
      ? ShieldAlert
      : attachment.mime === "application/zip"
        ? FileArchive
        : attachment.mime.includes("presentation")
          ? Presentation
          : FileText;
  return (
    <div className="flex items-center gap-3 rounded-control border border-border px-3 py-2">
      <Icon icon={icon} size={20} className={clean || pending ? "text-muted" : "text-danger"} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate" title={attachment.filename}>
          {attachment.filename}
        </span>
        <span className={clean || pending ? "text-xs text-muted" : "text-xs text-danger"}>
          {pending
            ? t("scanning")
            : clean
              ? formatSize(attachment.size_bytes)
              : attachment.status === "infected"
                ? t("infected")
                : t("rejected")}
        </span>
      </span>
      {clean && attachment.mime === "application/pdf" ? (
        <Button variant="tertiary" size="dense" onClick={() => setPreviewing(true)}>
          {t("preview")}
        </Button>
      ) : null}
      {clean ? <DownloadButton attachment={attachment} /> : null}
      {previewing ? (
        <PdfPreview attachment={attachment} open={previewing} onOpenChange={setPreviewing} />
      ) : null}
    </div>
  );
}

function PdfPreview({
  attachment,
  open,
  onOpenChange,
}: {
  attachment: Attachment;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("chat.attachments");
  const link = useLink(attachment, true, open);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={attachment.filename} className="max-w-4xl">
        {link.data ? (
          <iframe
            src={link.data}
            title={t("pdfTitle", { name: attachment.filename })}
            className="h-[70dvh] w-full rounded-control border border-border"
          />
        ) : (
          <p className="text-sm text-muted">{link.isError ? t("previewFailed") : t("loading")}</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DownloadButton({ attachment }: { attachment: Attachment }) {
  const t = useTranslations("chat.attachments");
  const api = useOptionalApi();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const download = async () => {
    if (!api) return;
    setBusy(true);
    try {
      const link = unwrap(
        await api.GET("/api/v1/chat/attachments/{attachment_id}/download", {
          params: { path: { attachment_id: attachment.id }, query: { inline: false } },
        }),
      );
      // The response carries Content-Disposition: attachment, so the page stays where it is.
      window.location.assign(link.url);
    } catch {
      toast({ title: t("downloadFailed"), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button
      variant="tertiary"
      size="icon-dense"
      loading={busy}
      aria-label={t("download", { name: attachment.filename })}
      onClick={() => void download()}
    >
      <Icon icon={Download} />
    </Button>
  );
}

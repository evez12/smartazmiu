"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import type { MaterialVersion } from "./model";

// Download links live one minute on the server; they are re-requested a little before that.
const LINK_STALE_MS = 45_000;

/** Preview (PDF and images) and download of one clean version; nothing for versions still being checked. */
export function VersionActions({ version }: { version: MaterialVersion }) {
  const t = useTranslations("materials");
  const [previewing, setPreviewing] = useState(false);
  if (version.status !== "clean") return null;
  return (
    <span className="flex items-center gap-1">
      {version.previewable ? (
        <Button variant="tertiary" size="dense" onClick={() => setPreviewing(true)}>
          {t("preview")}
        </Button>
      ) : null}
      <DownloadButton version={version} />
      {previewing ? (
        <Preview version={version} open={previewing} onOpenChange={setPreviewing} />
      ) : null}
    </span>
  );
}

function Preview({
  version,
  open,
  onOpenChange,
}: {
  version: MaterialVersion;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("materials");
  const api = useApi();
  const link = useQuery({
    queryKey: ["materials", "version", version.id, "inline"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/materials/versions/{version_id}/download", {
          params: { path: { version_id: version.id }, query: { inline: true } },
        }),
      ).url,
    enabled: open,
    staleTime: LINK_STALE_MS,
    gcTime: LINK_STALE_MS,
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={version.filename} className="max-w-4xl">
        {!link.data ? (
          <p className="text-sm text-muted">{link.isError ? t("previewFailed") : t("loading")}</p>
        ) : version.mime === "application/pdf" ? (
          <iframe
            src={link.data}
            title={t("pdfTitle", { name: version.filename })}
            className="h-[70dvh] w-full rounded-control border border-border"
          />
        ) : (
          // Presigned, short-lived URL on the app's origin (D-068); next/image would cache it past its life.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={link.data}
            alt={t("imageAlt", { name: version.filename })}
            className="max-h-[70dvh] w-auto max-w-full rounded-control border border-border object-contain"
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function DownloadButton({ version }: { version: MaterialVersion }) {
  const t = useTranslations("materials");
  const api = useApi();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      const link = unwrap(
        await api.GET("/api/v1/materials/versions/{version_id}/download", {
          params: { path: { version_id: version.id }, query: { inline: false } },
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
      aria-label={t("download", { name: version.filename })}
      onClick={() => void download()}
    >
      <Icon icon={Download} />
    </Button>
  );
}

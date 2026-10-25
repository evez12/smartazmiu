"use client";

import { useMutation } from "@tanstack/react-query";
import { Archive } from "lucide-react";
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

/** Takes an announcement down after confirmation (§12.4: destructive actions say what happens). */
export function ArchiveButton({ announcementId }: { announcementId: string }) {
  const t = useTranslations("announcements.staff");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [open, setOpen] = useState(false);
  const archive = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/announcements/{announcement_id}/archive", {
          params: { path: { announcement_id: announcementId } },
        }),
      ),
    onSuccess: () => {
      setOpen(false);
      toast({ title: t("archived") });
      router.refresh();
    },
    onError: () => setOpen(false),
  });
  return (
    <>
      <Button variant="destructive" onClick={() => setOpen(true)}>
        <Icon icon={Archive} />
        {t("archive")}
      </Button>
      {archive.isError ? (
        <Banner tone="danger" title={t("archiveFailed")}>
          {errorMessage(archive.error)}
        </Banner>
      ) : null}
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={t("archiveTitle")}
        consequence={t("archiveConsequence")}
        confirmLabel={t("archive")}
        destructive
        pending={archive.isPending}
        onConfirm={() => archive.mutate()}
      />
    </>
  );
}

"use client";

import { useMutation } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { FilePickerButton } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { ConfirmDialog } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

const ACCEPTED_IMAGES = "image/jpeg,image/png,image/webp";

type PhotoControlsProps = { displayName: string; photoUrl: string | null };

/** Uploading a photo is the consent to show it; removing it withdraws that consent (§5.4). */
export function PhotoControls({ displayName, photoUrl }: PhotoControlsProps) {
  const t = useTranslations("profile.photo");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const upload = useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.PUT("/api/v1/me/photo", {
          body: { file: file.name },
          bodySerializer: () => {
            const form = new FormData();
            form.append("file", file);
            return form;
          },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("uploaded") });
      router.refresh();
    },
  });
  const remove = useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/v1/me/photo")),
    onSuccess: () => {
      setConfirmOpen(false);
      toast({ title: t("removed") });
      router.refresh();
    },
    onError: () => setConfirmOpen(false),
  });
  const failure = upload.error ?? remove.error;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <Avatar name={displayName} src={photoUrl ?? undefined} size={64} decorative />
        <div className="flex flex-wrap gap-2">
          <FilePickerButton
            label={photoUrl ? t("replace") : t("upload")}
            accept={ACCEPTED_IMAGES}
            loading={upload.isPending}
            aria-describedby="photo-helper"
            onFileChange={(file) => {
              if (file) upload.mutate(file);
            }}
          />
          {photoUrl ? (
            <Button
              variant="tertiary"
              size="dense"
              className="text-danger"
              onClick={() => setConfirmOpen(true)}
            >
              <Icon icon={Trash2} />
              {t("remove")}
            </Button>
          ) : null}
        </div>
      </div>
      <p id="photo-helper" className="max-w-[75ch] text-sm text-muted">
        {t("helper")}
      </p>
      {failure ? (
        <Banner tone="danger" title={t("failedTitle")}>
          {errorMessage(failure)}
        </Banner>
      ) : null}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("confirmTitle")}
        consequence={t("confirmConsequence")}
        confirmLabel={t("remove")}
        destructive
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

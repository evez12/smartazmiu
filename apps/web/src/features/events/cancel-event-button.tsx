"use client";

import { useMutation } from "@tanstack/react-query";
import { CalendarX } from "lucide-react";
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

export function CancelEventButton({ eventId }: { eventId: string }) {
  const t = useTranslations("events.staff");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [open, setOpen] = useState(false);
  const cancel = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/events/{event_id}/cancel", {
          params: { path: { event_id: eventId } },
        }),
      ),
    onSuccess: () => {
      setOpen(false);
      toast({ title: t("cancelled") });
      router.refresh();
    },
    onError: () => setOpen(false),
  });
  return (
    <>
      <Button variant="destructive" onClick={() => setOpen(true)}>
        <Icon icon={CalendarX} />
        {t("cancel")}
      </Button>
      {cancel.isError ? (
        <Banner tone="danger" title={t("cancelFailed")}>
          {errorMessage(cancel.error)}
        </Banner>
      ) : null}
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={t("cancelTitle")}
        consequence={t("cancelConsequence")}
        confirmLabel={t("cancel")}
        destructive
        pending={cancel.isPending}
        onConfirm={() => cancel.mutate()}
      />
    </>
  );
}

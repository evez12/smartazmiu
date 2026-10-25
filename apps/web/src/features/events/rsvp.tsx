"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { hasStarted, type EventItem } from "./model";

/** Register (RSVP) or withdraw; the ticket appears on the page after a refresh from the server. */
export function Rsvp({ event }: { event: EventItem }) {
  const t = useTranslations("events.rsvp");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [confirming, setConfirming] = useState(false);
  const path = { params: { path: { event_id: event.id } } };

  const register = useMutation({
    mutationFn: async () => unwrap(await api.PUT("/api/v1/events/{event_id}/registration", path)),
    onSuccess: () => {
      toast({ title: t("registered") });
      router.refresh();
    },
  });
  const withdraw = useMutation({
    mutationFn: async () =>
      unwrap(await api.DELETE("/api/v1/events/{event_id}/registration", path)),
    onSuccess: () => {
      setConfirming(false);
      toast({ title: t("withdrawn") });
      router.refresh();
    },
    onError: () => setConfirming(false),
  });

  const mine = event.my_registration;
  const going = mine?.status === "going";
  if (event.status === "cancelled" || mine?.checked_in_at) return null;
  if (hasStarted(event)) {
    return <p className="text-sm text-muted">{t("closed")}</p>;
  }
  const failure = register.error ?? withdraw.error;
  return (
    <div className="flex flex-col items-start gap-3">
      {failure ? (
        <Banner tone="danger" title={t("failed")}>
          {errorMessage(failure)}
        </Banner>
      ) : null}
      {going ? (
        <Button onClick={() => setConfirming(true)}>{t("withdraw")}</Button>
      ) : (
        <Button
          variant="primary"
          loading={register.isPending}
          disabled={event.spots_left === 0}
          onClick={() => register.mutate()}
        >
          {t("register")}
        </Button>
      )}
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("withdrawTitle")}
        consequence={t("withdrawConsequence")}
        confirmLabel={t("withdraw")}
        destructive
        pending={withdraw.isPending}
        onConfirm={() => withdraw.mutate()}
      />
    </div>
  );
}

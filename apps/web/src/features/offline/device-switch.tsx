"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Switch } from "@/components/ui/choice";
import { useToast } from "@/components/ui/toast";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { lastSavedAt, setOfflineEnabled } from "@/lib/offline/device";
import { readDevice } from "@/lib/offline/store";
import { useFormatters } from "@/lib/use-format";

import { notifyDeviceChanged } from "./device-events";
import { syncAll } from "./sync";

type SwitchState = "checking" | "on" | "off" | "unavailable";

/**
 * "Bu cihazda oflayn saxla": storing the schedule and the channels' newest messages is off until the user turns
 * it on, per device, because browsers are shared (D-117). Turning it off deletes what was stored.
 */
export function OfflineDeviceSwitch({
  userId,
  sessionEndsAt,
}: {
  userId: string;
  sessionEndsAt: number;
}) {
  const t = useTranslations("offline.device");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const { formatDateTime } = useFormatters();
  const [state, setState] = useState<SwitchState>("checking");
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([readDevice(), lastSavedAt()]).then(
      ([device, at]) => {
        if (!mounted) return;
        setState(device?.userId === userId && device.enabled ? "on" : "off");
        setSavedAt(at);
      },
      () => mounted && setState("unavailable"),
    );
    return () => {
      mounted = false;
    };
  }, [userId]);

  const change = useMutation({
    mutationFn: async (enabled: boolean) => {
      await setOfflineEnabled(userId, enabled, sessionEndsAt);
      notifyDeviceChanged();
      if (enabled) await syncAll(api, userId, true);
      return enabled;
    },
    onSuccess: async (enabled) => {
      setState(enabled ? "on" : "off");
      setSavedAt(enabled ? await lastSavedAt() : null);
      toast({ title: enabled ? t("enabled") : t("disabled") });
    },
    onError: (_error, enabled) => {
      // Storing stays switched on after a failed first download: the app retries it by itself.
      if (enabled) setState("on");
    },
  });

  return (
    <div className="flex flex-col gap-3">
      <Switch
        label={t("label")}
        description={t("hint")}
        checked={state === "on"}
        disabled={state === "checking" || state === "unavailable" || change.isPending}
        onCheckedChange={(checked) => change.mutate(checked)}
      />
      {state === "unavailable" ? (
        <Banner tone="info" title={t("unavailableTitle")}>
          {t("unavailable")}
        </Banner>
      ) : null}
      {state === "on" ? (
        <p className="text-sm text-muted" aria-live="polite">
          {savedAt ? t("savedAt", { time: formatDateTime(new Date(savedAt)) }) : t("savedNever")}
        </p>
      ) : null}
      {change.isError ? (
        <Banner tone="danger" title={t("failed")}>
          {errorMessage(change.error)}
        </Banner>
      ) : null}
    </div>
  );
}

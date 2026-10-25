"use client";

import { useMutation } from "@tanstack/react-query";
import { BellOff, BellRing } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import {
  currentSubscription,
  PushPermissionError,
  pushSupport,
  subscribe,
  unsubscribe,
} from "@/lib/push";

type DeviceState = "checking" | "on" | "off" | "unsupported" | "denied";

async function deviceState(): Promise<DeviceState> {
  const support = pushSupport();
  if (support !== "supported") return support;
  try {
    return (await currentSubscription()) ? "on" : "off";
  } catch {
    return "off";
  }
}

/** Turns Web Push on or off for this browser; each device is registered separately. */
export function PushDevice({ publicKey, devices }: { publicKey: string | null; devices: number }) {
  const t = useTranslations("notifications.settings");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [state, setState] = useState<DeviceState>("checking");

  useEffect(() => {
    let mounted = true;
    deviceState().then((value) => {
      if (mounted) setState(value);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const enable = useMutation({
    mutationFn: async () => {
      const body = await subscribe(publicKey!);
      unwrap(await api.PUT("/api/v1/me/push-subscriptions", { body }));
    },
    onSuccess: () => {
      setState("on");
      toast({ title: t("enabled") });
      router.refresh();
    },
    onError: (error) => {
      // A dismissed prompt can be asked again; a refusal only changes in the browser's site settings.
      if (error instanceof PushPermissionError)
        setState(pushSupport() === "denied" ? "denied" : "off");
    },
  });
  const disable = useMutation({
    mutationFn: async () => {
      const endpoint = await unsubscribe();
      if (endpoint) {
        unwrap(
          await api.DELETE("/api/v1/me/push-subscriptions", { params: { query: { endpoint } } }),
        );
      }
    },
    onSuccess: () => {
      setState("off");
      toast({ title: t("disabled") });
      router.refresh();
    },
  });

  const failed =
    (enable.isError && !(enable.error instanceof PushPermissionError)) || disable.isError;
  const notice =
    publicKey === null
      ? t("unavailable")
      : state === "unsupported"
        ? t("unsupported")
        : state === "denied"
          ? t("denied")
          : null;

  return (
    <div className="flex flex-col gap-3">
      <p className="max-w-[75ch] text-sm text-muted">{t("deviceHint")}</p>
      {notice ? (
        <Banner tone="info" title={t("deviceOff")}>
          {notice}
        </Banner>
      ) : (
        <>
          <p className="flex items-center gap-2" aria-live="polite">
            <Icon icon={state === "on" ? BellRing : BellOff} className="text-muted" />
            {state === "checking" ? "" : state === "on" ? t("deviceOn") : t("deviceOff")}
          </p>
          <div>
            {state === "on" ? (
              <Button loading={disable.isPending} onClick={() => disable.mutate()}>
                {t("disable")}
              </Button>
            ) : (
              <Button
                loading={enable.isPending}
                disabled={state === "checking"}
                onClick={() => enable.mutate()}
              >
                {t("enable")}
              </Button>
            )}
          </div>
        </>
      )}
      {failed ? (
        <Banner tone="danger" title={t("deviceFailed")}>
          {errorMessage(enable.error ?? disable.error)}
        </Banner>
      ) : null}
      <p className="text-sm text-muted">{t("devices", { count: devices })}</p>
    </div>
  );
}

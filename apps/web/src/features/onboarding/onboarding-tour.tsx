"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import { tourSteps } from "./steps";

/**
 * The first-run tour (D-072): a few steps through the sections that matter for the user's role, on the
 * dashboard rather than in a modal, so it never stands between the user and their work. Finishing or closing it
 * is stored on the account.
 */
export function OnboardingTour({ roles }: { roles: readonly string[] }) {
  const t = useTranslations("onboarding");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const steps = tourSteps(roles);
  const [index, setIndex] = useState(0);
  const [hidden, setHidden] = useState(false);
  const finish = useMutation({
    mutationFn: async () =>
      unwrap(await api.PUT("/api/v1/me/onboarding", { body: { done: true } })),
    onMutate: () => setHidden(true),
    onSuccess: () => router.refresh(),
    onError: () => {
      setHidden(false);
      toast({ title: t("failed"), tone: "danger" });
    },
  });
  if (hidden) return null;
  const step = steps[index]!;
  const last = index === steps.length - 1;
  return (
    <Panel aria-labelledby="onboarding-title">
      <PanelHeader
        titleId="onboarding-title"
        title={t("title")}
        description={t("progress", { step: index + 1, total: steps.length })}
        action={
          <Button size="dense" variant="tertiary" onClick={() => finish.mutate()}>
            {t("dismiss")}
          </Button>
        }
      />
      <PanelBody className="flex flex-col gap-4">
        <div aria-live="polite" className="flex flex-col gap-1">
          <h3 className="font-semibold">{t(`steps.${step.key}.title`)}</h3>
          <p className="max-w-prose">{t(`steps.${step.key}.body`)}</p>
          <TextLink href={step.href} className="self-start">
            {t("open")}
          </TextLink>
        </div>
        <div className="flex flex-wrap gap-2">
          {index > 0 ? (
            <Button size="dense" onClick={() => setIndex(index - 1)}>
              {t("previous")}
            </Button>
          ) : null}
          {last ? (
            <Button size="dense" variant="primary" onClick={() => finish.mutate()}>
              {t("finish")}
            </Button>
          ) : (
            <Button size="dense" variant="primary" onClick={() => setIndex(index + 1)}>
              {t("next")}
            </Button>
          )}
        </div>
      </PanelBody>
    </Panel>
  );
}

/** Marks the tour as not done on the server and opens the dashboard, where it shows again. */
export function useRestartTour() {
  const t = useTranslations("onboarding");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.PUT("/api/v1/me/onboarding", { body: { done: false } })),
    onSuccess: () => router.push("/"),
    onError: () => toast({ title: t("failed"), tone: "danger" }),
  });
}

/** On the profile page; the profile menu offers the same through useRestartTour. */
export function RestartTourButton() {
  const t = useTranslations("onboarding");
  const restart = useRestartTour();
  return (
    <Button loading={restart.isPending} onClick={() => restart.mutate()}>
      {t("restart")}
    </Button>
  );
}

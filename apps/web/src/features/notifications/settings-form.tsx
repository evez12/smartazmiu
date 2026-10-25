"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox, Switch } from "@/components/ui/choice";
import { Field, Input } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import type { NotificationCategory, NotificationSettings } from "./model";

type Channels = { push: boolean; email: boolean };

/** Push and e-mail per category plus quiet hours; in-app notifications are always on. */
export function NotificationSettingsForm({ settings }: { settings: NotificationSettings }) {
  const t = useTranslations("notifications.settings");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [channels, setChannels] = useState(
    () =>
      Object.fromEntries(
        settings.categories.map((item) => [item.category, { push: item.push, email: item.email }]),
      ) as Record<NotificationCategory, Channels>,
  );
  const [quiet, setQuiet] = useState(settings.quiet_hours);
  const sameTimes = quiet.enabled && quiet.starts_at === quiet.ends_at;

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/me/notification-settings", {
          body: {
            categories: settings.categories.map(({ category }) => ({
              category,
              ...channels[category],
            })),
            quiet_hours: quiet,
          },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("saved") });
      router.refresh();
    },
  });

  const toggle = (category: NotificationCategory, channel: keyof Channels, value: boolean) =>
    setChannels((current) => ({
      ...current,
      [category]: { ...current[category], [channel]: value },
    }));
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!sameTimes) save.mutate();
  };

  return (
    <form onSubmit={submit} noValidate className="flex max-w-2xl flex-col gap-6">
      {save.isError ? (
        <Banner tone="danger" title={t("saveFailed")}>
          {errorMessage(save.error)}
        </Banner>
      ) : null}

      <div className="flex flex-col gap-4">
        {settings.categories.map(({ category }) => (
          <fieldset key={category} className="flex flex-col gap-2">
            <legend className="mb-1 font-medium text-text">{t(`categories.${category}`)}</legend>
            <div className="flex flex-wrap gap-x-8 gap-y-2">
              <Checkbox
                label={t("push")}
                checked={channels[category].push}
                onCheckedChange={(value) => toggle(category, "push", value === true)}
              />
              <Checkbox
                label={t("email")}
                checked={channels[category].email}
                onCheckedChange={(value) => toggle(category, "email", value === true)}
              />
            </div>
          </fieldset>
        ))}
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 font-medium text-text">{t("quietTitle")}</legend>
        <p className="max-w-[75ch] text-sm text-muted">{t("quietHint")}</p>
        <Switch
          label={t("quietEnabled")}
          checked={quiet.enabled}
          onCheckedChange={(enabled) => setQuiet((current) => ({ ...current, enabled }))}
        />
        <div className="flex flex-wrap gap-4">
          <Field label={t("quietStart")} error={sameTimes ? t("quietSame") : undefined}>
            <Input
              type="time"
              step={60}
              className="w-40 tabular"
              value={quiet.starts_at}
              disabled={!quiet.enabled}
              onChange={(event) =>
                setQuiet((current) => ({ ...current, starts_at: event.target.value }))
              }
            />
          </Field>
          <Field label={t("quietEnd")}>
            <Input
              type="time"
              step={60}
              className="w-40 tabular"
              value={quiet.ends_at}
              disabled={!quiet.enabled}
              onChange={(event) =>
                setQuiet((current) => ({ ...current, ends_at: event.target.value }))
              }
            />
          </Field>
        </div>
      </fieldset>

      <div>
        <Button type="submit" variant="primary" loading={save.isPending} disabled={sameTimes}>
          {t("save")}
        </Button>
      </div>
    </form>
  );
}

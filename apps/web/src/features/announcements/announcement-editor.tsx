"use client";

import { useMutation } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { AudiencePicker, type AudienceChoice } from "@/features/audiences/audience-picker";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { cn } from "@/lib/cn";
import { bakuInputToIso, isoToBakuInput } from "@/lib/format";

import { BODY_MAX, TITLE_MAX, type Announcement } from "./model";

/**
 * New announcement (with audience) or a correction of an existing one (text and end time only, D-050).
 * One request per click: the Idempotency-Key makes a retried publish return the first announcement.
 */
export function AnnouncementEditor({ announcement }: { announcement?: Announcement }) {
  const t = useTranslations("announcements.editor");
  const tAudience = useTranslations("audiences");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [title, setTitle] = useState(announcement?.title ?? "");
  const [body, setBody] = useState(announcement?.body ?? "");
  const [expires, setExpires] = useState(
    announcement?.expires_at ? isoToBakuInput(announcement.expires_at) : "",
  );
  const [audience, setAudience] = useState<AudienceChoice>({ type: "university", target: null });
  const [submitted, setSubmitted] = useState(false);
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  const errors = {
    title: !title.trim() ? t("titleRequired") : undefined,
    body: !body.trim() ? t("bodyRequired") : undefined,
    audience:
      !announcement && audience.type !== "university" && !audience.target
        ? tAudience("required")
        : undefined,
  };
  const valid = !errors.title && !errors.body && !errors.audience && body.length <= BODY_MAX;
  const expiresAt = expires ? bakuInputToIso(expires) : null;

  const save = useMutation({
    mutationFn: async () => {
      if (announcement) {
        return unwrap(
          await api.PATCH("/api/v1/announcements/{announcement_id}", {
            params: { path: { announcement_id: announcement.id } },
            body: { version: announcement.version, title, body, expires_at: expiresAt },
          }),
        );
      }
      return unwrap(
        await api.POST("/api/v1/announcements", {
          params: { header: { "Idempotency-Key": idempotencyKey } },
          body: {
            title,
            body,
            expires_at: expiresAt,
            audience: { type: audience.type, target_id: audience.target?.id ?? null },
          },
        }),
      );
    },
    onSuccess: (saved) => {
      toast({ title: announcement ? t("saved") : t("published") });
      router.push(`/announcements/${saved.id}`);
      router.refresh();
    },
  });
  const conflict = save.error instanceof ApiRequestError && save.error.status === 409;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (valid) save.mutate();
  };

  return (
    <form onSubmit={submit} noValidate className="flex max-w-2xl flex-col gap-6">
      {save.isError ? (
        <Banner
          tone="danger"
          title={t("failed")}
          action={
            conflict ? (
              <Button size="dense" onClick={() => window.location.reload()}>
                <Icon icon={RotateCw} />
                {t("reload")}
              </Button>
            ) : undefined
          }
        >
          {errorMessage(save.error)}
        </Banner>
      ) : null}

      <Field
        label={t("titleLabel")}
        helper={t("titleHelp")}
        error={submitted ? errors.title : undefined}
        required
      >
        <Input
          value={title}
          maxLength={TITLE_MAX}
          onChange={(event) => setTitle(event.target.value)}
        />
      </Field>

      <div className="flex flex-col gap-1">
        <Field
          label={t("body")}
          helper={t("bodyHelp")}
          error={submitted ? errors.body : undefined}
          required
        >
          <Textarea rows={8} value={body} onChange={(event) => setBody(event.target.value)} />
        </Field>
        <p
          className={cn("text-sm tabular", body.length > BODY_MAX ? "text-danger" : "text-muted")}
          aria-live="polite"
        >
          {t("bodyCount", { count: body.length })}
        </p>
      </div>

      {announcement ? null : (
        <AudiencePicker
          value={audience}
          onChange={setAudience}
          error={submitted ? errors.audience : undefined}
        />
      )}

      <Field label={t("expires")} helper={t("expiresHelp")}>
        <Input
          type="datetime-local"
          className="w-60 tabular"
          value={expires}
          onChange={(event) => setExpires(event.target.value)}
        />
      </Field>

      <div>
        <Button type="submit" variant="primary" loading={save.isPending}>
          {announcement ? t("save") : t("publish")}
        </Button>
      </div>
    </form>
  );
}

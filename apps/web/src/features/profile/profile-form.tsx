"use client";

import { useMutation } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { RadioGroup } from "@/components/ui/choice";
import { Field, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { cn } from "@/lib/cn";

type Profile = components["schemas"]["ProfileOut"];
type DmPolicy = Profile["dm_policy"];
type ContactVisibility = Profile["contact_visibility"];

export const BIO_MAX_LENGTH = 300;
const DM_POLICIES = ["shared_context", "guides_and_teachers", "everyone", "nobody"] as const;
const CONTACT_VISIBILITIES = ["hidden", "shared_context", "everyone"] as const;

/** Bio and privacy settings; one form with the page's single primary action (§12.4). */
export function ProfileForm({ profile }: { profile: Profile }) {
  const t = useTranslations("profile");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [bio, setBio] = useState(profile.bio);
  const [dmPolicy, setDmPolicy] = useState<DmPolicy>(profile.dm_policy);
  const [visibility, setVisibility] = useState<ContactVisibility>(profile.contact_visibility);
  const tooLong = bio.length > BIO_MAX_LENGTH;

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PATCH("/api/v1/me/profile", {
          body: {
            version: profile.version,
            bio,
            dm_policy: dmPolicy,
            contact_visibility: visibility,
          },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("saved") });
      router.refresh();
    },
  });
  const conflict = save.error instanceof ApiRequestError && save.error.status === 409;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!tooLong) save.mutate();
  };

  return (
    <form onSubmit={submit} noValidate className="flex max-w-2xl flex-col gap-6">
      {save.isError ? (
        <Banner
          tone="danger"
          title={t("saveFailedTitle")}
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

      <div className="flex flex-col gap-1">
        <Field
          label={t("bio")}
          helper={t("bioHelper")}
          error={tooLong ? t("bioTooLong") : undefined}
        >
          <Textarea name="bio" value={bio} onChange={(event) => setBio(event.target.value)} />
        </Field>
        <p
          className={cn("text-sm tabular", tooLong ? "text-danger" : "text-muted")}
          aria-live="polite"
        >
          {t("bioCount", { count: bio.length })}
        </p>
      </div>

      <RadioGroup
        legend={t("dmPolicy")}
        value={dmPolicy}
        onValueChange={(value) => setDmPolicy(value as DmPolicy)}
        options={DM_POLICIES.map((value) => ({
          value,
          label: t(`dmPolicies.${value}`),
          description: value === "nobody" ? t("dmPolicyNote") : undefined,
        }))}
      />

      <div className="flex flex-col gap-2">
        <RadioGroup
          legend={t("contactVisibility")}
          value={visibility}
          onValueChange={(value) => setVisibility(value as ContactVisibility)}
          options={CONTACT_VISIBILITIES.map((value) => ({
            value,
            label: t(`contactVisibilities.${value}`),
          }))}
        />
        <p className="max-w-[75ch] text-sm text-muted">{t("contactVisibilityNote")}</p>
      </div>

      <div>
        <Button type="submit" variant="primary" loading={save.isPending} disabled={tooLong}>
          {t("save")}
        </Button>
      </div>
    </form>
  );
}

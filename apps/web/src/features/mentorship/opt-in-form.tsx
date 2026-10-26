"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox, RadioGroup } from "@/components/ui/choice";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import {
  AVAILABILITIES,
  GRADE_VISIBILITIES,
  MAX_BIO,
  type Availability,
  type GradeVisibility,
  type MyGuideProfile,
} from "./model";

/** Opt-in with explicit consent, or later changes to the profile (§5.2); grades hidden unless chosen. */
export function OptInForm({
  subjectId,
  teacherName,
  profile,
}: {
  subjectId: string;
  teacherName: string | null;
  profile: MyGuideProfile | null;
}) {
  const t = useTranslations("guides");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const editing = profile !== null && profile.active;
  const [consent, setConsent] = useState(editing);
  const [missingConsent, setMissingConsent] = useState(false);
  const [gradeVisibility, setGradeVisibility] = useState<GradeVisibility>(
    profile?.grade_visibility ?? "hidden",
  );
  const [showTeacher, setShowTeacher] = useState(profile?.show_teacher ?? false);
  const [bio, setBio] = useState(profile?.bio ?? "");
  const [availability, setAvailability] = useState<Availability>(
    profile?.availability ?? "available",
  );
  const [maxOpen, setMaxOpen] = useState(profile?.max_open_requests ?? 3);
  const save = useMutation({
    mutationFn: async () => {
      const body = {
        grade_visibility: gradeVisibility,
        show_teacher: showTeacher,
        bio: bio.trim(),
        availability,
        max_open_requests: maxOpen,
      };
      const params = { path: { subject_id: subjectId } };
      return editing
        ? unwrap(await api.PATCH("/api/v1/subjects/{subject_id}/guides/me", { params, body }))
        : unwrap(
            await api.POST("/api/v1/subjects/{subject_id}/guides/me", {
              params,
              body: { ...body, consent: true },
            }),
          );
    },
    onSuccess: () => {
      toast({ title: t("optInPage.saved") });
      router.push("/guides");
      router.refresh();
    },
  });
  return (
    <form
      className="flex max-w-xl flex-col gap-6"
      onSubmit={(event) => {
        event.preventDefault();
        if (!consent) {
          setMissingConsent(true);
          return;
        }
        save.mutate();
      }}
    >
      {save.isError ? (
        <Banner tone="danger" title={t("optInPage.failed")}>
          {errorMessage(save.error)}
        </Banner>
      ) : null}
      {editing ? null : (
        <div className="flex flex-col gap-1">
          <Checkbox
            checked={consent}
            onCheckedChange={(checked) => {
              setConsent(checked === true);
              setMissingConsent(false);
            }}
            label={t("optInPage.consent")}
            description={t("optInPage.consentHelper")}
          />
          {missingConsent ? (
            <p className="text-sm text-danger" role="alert">
              {t("optInPage.consentRequired")}
            </p>
          ) : null}
        </div>
      )}
      <RadioGroup
        legend={t("gradeVisibility.label")}
        value={gradeVisibility}
        onValueChange={(value) => setGradeVisibility(value as GradeVisibility)}
        options={GRADE_VISIBILITIES.map((value) => ({
          value,
          label: t(`gradeVisibility.${value}`),
        }))}
      />
      <p className="-mt-4 text-sm text-muted">{t("gradeVisibility.helper")}</p>
      {teacherName ? (
        <Checkbox
          checked={showTeacher}
          onCheckedChange={(checked) => setShowTeacher(checked === true)}
          label={t("optInPage.showTeacher")}
          description={t("optInPage.showTeacherHelper", { name: teacherName })}
        />
      ) : null}
      <Field label={t("optInPage.bio")} helper={t("optInPage.bioHelper")}>
        <Textarea
          value={bio}
          maxLength={MAX_BIO}
          rows={3}
          onChange={(event) => setBio(event.target.value)}
        />
      </Field>
      <Field label={t("availability.label")} required>
        <Select
          value={availability}
          onChange={(event) => setAvailability(event.target.value as Availability)}
        >
          {AVAILABILITIES.map((value) => (
            <option key={value} value={value}>
              {t(`availability.${value}`)}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("optInPage.maxOpen")} required>
        <Input
          type="number"
          inputMode="numeric"
          min={1}
          max={10}
          value={maxOpen}
          onChange={(event) =>
            setMaxOpen(Math.min(10, Math.max(1, Number(event.target.value) || 1)))
          }
        />
      </Field>
      <div>
        <Button type="submit" variant="primary" loading={save.isPending}>
          {t("optInPage.save")}
        </Button>
      </div>
    </form>
  );
}

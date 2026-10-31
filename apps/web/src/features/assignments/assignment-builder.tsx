"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { RadioGroup } from "@/components/ui/choice";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Panel, PanelBody } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";
import { OfferingField, useManagedOfferings } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { bakuInputToIso } from "@/lib/format";

type LatePolicy = components["schemas"]["LatePolicy"];
type Errors = Partial<Record<"offering" | "title" | "dates" | "points" | "penalty", string>>;

const POLICIES: readonly LatePolicy[] = ["reject", "penalize", "accept"] as const;

/** Creates an assignment for an offering the user teaches (or, for staff, any); the dates are Baku time. */
export function AssignmentBuilder() {
  const t = useTranslations("assignments.form");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const offerings = useManagedOfferings();
  const [offering, setOffering] = useState("");
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [availableFrom, setAvailableFrom] = useState("");
  const [deadline, setDeadline] = useState("");
  const [maxPoints, setMaxPoints] = useState("100");
  const [policy, setPolicy] = useState<LatePolicy>("reject");
  const [penalty, setPenalty] = useState("10");
  const [errors, setErrors] = useState<Errors>({});

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/assignments", {
          body: {
            course_offering_id: offering,
            title: title.trim(),
            instructions: instructions.trim(),
            available_from: availableFrom ? bakuInputToIso(availableFrom) : null,
            deadline: deadline ? bakuInputToIso(deadline) : null,
            max_points: maxPoints.replace(",", "."),
            late_policy: policy,
            late_penalty_percent: policy === "penalize" ? penalty.replace(",", ".") : "0",
          },
        }),
      ),
    onSuccess: (created) => {
      toast({ title: t("saved") });
      router.push(`/assignments/${created.id}`);
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const points = Number(maxPoints.replace(",", "."));
    const percent = Number(penalty.replace(",", "."));
    if (!offering) found.offering = t("offeringRequired");
    if (!title.trim()) found.title = t("titleRequired");
    if (availableFrom && deadline && deadline <= availableFrom) found.dates = t("datesOrder");
    if (!(points > 0 && points <= 100_000)) found.points = t("maxPointsInvalid");
    if (policy === "penalize" && !(percent >= 0 && percent <= 100))
      found.penalty = t("penaltyInvalid");
    setErrors(found);
    if (Object.keys(found).length === 0) save.mutate();
  };

  if (offerings.data && offerings.data.length === 0) {
    return <Banner tone="info" title={t("offeringNone")} />;
  }
  return (
    <Panel>
      <PanelBody>
        <form noValidate onSubmit={submit} className="flex max-w-2xl flex-col gap-4">
          {save.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(save.error)}
            </Banner>
          ) : null}
          <OfferingField
            value={offering}
            onChange={setOffering}
            error={errors.offering}
            labels={{ field: t("offering"), choose: t("offeringChoose") }}
          />
          <Field label={t("assignmentTitle")} error={errors.title} required>
            <Input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label={t("instructions")}>
            <Textarea
              rows={5}
              value={instructions}
              maxLength={20000}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-4">
            <Field label={t("availableFrom")} helper={t("availableFromHelp")}>
              <Input
                type="datetime-local"
                className="w-60 tabular"
                value={availableFrom}
                onChange={(e) => setAvailableFrom(e.target.value)}
              />
            </Field>
            <Field label={t("deadline")} helper={t("deadlineHelp")} error={errors.dates}>
              <Input
                type="datetime-local"
                className="w-60 tabular"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
            </Field>
          </div>
          <Field label={t("maxPoints")} error={errors.points} required>
            <Input
              inputMode="decimal"
              className="w-32 tabular"
              value={maxPoints}
              onChange={(e) => setMaxPoints(e.target.value)}
            />
          </Field>
          <RadioGroup
            legend={t("lateLegend")}
            value={policy}
            onValueChange={(value) => setPolicy(value as LatePolicy)}
            options={POLICIES.map((value) => ({
              value,
              label: t(`late.${value}`),
              description: t(`late.${value}Help`),
            }))}
          />
          {policy === "penalize" ? (
            <Field label={t("penalty")} error={errors.penalty} required>
              <Input
                inputMode="decimal"
                className="w-32 tabular"
                value={penalty}
                onChange={(e) => setPenalty(e.target.value)}
              />
            </Field>
          ) : null}
          <div>
            <Button type="submit" variant="primary" loading={save.isPending}>
              {t("save")}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

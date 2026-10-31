"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Panel, PanelBody } from "@/components/ui/panel";
import { OfferingField, useManagedOfferings } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { bakuInputToIso } from "@/lib/format";

type Errors = Partial<Record<"offering" | "title" | "dates" | "limit" | "attempts", string>>;

/** Creates a quiz draft; questions are added on its page and the quiz is opened to students by publishing. */
export function QuizBuilder() {
  const t = useTranslations("quizzes.form");
  const api = useApi();
  const router = useRouter();
  const errorMessage = useErrorMessage();
  const offerings = useManagedOfferings();
  const [offering, setOffering] = useState("");
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [availableFrom, setAvailableFrom] = useState("");
  const [deadline, setDeadline] = useState("");
  const [minutes, setMinutes] = useState("");
  const [attempts, setAttempts] = useState("1");
  const [errors, setErrors] = useState<Errors>({});

  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/quizzes", {
          body: {
            course_offering_id: offering,
            title: title.trim(),
            instructions: instructions.trim(),
            available_from: availableFrom ? bakuInputToIso(availableFrom) : null,
            deadline: deadline ? bakuInputToIso(deadline) : null,
            time_limit_seconds: minutes.trim() ? Number(minutes) * 60 : null,
            max_attempts: Number(attempts),
          },
        }),
      ),
    onSuccess: (quiz) => router.push(`/quizzes/${quiz.id}`),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!offering) found.offering = t("offeringRequired");
    if (!title.trim()) found.title = t("titleRequired");
    if (availableFrom && deadline && deadline <= availableFrom) found.dates = t("datesOrder");
    if (
      minutes.trim() &&
      !(Number.isInteger(Number(minutes)) && Number(minutes) >= 1 && Number(minutes) <= 480)
    ) {
      found.limit = t("timeLimitInvalid");
    }
    if (!(Number.isInteger(Number(attempts)) && Number(attempts) >= 1 && Number(attempts) <= 10)) {
      found.attempts = t("attemptsInvalid");
    }
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
          <Field label={t("quizTitle")} error={errors.title} required>
            <Input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label={t("instructions")}>
            <Textarea
              rows={4}
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
          <div className="flex flex-wrap gap-4">
            <Field label={t("timeLimit")} helper={t("timeLimitHelp")} error={errors.limit}>
              <Input
                inputMode="numeric"
                className="w-32 tabular"
                value={minutes}
                onChange={(e) => setMinutes(e.target.value)}
              />
            </Field>
            <Field label={t("attempts")} error={errors.attempts} required>
              <Input
                inputMode="numeric"
                className="w-32 tabular"
                value={attempts}
                onChange={(e) => setAttempts(e.target.value)}
              />
            </Field>
          </div>
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

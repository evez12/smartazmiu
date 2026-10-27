"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import type { components } from "@/lib/api/schema";
import { useApi, useErrorMessage } from "@/lib/api/provider";

type MyTip = components["schemas"]["MyTipOut"];
type WeeklyHours = MyTip["weekly_hours"];
type Resource = { title: string; url: string; material_id: string };

export const WEEKLY_HOURS: readonly WeeklyHours[] = [
  "under_2",
  "2_4",
  "4_6",
  "6_10",
  "over_10",
] as const;

/** The Subject Guide card (§5.2 flow 5): one per subject and semester; saving sends it to moderation. */
export function TipForm({
  subjectId,
  semesters,
  initialSemester,
  existing,
  materials,
}: {
  subjectId: string;
  semesters: { id: string; label: string }[];
  initialSemester: string;
  existing: MyTip[];
  materials: { id: string; title: string }[];
}) {
  const t = useTranslations("guides.tips");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const load = (semesterId: string) => existing.find((tip) => tip.semester_id === semesterId);
  const [semesterId, setSemesterId] = useState(initialSemester);
  const current = load(semesterId);
  const [difficulty, setDifficulty] = useState(current?.difficulty ?? 3);
  const [weeklyHours, setWeeklyHours] = useState<WeeklyHours>(current?.weekly_hours ?? "2_4");
  const [keyTopics, setKeyTopics] = useState(current?.key_topics ?? "");
  const [examAdvice, setExamAdvice] = useState(current?.exam_advice ?? "");
  const [retrospective, setRetrospective] = useState(current?.retrospective ?? "");
  const [resources, setResources] = useState<Resource[]>(
    (current?.resources ?? []).map((item) => ({
      title: item.title,
      url: item.url ?? "",
      material_id: item.material_id ?? "",
    })),
  );
  const [missing, setMissing] = useState(false);
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/subjects/{subject_id}/tips/mine", {
          params: { path: { subject_id: subjectId } },
          body: {
            semester_id: semesterId,
            difficulty,
            weekly_hours: weeklyHours,
            key_topics: keyTopics.trim(),
            exam_advice: examAdvice.trim(),
            retrospective: retrospective.trim(),
            resources: resources
              .filter((item) => item.title.trim())
              .map((item) => ({
                title: item.title.trim(),
                url: item.url.trim() || null,
                material_id: item.material_id || null,
              })),
          },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("saved") });
      router.push(`/guides/${subjectId}/tips`);
      router.refresh();
    },
  });
  const blank = (value: string) => missing && !value.trim();
  return (
    <form
      className="flex max-w-2xl flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (!keyTopics.trim() || !examAdvice.trim() || !retrospective.trim()) {
          setMissing(true);
          return;
        }
        save.mutate();
      }}
    >
      {save.isError ? (
        <Banner tone="danger" title={t("failed")}>
          {errorMessage(save.error)}
        </Banner>
      ) : null}
      {current ? <Banner tone="info" title={t("editNotice")} /> : null}
      <Field label={t("semesterField")} required>
        <Select value={semesterId} onChange={(event) => setSemesterId(event.target.value)}>
          {semesters.map((semester) => (
            <option key={semester.id} value={semester.id}>
              {semester.label}
            </option>
          ))}
        </Select>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("difficultyField")} required>
          <Select
            value={String(difficulty)}
            onChange={(event) => setDifficulty(Number(event.target.value))}
          >
            {[1, 2, 3, 4, 5].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("weeklyHoursField")} required>
          <Select
            value={weeklyHours}
            onChange={(event) => setWeeklyHours(event.target.value as WeeklyHours)}
          >
            {WEEKLY_HOURS.map((value) => (
              <option key={value} value={value}>
                {t(`hours.${value}`)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field
        label={t("keyTopicsField")}
        required
        error={blank(keyTopics) ? t("required") : undefined}
      >
        <Textarea
          value={keyTopics}
          maxLength={1000}
          rows={3}
          onChange={(e) => setKeyTopics(e.target.value)}
        />
      </Field>
      <Field
        label={t("examAdviceField")}
        required
        error={blank(examAdvice) ? t("required") : undefined}
      >
        <Textarea
          value={examAdvice}
          maxLength={2000}
          rows={4}
          onChange={(e) => setExamAdvice(e.target.value)}
        />
      </Field>
      <Field
        label={t("retrospectiveField")}
        required
        error={blank(retrospective) ? t("required") : undefined}
      >
        <Textarea
          value={retrospective}
          maxLength={2000}
          rows={4}
          onChange={(e) => setRetrospective(e.target.value)}
        />
      </Field>
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 font-medium">{t("resourcesField")}</legend>
        {resources.map((resource, index) => {
          const change = (patch: Partial<Resource>) =>
            setResources((items) =>
              items.map((item, i) => (i === index ? { ...item, ...patch } : item)),
            );
          return (
            <div key={index} className="grid gap-3 rounded-control border border-border p-3">
              <Field label={t("resourceTitle")}>
                <Input
                  value={resource.title}
                  maxLength={200}
                  onChange={(e) => change({ title: e.target.value })}
                />
              </Field>
              <Field label={t("resourceUrl")}>
                <Input
                  type="url"
                  value={resource.url}
                  maxLength={500}
                  onChange={(e) => change({ url: e.target.value })}
                />
              </Field>
              {materials.length ? (
                <Field label={t("resourceMaterial")}>
                  <Select
                    value={resource.material_id}
                    onChange={(e) => change({ material_id: e.target.value })}
                  >
                    <option value="">{t("noMaterial")}</option>
                    {materials.map((material) => (
                      <option key={material.id} value={material.id}>
                        {material.title}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              <div>
                <Button
                  variant="tertiary"
                  size="dense"
                  onClick={() => setResources((items) => items.filter((_, i) => i !== index))}
                >
                  {t("removeResource")}
                </Button>
              </div>
            </div>
          );
        })}
        {resources.length < 10 ? (
          <div>
            <Button
              variant="secondary"
              size="dense"
              onClick={() =>
                setResources((items) => [...items, { title: "", url: "", material_id: "" }])
              }
            >
              {t("addResource")}
            </Button>
          </div>
        ) : null}
      </fieldset>
      <div>
        <Button type="submit" variant="primary" loading={save.isPending}>
          {t("save")}
        </Button>
      </div>
    </form>
  );
}

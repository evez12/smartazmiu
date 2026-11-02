"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { formatPoints, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { SubmissionFiles } from "./submission-files";
import { useFormatters } from "@/lib/use-format";

/** A teacher or staff member reads one submission and gives points and feedback (grades are audited, D-092). */
export function GradeSubmission({
  assignmentId,
  submissionId,
}: {
  assignmentId: string;
  submissionId: string;
}) {
  const { formatDateTime } = useFormatters();
  const t = useTranslations("assignments");
  const tForm = useTranslations("assignments.gradeForm");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const query = useQuery({
    queryKey: ["assignment-submission", submissionId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/assignment-submissions/{submission_id}", {
          params: { path: { submission_id: submissionId } },
        }),
      ),
  });
  // What the person typed, or nothing yet: the form then shows the grade already given, so a regrade
  // changes it instead of retyping it.
  const [typedPoints, setPoints] = useState<string | null>(null);
  const [typedFeedback, setFeedback] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | undefined>();
  const grade = query.data?.grade;
  const points = typedPoints ?? (grade ? formatPoints(grade.raw_points) : "");
  const feedback = typedFeedback ?? grade?.feedback ?? "";

  const save = useMutation({
    mutationFn: async (value: number) =>
      unwrap(
        await api.POST("/api/v1/assignment-submissions/{submission_id}/grade", {
          params: { path: { submission_id: submissionId } },
          body: { points: String(value), feedback: feedback.trim() },
        }),
      ),
    onSuccess: async () => {
      toast({ title: tForm("saved") });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assignment-submission", submissionId] }),
        queryClient.invalidateQueries({ queryKey: ["assignment-submissions", assignmentId] }),
        queryClient.invalidateQueries({ queryKey: ["assignment", assignmentId] }),
      ]);
    },
  });

  if (!query.data) {
    return (
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
    );
  }
  const submission = query.data;
  const max = Number(submission.max_points);
  return (
    <div className="flex flex-col gap-4">
      <Link className="text-primary hover:underline" href={`/assignments/${assignmentId}`}>
        {tForm("back")}
      </Link>
      <Panel>
        <PanelHeader
          title={submission.student.display_name}
          action={
            submission.is_late ? <Tag tone="warning">{t("submission.lateTag")}</Tag> : undefined
          }
        />
        <PanelBody>
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted tabular">
              {submission.assignment_title} · {submission.student.group_code ?? "—"} ·{" "}
              {t("submission.sentAt", { time: formatDateTime(submission.submitted_at) })}
            </p>
            <SubmissionFiles files={submission.files} />
          </div>
        </PanelBody>
      </Panel>
      <Panel>
        <PanelBody>
          <form
            noValidate
            className="flex max-w-xl flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              const value = Number(points.replace(",", "."));
              if (!points.trim() || !(value >= 0 && value <= max)) {
                setProblem(tForm("pointsRequired", { max: formatPoints(max) }));
                return;
              }
              setProblem(undefined);
              save.mutate(value);
            }}
          >
            {save.isError ? (
              <Banner tone="danger" title={tForm("failed")}>
                {errorMessage(save.error)}
              </Banner>
            ) : null}
            {submission.is_late && submission.late_policy === "penalize" ? (
              <Banner
                tone="info"
                title={tForm("latePenalty", {
                  percent: formatPoints(submission.late_penalty_percent),
                })}
              />
            ) : null}
            {grade ? (
              <p className="font-medium tabular">
                {tForm("current", {
                  points: formatPoints(grade.points),
                  max: formatPoints(max),
                })}
              </p>
            ) : null}
            <Field label={tForm("points", { max: formatPoints(max) })} error={problem} required>
              <Input
                inputMode="decimal"
                className="w-32 tabular"
                value={points}
                onChange={(event) => {
                  setPoints(event.target.value);
                  setProblem(undefined);
                }}
              />
            </Field>
            <Field label={tForm("feedback")} helper={tForm("feedbackHelp")}>
              <Textarea
                rows={5}
                value={feedback}
                maxLength={20000}
                onChange={(event) => setFeedback(event.target.value)}
              />
            </Field>
            <div>
              <Button type="submit" variant="primary" loading={save.isPending}>
                {tForm("save")}
              </Button>
            </div>
          </form>
        </PanelBody>
      </Panel>
    </div>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, FileInput } from "@/components/ui/field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { formatPoints, offeringLabel, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { ACCEPTED_FILES, formatSize, putFile, uploadType } from "@/lib/uploads";

import { AssignmentStatus } from "./assignments-list";
import { SubmissionFiles } from "./submission-files";
import { useFormatters } from "@/lib/use-format";

type Detail = components["schemas"]["AssignmentDetailOut"];

const MAX_FILE_BYTES = 25 * 1024 * 1024;

export function AssignmentPage({ id }: { id: string }) {
  const t = useTranslations("assignments");
  const api = useApi();
  const query = useQuery({
    queryKey: ["assignment", id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/assignments/{assignment_id}", {
          params: { path: { assignment_id: id } },
        }),
      ),
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
  const assignment = query.data;
  return (
    <div className="flex flex-col gap-4">
      <AssignmentInfo assignment={assignment} />
      {assignment.can_manage ? (
        <ClassTable assignment={assignment} />
      ) : (
        <MySubmission assignment={assignment} />
      )}
    </div>
  );
}

export function AssignmentInfo({ assignment }: { assignment: Detail }) {
  const { formatDateTime } = useFormatters();
  const t = useTranslations("assignments");
  return (
    <Panel>
      <PanelBody>
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold break-words">{assignment.title}</h2>
          <p className="text-sm text-muted">{offeringLabel(assignment.offering)}</p>
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            <div>
              <dt className="sr-only">{t("form.deadline")}</dt>
              <dd className="tabular">
                {assignment.deadline
                  ? t("deadlineAt", { time: formatDateTime(assignment.deadline) })
                  : t("deadlineNone")}
              </dd>
            </div>
            {assignment.available_from ? (
              <div>
                <dd className="tabular">
                  {t("opensAt", { time: formatDateTime(assignment.available_from) })}
                </dd>
              </div>
            ) : null}
            <div>
              <dd className="tabular">
                {t("maxPoints", { points: formatPoints(assignment.max_points) })}
              </dd>
            </div>
            <div>
              <dd>
                {t(`late.${assignment.late_policy}`, {
                  percent: formatPoints(assignment.late_penalty_percent),
                })}
              </dd>
            </div>
          </dl>
          {assignment.instructions ? (
            <p className="break-words whitespace-pre-wrap">{assignment.instructions}</p>
          ) : null}
        </div>
      </PanelBody>
    </Panel>
  );
}

export function MySubmission({ assignment }: { assignment: Detail }) {
  const { formatDateTime } = useFormatters();
  const t = useTranslations("assignments");
  const mine = assignment.my_submission;
  return (
    <Panel>
      <PanelHeader
        title={t("submission.heading")}
        action={
          assignment.my_status ? <AssignmentStatus status={assignment.my_status} /> : undefined
        }
      />
      <PanelBody>
        <div className="flex flex-col gap-4">
          {mine ? (
            <>
              <p className="flex flex-wrap items-center gap-2 text-sm tabular">
                {t("submission.sentAt", { time: formatDateTime(mine.submitted_at) })}
                {mine.is_late ? <Tag tone="warning">{t("submission.lateTag")}</Tag> : null}
              </p>
              <SubmissionFiles files={mine.files} />
              {mine.files.some((file) => file.status === "infected" || file.status === "failed") ? (
                <Banner tone="danger" title={t("submission.rejectedHint")} />
              ) : null}
              {mine.grade ? <GradeCard assignment={assignment} grade={mine.grade} /> : null}
            </>
          ) : null}
          {assignment.submit_blocked ? (
            <Banner
              tone="info"
              title={t(`submission.blocked.${assignment.submit_blocked as "closed"}`)}
            />
          ) : null}
          {assignment.can_submit ? (
            <UploadForm assignmentId={assignment.id} replacing={mine !== null} />
          ) : null}
        </div>
      </PanelBody>
    </Panel>
  );
}

function GradeCard({
  assignment,
  grade,
}: {
  assignment: Detail;
  grade: NonNullable<Detail["my_submission"]>["grade"] & object;
}) {
  const t = useTranslations("assignments.grade");
  const penalised = grade.raw_points !== grade.points;
  return (
    <section aria-label={t("heading")} className="flex flex-col gap-2 border-t border-border pt-4">
      <h3 className="text-lg font-semibold">{t("heading")}</h3>
      <p className="text-xl font-semibold tabular">
        {t("points", {
          points: formatPoints(grade.points),
          max: formatPoints(assignment.max_points),
        })}
      </p>
      {penalised ? (
        <p className="text-sm text-muted">
          {t("penaltyNote", { raw: formatPoints(grade.raw_points) })}
        </p>
      ) : null}
      <p className="font-medium">{t("feedback")}</p>
      <p className="break-words whitespace-pre-wrap">{grade.feedback || t("noFeedback")}</p>
    </section>
  );
}

/** Reserve → PUT to storage → submit: the file is checked by the worker before a teacher can open it (D-092). */
function UploadForm({ assignmentId, replacing }: { assignmentId: string; replacing: boolean }) {
  const t = useTranslations("assignments.submission");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | undefined>();
  const [progress, setProgress] = useState<number | null>(null);
  const abort = useRef<AbortController | null>(null);

  const send = useMutation({
    mutationFn: async (chosen: File) => {
      const controller = new AbortController();
      abort.current = controller;
      setProgress(0);
      const reserved = unwrap(
        await api.POST("/api/v1/assignments/{assignment_id}/uploads/presign", {
          params: { path: { assignment_id: assignmentId } },
          body: { filename: chosen.name, mime: uploadType(chosen)!, size: chosen.size },
        }),
      );
      await putFile(
        reserved.url,
        reserved.headers,
        chosen,
        setProgress,
        controller.signal,
        "assignments.storage_unavailable",
      );
      return unwrap(
        await api.POST("/api/v1/assignments/{assignment_id}/submissions", {
          params: { path: { assignment_id: assignmentId } },
          body: { upload_id: reserved.upload_id },
        }),
      );
    },
    onSuccess: async () => {
      setFile(null);
      toast({ title: t("sent") });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assignment", assignmentId] }),
        queryClient.invalidateQueries({ queryKey: ["assignments"] }),
      ]);
    },
    onSettled: () => {
      abort.current = null;
      setProgress(null);
    },
  });

  const check = (): string | undefined => {
    if (!file) return t("fileRequired");
    if (!uploadType(file)) return t("fileType");
    if (file.size === 0 || file.size > MAX_FILE_BYTES) {
      return t("fileSize", { max: formatSize(MAX_FILE_BYTES) });
    }
    return undefined;
  };

  return (
    <form
      noValidate
      className="flex flex-col gap-3 border-t border-border pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        const found = check();
        setProblem(found);
        if (!found && file) send.mutate(file);
      }}
    >
      {send.isError ? (
        <Banner tone="danger" title={t("failed")}>
          {errorMessage(send.error)}
        </Banner>
      ) : null}
      <Field
        label={t("fileLabel")}
        helper={t("fileHelp", { max: formatSize(MAX_FILE_BYTES) })}
        error={problem}
        required
      >
        <FileInput
          file={file}
          accept={ACCEPTED_FILES}
          onFileChange={(chosen) => {
            setFile(chosen);
            setProblem(undefined);
          }}
        />
      </Field>
      {progress !== null ? (
        <progress className="w-full" value={progress} max={1} aria-label={t("uploading")} />
      ) : null}
      <div>
        <Button type="submit" variant="primary" loading={send.isPending}>
          {replacing ? t("resubmit") : t("submit")}
        </Button>
      </div>
    </form>
  );
}

function ClassTable({ assignment }: { assignment: Detail }) {
  const { formatDateTime } = useFormatters();
  const t = useTranslations("assignments");
  const tStatus = useTranslations("assignments.submission.fileStatus");
  const api = useApi();
  const rows = useQuery({
    queryKey: ["assignment-submissions", assignment.id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/assignments/{assignment_id}/submissions", {
          params: { path: { assignment_id: assignment.id } },
        }),
      ).items,
  });
  const items = rows.data ?? [];
  return (
    <Panel>
      <PanelHeader
        title={t("manage.students")}
        action={
          <span className="text-sm text-muted tabular">
            {t("progress", {
              submitted: assignment.submitted_count ?? 0,
              enrolled: assignment.enrolled_count ?? 0,
              graded: assignment.graded_count ?? 0,
            })}
          </span>
        }
      />
      <PanelBody>
        <ScreenState
          loading={rows.isLoading}
          error={rows.error}
          empty={!rows.isLoading && !rows.isError && items.length === 0}
          emptyMessage={t("manage.empty")}
          errorMessage={t("error")}
          retryLabel={t("retry")}
          retry={() => void rows.refetch()}
        />
        {items.length ? (
          <Table>
            <TableCaption>{t("manage.tableCaption")}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>{t("manage.student")}</TableHead>
                <TableHead>{t("manage.group")}</TableHead>
                <TableHead>{t("manage.status")}</TableHead>
                <TableHead>{t("manage.sentAt")}</TableHead>
                <TableHead>{t("manage.file")}</TableHead>
                <TableHead numeric>{t("manage.points")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("manage.open")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((row) => (
                <TableRow key={row.student.id}>
                  <TableCell label={t("manage.student")}>{row.student.display_name}</TableCell>
                  <TableCell label={t("manage.group")}>{row.student.group_code ?? "—"}</TableCell>
                  <TableCell label={t("manage.status")}>
                    <AssignmentStatus
                      status={
                        row.graded ? "graded" : row.submission_id ? "submitted" : "not_submitted"
                      }
                    />
                    {row.is_late ? <Tag tone="warning">{t("submission.lateTag")}</Tag> : null}
                  </TableCell>
                  <TableCell label={t("manage.sentAt")} className="tabular">
                    {row.submitted_at ? formatDateTime(row.submitted_at) : t("manage.noWork")}
                  </TableCell>
                  <TableCell label={t("manage.file")}>
                    {row.file_status ? tStatus(row.file_status) : "—"}
                  </TableCell>
                  <TableCell label={t("manage.points")} numeric>
                    {row.points !== null ? formatPoints(row.points) : "—"}
                  </TableCell>
                  <TableCell label={t("manage.open")}>
                    {row.submission_id ? (
                      <Link
                        className="text-primary hover:underline"
                        href={`/assignments/${assignment.id}/submissions/${row.submission_id}`}
                      >
                        {row.graded ? t("manage.regrade") : t("manage.grade")}
                      </Link>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : null}
      </PanelBody>
    </Panel>
  );
}

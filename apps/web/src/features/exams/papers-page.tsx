"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox, RadioGroup } from "@/components/ui/choice";
import { Field, FileInput, Input, Select } from "@/components/ui/field";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { formatDateTime } from "@/lib/format";
import { ACCEPTED_FILES, formatSize, putFile, uploadType } from "@/lib/uploads";

type Paper = components["schemas"]["PaperOut"];
type Kind = components["schemas"]["PastPaperKind"];

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const KINDS: readonly Kind[] = ["final", "midterm", "retake"] as const;
const STATUS_TONE = { pending: "warning", approved: "success", rejected: "danger" } as const;

/** Exam papers of finished semesters, shared after a teacher or the dean's office approves them (D-097). */
export function PapersPage() {
  const t = useTranslations("exams.papers");
  const api = useApi();
  const [picked, setPicked] = useState("");
  const subjects = useQuery({
    queryKey: ["papers", "subjects"],
    queryFn: async () => unwrap(await api.GET("/api/v1/exams/papers/subjects")).items,
  });
  const items = subjects.data ?? [];
  const subjectId = picked || items[0]?.id || "";
  return (
    <div className="flex flex-col gap-4">
      <ScreenState
        loading={subjects.isLoading}
        error={subjects.error}
        empty={!subjects.isLoading && !subjects.isError && items.length === 0}
        emptyMessage={t("noSubjects")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void subjects.refetch()}
      />
      {items.length > 0 ? (
        <Field label={t("subject")}>
          <Select value={subjectId} onChange={(event) => setPicked(event.target.value)}>
            {items.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.code} · {subject.name}
                {subject.pending > 0 ? ` (${t("waiting", { count: subject.pending })})` : ""}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}
      {subjectId ? <SubjectPapers key={subjectId} subjectId={subjectId} /> : null}
    </div>
  );
}

function SubjectPapers({ subjectId }: { subjectId: string }) {
  const t = useTranslations("exams.papers");
  const api = useApi();
  const query = useQuery({
    queryKey: ["papers", "list", subjectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/exams/papers", { params: { query: { subject_id: subjectId } } }),
      ),
  });
  const papers = query.data?.items ?? [];
  return (
    <>
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={!query.isLoading && !query.isError && papers.length === 0}
        emptyMessage={t("empty")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
      <ul aria-label={t("listLabel")} className="flex flex-col gap-3">
        {papers.map((paper) => (
          <li key={paper.id}>
            <PaperCard paper={paper} subjectId={subjectId} />
          </li>
        ))}
      </ul>
      <UploadForm subjectId={subjectId} />
    </>
  );
}

export function PaperCard({ paper, subjectId }: { paper: Paper; subjectId: string }) {
  const t = useTranslations("exams.papers");
  const api = useApi();
  const toast = useToast();
  const [reviewing, setReviewing] = useState(false);
  const open = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.GET("/api/v1/exams/papers/{paper_id}/download", {
          params: { path: { paper_id: paper.id } },
        }),
      ),
    onSuccess: (link) => window.location.assign(link.url),
    onError: () => toast({ title: t("downloadFailed"), tone: "danger" }),
  });
  return (
    <Panel>
      <PanelBody>
        <article className="flex flex-col gap-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h3 className="text-lg font-semibold break-words">{paper.title}</h3>
            <div className="flex flex-wrap gap-2">
              <Tag tone={STATUS_TONE[paper.status]}>{t(`status.${paper.status}`)}</Tag>
              {paper.scan_status !== "clean" ? (
                <Tag tone={paper.scan_status === "pending" ? "neutral" : "danger"}>
                  {t(`scan.${paper.scan_status}`)}
                </Tag>
              ) : null}
            </div>
          </div>
          <p className="text-sm text-muted">
            {t("meta", {
              semester: paper.semester,
              kind: t(`kind.${paper.kind}`),
              size: formatSize(paper.size_bytes),
            })}
          </p>
          <p className="text-sm text-muted">{formatDateTime(paper.created_at)}</p>
          {paper.review_note ? (
            <p className="text-sm">{t("note", { note: paper.review_note })}</p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            {paper.can_download ? (
              <Button variant="secondary" loading={open.isPending} onClick={() => open.mutate()}>
                <Download aria-hidden className="size-4" />
                {t("download")}
              </Button>
            ) : null}
            {paper.can_review ? (
              <Button variant="primary" onClick={() => setReviewing(true)}>
                {t("review")}
              </Button>
            ) : null}
          </div>
        </article>
        {reviewing ? (
          <ReviewDialog paper={paper} subjectId={subjectId} onClose={() => setReviewing(false)} />
        ) : null}
      </PanelBody>
    </Panel>
  );
}

function ReviewDialog({
  paper,
  subjectId,
  onClose,
}: {
  paper: Paper;
  subjectId: string;
  onClose: () => void;
}) {
  const t = useTranslations("exams.papers");
  const api = useApi();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: async (approve: boolean) =>
      unwrap(
        await api.POST("/api/v1/exams/papers/{paper_id}/review", {
          params: { path: { paper_id: paper.id } },
          body: { approve, note: note.trim() },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["papers"] });
      void client.invalidateQueries({ queryKey: ["papers", "list", subjectId] });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("reviewTitle")}
        description={paper.title}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="destructive"
              loading={decide.isPending && decide.variables === false}
              onClick={() => decide.mutate(false)}
            >
              {t("reject")}
            </Button>
            <Button
              variant="primary"
              loading={decide.isPending && decide.variables === true}
              onClick={() => decide.mutate(true)}
            >
              {t("approve")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted">{t("reviewHelp")}</p>
          {decide.isError ? (
            <Banner tone="danger" title={t("reviewFailed")}>
              {errorMessage(decide.error)}
            </Banner>
          ) : null}
          <Field label={t("noteLabel")} helper={t("noteHelp")}>
            <Input value={note} maxLength={300} onChange={(event) => setNote(event.target.value)} />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

type Errors = Partial<Record<"file" | "semester" | "title" | "consent", string>>;

function UploadForm({ subjectId }: { subjectId: string }) {
  const t = useTranslations("exams.papers.upload");
  const api = useApi();
  const toast = useToast();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const form = useQuery({
    queryKey: ["papers", "form", subjectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/exams/papers/form", {
          params: { query: { subject_id: subjectId } },
        }),
      ),
  });
  const [file, setFile] = useState<File | null>(null);
  const [semester, setSemester] = useState("");
  const [kind, setKind] = useState<Kind>("final");
  const [title, setTitle] = useState("");
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [progress, setProgress] = useState<number | null>(null);
  const abort = useRef<AbortController | null>(null);
  const semesters = form.data?.semesters ?? [];

  const send = useMutation({
    mutationFn: async (chosen: File) => {
      const controller = new AbortController();
      abort.current = controller;
      setProgress(0);
      const reserved = unwrap(
        await api.POST("/api/v1/exams/papers/uploads/presign", {
          body: {
            subject_id: subjectId,
            filename: chosen.name,
            mime: uploadType(chosen)!,
            size: chosen.size,
          },
        }),
      );
      await putFile(
        reserved.url,
        reserved.required_headers,
        chosen,
        setProgress,
        controller.signal,
        "exams.storage_unavailable",
      );
      return unwrap(
        await api.POST("/api/v1/exams/papers", {
          body: {
            upload_id: reserved.upload_id,
            semester_id: semester,
            kind,
            title: title.trim(),
            consent,
          },
        }),
      );
    },
    onSuccess: (saved) => {
      toast({ title: saved.status === "approved" ? t("sentApproved") : t("sent") });
      setFile(null);
      setTitle("");
      setConsent(false);
      void client.invalidateQueries({ queryKey: ["papers"] });
    },
    onSettled: () => {
      abort.current = null;
      setProgress(null);
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!file) found.file = t("fileRequired");
    else if (!uploadType(file)) found.file = t("fileType");
    else if (file.size === 0 || file.size > MAX_FILE_BYTES) {
      found.file = t("fileSize", { max: formatSize(MAX_FILE_BYTES) });
    }
    if (!semester) found.semester = t("semesterRequired");
    if (title.trim().length < 3) found.title = t("titleRequired");
    if (!consent) found.consent = t("consentRequired");
    setErrors(found);
    if (Object.keys(found).length === 0 && file) send.mutate(file);
  };

  return (
    <Panel>
      <PanelBody>
        <form noValidate onSubmit={submit} className="flex max-w-2xl flex-col gap-4">
          <h2 className="text-lg font-semibold">{t("title")}</h2>
          <p className="text-sm text-muted">{t("rule")}</p>
          {send.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(send.error)}
            </Banner>
          ) : null}
          {form.data && semesters.length === 0 ? (
            <Banner tone="info" title={t("noSemesters")} />
          ) : null}
          <Field
            label={t("file")}
            helper={t("fileHelp", { max: formatSize(MAX_FILE_BYTES) })}
            error={errors.file}
            required
          >
            <FileInput
              file={file}
              accept={ACCEPTED_FILES}
              onFileChange={(chosen) => {
                setFile(chosen);
                setErrors((previous) => ({ ...previous, file: undefined }));
              }}
            />
          </Field>
          <Field label={t("semester")} error={errors.semester} required>
            <Select value={semester} onChange={(event) => setSemester(event.target.value)}>
              <option value="">{t("semesterChoose")}</option>
              {semesters.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
          <RadioGroup
            legend={t("kind")}
            value={kind}
            onValueChange={(value) => setKind(value as Kind)}
            options={KINDS.map((value) => ({ value, label: t(`kinds.${value}`) }))}
          />
          <Field label={t("paperTitle")} error={errors.title} required>
            <Input
              value={title}
              maxLength={200}
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
          <div className="flex flex-col gap-1">
            <Checkbox
              checked={consent}
              onCheckedChange={(value) => setConsent(value === true)}
              label={t("consent")}
              description={t("consentHelp")}
            />
            {errors.consent ? (
              <p role="alert" className="text-sm text-danger">
                {errors.consent}
              </p>
            ) : null}
          </div>
          {progress !== null ? (
            <progress className="w-full" value={progress} max={1} aria-label={t("uploading")} />
          ) : null}
          <div>
            <Button type="submit" variant="primary" loading={send.isPending}>
              {t("submit")}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

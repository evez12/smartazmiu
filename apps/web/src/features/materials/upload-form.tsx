"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRef, useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/choice";
import { Field, FileInput, Input, Select, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { ACCEPTED_FILES, formatSize, putFile, uploadType } from "@/lib/uploads";

import {
  MATERIAL_TYPES,
  MAX_MATERIAL_BYTES,
  materialHref,
  type MaterialType,
  type Semester,
} from "./model";

type Errors = Partial<Record<"semester" | "type" | "title" | "file" | "consent", string>>;

type UploadFormProps =
  | { mode: "material"; subjectId: string; semesters: Semester[] }
  | { mode: "version"; subjectId: string; semesterId: string; materialId: string };

/**
 * Upload of a new material or of the next version of one (§6.1): the file goes straight to object storage
 * through a presigned URL, then the form is saved with the uploader's copyright confirmation.
 */
export function UploadForm(props: UploadFormProps) {
  const t = useTranslations("materials.form");
  const tTypes = useTranslations("materials.types");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const uploadable =
    props.mode === "material" ? props.semesters.filter((semester) => semester.can_upload) : [];
  const [semesterId, setSemesterId] = useState(uploadable.length === 1 ? uploadable[0]!.id : "");
  const [type, setType] = useState<MaterialType | "">("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [progress, setProgress] = useState<number | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const max = formatSize(MAX_MATERIAL_BYTES);

  const validate = (): Errors => {
    const found: Errors = {};
    if (props.mode === "material") {
      if (!semesterId) found.semester = t("errors.semester");
      if (!type) found.type = t("errors.type");
      if (!title.trim()) found.title = t("errors.title");
    }
    if (!file) found.file = t("errors.file");
    else if (!uploadType(file)) found.file = t("errors.fileType");
    else if (file.size === 0 || file.size > MAX_MATERIAL_BYTES)
      found.file = t("errors.fileSize", { max });
    if (!consent) found.consent = t("errors.consent");
    return found;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length > 0 || !file) return;
    const controller = new AbortController();
    abort.current = controller;
    setProgress(0);
    try {
      const reserved = unwrap(
        await api.POST("/api/v1/materials/uploads/presign", {
          body: {
            subject_id: props.subjectId,
            semester_id: props.mode === "material" ? semesterId : props.semesterId,
            filename: file.name,
            mime: uploadType(file)!,
            size: file.size,
          },
        }),
      );
      await putFile(
        reserved.url,
        reserved.headers,
        file,
        setProgress,
        controller.signal,
        "materials.storage_unavailable",
      );
      const saved =
        props.mode === "material"
          ? unwrap(
              await api.POST("/api/v1/materials", {
                body: {
                  upload_id: reserved.upload_id,
                  type: type as MaterialType,
                  title: title.trim(),
                  description: description.trim(),
                  copyright_confirmed: consent,
                },
              }),
            )
          : unwrap(
              await api.POST("/api/v1/materials/{material_id}/versions", {
                params: { path: { material_id: props.materialId } },
                body: {
                  upload_id: reserved.upload_id,
                  note: note.trim(),
                  copyright_confirmed: consent,
                },
              }),
            );
      toast({ title: t("saved") });
      router.push(materialHref(props.subjectId, saved.id));
      router.refresh();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setFailure(errorMessage(error));
    } finally {
      abort.current = null;
      setProgress(null);
    }
  };

  const busy = progress !== null;

  return (
    <form noValidate onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
      {failure ? (
        <Banner tone="danger" title={t("failed")}>
          {failure}
        </Banner>
      ) : null}
      {props.mode === "material" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("semester")} required error={errors.semester}>
              <Select value={semesterId} onChange={(event) => setSemesterId(event.target.value)}>
                <option value="">{t("chooseSemester")}</option>
                {uploadable.map((semester) => (
                  <option key={semester.id} value={semester.id}>
                    {semester.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("type")} required error={errors.type}>
              <Select
                value={type}
                onChange={(event) => setType(event.target.value as MaterialType | "")}
              >
                <option value="">{t("chooseType")}</option>
                {MATERIAL_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {tTypes(value)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label={t("titleLabel")} helper={t("titleHelper")} required error={errors.title}>
            <Input
              value={title}
              maxLength={200}
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
          <Field label={t("descriptionLabel")}>
            <Textarea
              value={description}
              maxLength={1000}
              rows={3}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
        </>
      ) : (
        <Field label={t("note")} helper={t("noteHelper")}>
          <Input value={note} maxLength={300} onChange={(event) => setNote(event.target.value)} />
        </Field>
      )}
      <Field label={t("file")} helper={t("fileHelper", { max })} required error={errors.file}>
        <FileInput file={file} accept={ACCEPTED_FILES} onFileChange={setFile} disabled={busy} />
      </Field>
      <div className="flex flex-col gap-1">
        <Checkbox
          checked={consent}
          onCheckedChange={(checked) => setConsent(checked === true)}
          label={t("consent")}
          description={t("consentHelper")}
          aria-invalid={errors.consent ? true : undefined}
        />
        {errors.consent ? <p className="text-sm text-danger">{errors.consent}</p> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" loading={busy}>
          {t("submit")}
        </Button>
        {busy ? (
          <>
            <Button type="button" variant="tertiary" onClick={() => abort.current?.abort()}>
              {t("cancel")}
            </Button>
            <span role="status" className="text-sm text-muted tabular">
              {t("uploading", { percent: Math.round((progress ?? 0) * 100) })}
            </span>
          </>
        ) : null}
      </div>
    </form>
  );
}

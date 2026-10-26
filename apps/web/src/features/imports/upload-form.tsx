"use client";

import { useMutation } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, FileInput, Select } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { textLinkClasses } from "@/components/ui/text-link";
import { touchTarget } from "@/components/ui/touch-target";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { cn } from "@/lib/cn";

import { FILE_ENCODINGS, IMPORT_KINDS, type FileEncoding, type ImportKind } from "./model";

const ACCEPTED_FILES =
  ".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/** Step 1 of the import wizard: choose the kind and file; the preview opens on the import's own page. */
export function UploadForm({ initialKind }: { initialKind: ImportKind }) {
  const t = useTranslations("imports");
  const api = useApi();
  const router = useRouter();
  const errorMessage = useErrorMessage();
  const [kind, setKind] = useState<ImportKind>(initialKind);
  const [encoding, setEncoding] = useState<FileEncoding | "auto">("auto");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | undefined>();

  const upload = useMutation({
    mutationFn: async (selected: File) =>
      unwrap(
        await api.POST("/api/v1/admin/imports", {
          body: { kind, file: selected.name, encoding: encoding === "auto" ? null : encoding },
          bodySerializer: () => {
            const form = new FormData();
            form.append("kind", kind);
            form.append("file", selected);
            if (encoding !== "auto") form.append("encoding", encoding);
            return form;
          },
        }),
      ),
    onSuccess: (created) => router.push(`/admin/imports/${created.id}`),
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setFileError(t("new.fileRequired"));
      return;
    }
    upload.mutate(file);
  };

  return (
    <form onSubmit={submit} noValidate className="flex max-w-xl flex-col gap-6">
      {upload.isError ? (
        <Banner tone="danger" title={t("new.failedTitle")}>
          {errorMessage(upload.error)}
        </Banner>
      ) : null}

      <div className="flex flex-col gap-2">
        <Field label={t("new.kind")} helper={t("new.kindHelper")} required>
          <Select
            name="kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as ImportKind)}
          >
            {IMPORT_KINDS.map((value, index) => (
              <option key={value} value={value}>
                {`${index + 1}. ${t(`kinds.${value}`)}`}
              </option>
            ))}
          </Select>
        </Field>
        <a
          href={`/api/v1/admin/imports/templates/${kind}`}
          download
          className={cn(
            textLinkClasses,
            touchTarget,
            "inline-flex items-center gap-1 self-start text-sm",
          )}
        >
          <Icon icon={Download} />
          {t("new.template")}
        </a>
      </div>

      <Field label={t("new.file")} helper={t("new.fileHelper")} error={fileError} required>
        <FileInput
          name="file"
          accept={ACCEPTED_FILES}
          file={file}
          onFileChange={(selected) => {
            setFile(selected);
            setFileError(undefined);
          }}
        />
      </Field>

      <Field label={t("new.encoding")} helper={t("new.encodingHelper")}>
        <Select
          name="encoding"
          value={encoding}
          onChange={(event) => setEncoding(event.target.value as FileEncoding | "auto")}
        >
          <option value="auto">{t("new.encodings.auto")}</option>
          {FILE_ENCODINGS.map((value) => (
            <option key={value} value={value}>
              {t(`new.encodings.${value}`)}
            </option>
          ))}
        </Select>
      </Field>

      <div>
        <Button type="submit" variant="primary" loading={upload.isPending || upload.isSuccess}>
          {t("new.submit")}
        </Button>
      </div>
    </form>
  );
}

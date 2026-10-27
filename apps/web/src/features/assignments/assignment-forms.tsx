"use client";

import { useMutation } from "@tanstack/react-query";
import { FileUp, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, FileInput, Input, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

export function AssignmentBuilder({ courseOfferingId }: { courseOfferingId: string }) {
  const t = useTranslations("assignments");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [deadline, setDeadline] = useState("");
  const [policy, setPolicy] = useState<"accept" | "penalize" | "reject">("reject");
  const [penalty, setPenalty] = useState("0");
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/assignments", {
          body: {
            course_offering_id: courseOfferingId,
            title,
            instructions,
            deadline: deadline ? new Date(deadline).toISOString() : null,
            available_from: null,
            max_points: 100,
            late_policy: policy,
            late_penalty_percent: Number(penalty),
          },
        }),
      ),
    onSuccess: () => toast({ title: t("saved") }),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <Panel>
      <PanelBody>
        <form onSubmit={submit} className="flex max-w-2xl flex-col gap-4">
          {save.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(save.error)}
            </Banner>
          ) : null}
          <Field label={t("title")} required>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label={t("instructions")}>
            <Textarea
              rows={5}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </Field>
          <Field label={t("deadline")} helper={t("deadlineHelp")}>
            <Input
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("latePolicy")}>
              <Select value={policy} onChange={(e) => setPolicy(e.target.value as typeof policy)}>
                <option value="reject">{t("reject")}</option>
                <option value="accept">{t("accept")}</option>
                <option value="penalize">{t("penalize")}</option>
              </Select>
            </Field>
            <Field label={t("penalty")}>
              <Input
                type="number"
                min={0}
                max={100}
                value={penalty}
                onChange={(e) => setPenalty(e.target.value)}
              />
            </Field>
          </div>
          <Button type="submit" variant="primary" loading={save.isPending}>
            <Icon icon={Save} />
            {t("save")}
          </Button>
        </form>
      </PanelBody>
    </Panel>
  );
}

export function AssignmentSubmission({ assignmentId }: { assignmentId: string }) {
  const t = useTranslations("assignments");
  const api = useApi();
  const errorMessage = useErrorMessage();
  const [file, setFile] = useState<File | null>(null);
  const submit = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error(t("fileRequired"));
      return unwrap(
        await api.POST("/api/v1/assignments/{assignment_id}/submissions", {
          params: { path: { assignment_id: assignmentId } },
          body: {
            object_key: `assignments/${crypto.randomUUID()}/${file.name}`,
            filename: file.name,
            mime: file.type || "application/octet-stream",
            size_bytes: file.size,
          },
        }),
      );
    },
  });
  return (
    <Panel>
      <PanelBody>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit.mutate();
          }}
        >
          {submit.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(submit.error)}
            </Banner>
          ) : null}
          <Field label={t("file")} helper={t("fileHelp")} required>
            <FileInput file={file} onFileChange={setFile} />
          </Field>
          <Button type="submit" variant="primary" loading={submit.isPending}>
            <Icon icon={FileUp} />
            {t("submit")}
          </Button>
        </form>
      </PanelBody>
    </Panel>
  );
}

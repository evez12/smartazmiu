"use client";

import { useMutation } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

export function GradeView({ submissionId }: { submissionId: string }) {
  const t = useTranslations("assignments");
  const api = useApi();
  const errorMessage = useErrorMessage();
  const [points, setPoints] = useState("0");
  const [feedback, setFeedback] = useState("");
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/assignment-submissions/{submission_id}/grade", {
          params: { path: { submission_id: submissionId } },
          body: { points: Number(points), feedback },
        }),
      ),
  });
  return (
    <Panel>
      <PanelBody>
        <form
          className="flex max-w-xl flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          {save.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(save.error)}
            </Banner>
          ) : null}
          <Field label={t("points")} required>
            <Input
              type="number"
              min={0}
              value={points}
              onChange={(e) => setPoints(e.target.value)}
            />
          </Field>
          <Field label={t("feedback")}>
            <Textarea rows={5} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          </Field>
          <Button type="submit" variant="primary" loading={save.isPending}>
            <Icon icon={Check} />
            {t("grade")}
          </Button>
        </form>
      </PanelBody>
    </Panel>
  );
}

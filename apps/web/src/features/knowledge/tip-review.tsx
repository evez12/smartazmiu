"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import type { components } from "@/lib/api/schema";
import { useApi } from "@/lib/api/provider";

type Status = components["schemas"]["TipStatus"];

/** Staff decision on one card: publish, reject, hide, or restore (publish again); nothing is deleted. */
export function TipReview({ tipId, status }: { tipId: string; status: Status }) {
  const t = useTranslations("guides.tipModeration");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const [note, setNote] = useState("");
  const review = useMutation({
    mutationFn: async (next: Status) =>
      unwrap(
        await api.PATCH("/api/v1/moderation/tips/{tip_id}", {
          params: { path: { tip_id: tipId } },
          body: { status: next, note: note.trim() },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("changed") });
      router.refresh();
    },
    onError: () => toast({ title: t("failed"), tone: "danger" }),
  });
  const actions: {
    next: Status;
    label: string;
    variant: "primary" | "secondary" | "destructive";
  }[] =
    status === "pending"
      ? [
          { next: "published", label: t("publish"), variant: "primary" },
          { next: "rejected", label: t("reject"), variant: "destructive" },
        ]
      : status === "published"
        ? [{ next: "hidden", label: t("hide"), variant: "destructive" }]
        : [{ next: "published", label: t("restore"), variant: "secondary" }];
  return (
    <div className="flex flex-col gap-2">
      <Field label={t("note")}>
        <Input value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} />
      </Field>
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => (
          <Button
            key={action.next}
            size="dense"
            variant={action.variant}
            loading={review.isPending && review.variables === action.next}
            onClick={() => review.mutate(action.next)}
          >
            {action.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

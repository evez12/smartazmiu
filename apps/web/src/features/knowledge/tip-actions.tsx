"use client";

import { useMutation } from "@tanstack/react-query";
import { Flag, ThumbsUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { ReportDialog } from "@/features/reports/report-dialog";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

/** Upvote toggle and report for one published card; authors see neither (D-084). */
export function TipActions({
  tipId,
  upvotes,
  upvoted,
  mine,
}: {
  tipId: string;
  upvotes: number;
  upvoted: boolean;
  mine: boolean;
}) {
  const t = useTranslations("guides.tips");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [count, setCount] = useState(upvotes);
  const [on, setOn] = useState(upvoted);
  const [reporting, setReporting] = useState(false);
  const toggle = useMutation({
    mutationFn: async () => {
      const params = { params: { path: { tip_id: tipId } } };
      return unwrap(
        on
          ? await api.DELETE("/api/v1/tips/{tip_id}/upvote", params)
          : await api.PUT("/api/v1/tips/{tip_id}/upvote", params),
      );
    },
    onSuccess: (next) => {
      setCount(next);
      setOn(!on);
    },
    onError: (error) => toast({ title: errorMessage(error), tone: "danger" }),
  });
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted tabular">{t("upvotes", { count })}</span>
      {mine ? null : (
        <>
          <Button
            variant={on ? "secondary" : "tertiary"}
            size="dense"
            aria-pressed={on}
            loading={toggle.isPending}
            onClick={() => toggle.mutate()}
          >
            <Icon icon={ThumbsUp} />
            {on ? t("upvoted") : t("upvote")}
          </Button>
          <Button variant="tertiary" size="dense" onClick={() => setReporting(true)}>
            <Icon icon={Flag} />
            {t("report")}
          </Button>
          {reporting ? (
            <ReportDialog
              open={reporting}
              onOpenChange={setReporting}
              targetType="tip"
              targetId={tipId}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

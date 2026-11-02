"use client";

import { TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";

import { Icon } from "@/components/ui/icon";
import type { components } from "@/lib/api/schema";
import { useFormatters } from "@/lib/use-format";

export type Source = components["schemas"]["SourceOut"];

/**
 * Says whether the cabinet figures are current. When the latest sync failed the data below is the last good copy,
 * and the notice names its time so nobody reads it as today's state (§13.5, D-126). Nothing is shown when all is well
 * except the time of the last sync.
 */
export function SourceNotice({ source }: { source: Source }) {
  const t = useTranslations("cabinet.source");
  const { formatDateTime } = useFormatters();
  if (source.state === "unavailable") {
    return (
      <div
        role="status"
        className="flex items-start gap-3 rounded-panel border border-warning p-3 text-sm"
        data-testid="cabinet-source-unavailable"
      >
        <Icon icon={TriangleAlert} size={20} className="mt-0.5 text-warning" />
        <div className="flex flex-col gap-1">
          <p className="font-medium">{t("unavailableTitle")}</p>
          <p>
            {source.last_synced_at
              ? t("unavailable", { time: formatDateTime(source.last_synced_at) })
              : t("unavailableNever")}
          </p>
        </div>
      </div>
    );
  }
  if (source.state === "never_synced") {
    return (
      <p className="text-sm text-muted" data-testid="cabinet-never-synced">
        {t("neverSynced")}
      </p>
    );
  }
  return source.last_synced_at ? (
    <p className="text-sm text-muted tabular">
      {t("lastSynced", { time: formatDateTime(source.last_synced_at) })}
    </p>
  ) : null;
}

import { useTranslations } from "next-intl";

import type { GuideStats } from "./model";

/** Helped count, helpful rate and response time, as plain text with tabular numerals. */
export function GuideStatsLine({ stats }: { stats: GuideStats }) {
  const t = useTranslations("guides.stats");
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted tabular">
      <span>{t("helped", { count: stats.helped_count })}</span>
      <span>
        {stats.helpful_rate === null
          ? t("noRating")
          : t("helpfulRate", { percent: Math.round(stats.helpful_rate * 100) })}
      </span>
      {stats.avg_response_minutes !== null ? (
        <span>{t("response", { minutes: stats.avg_response_minutes })}</span>
      ) : null}
    </p>
  );
}

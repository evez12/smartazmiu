"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { useFormatters } from "@/lib/use-format";
import { lastSavedAt } from "@/lib/offline/device";

import { InstallPrompt } from "./install-prompt";
import { UpdateBanner } from "./update-banner";
import { useOnline } from "@/lib/use-online";

/**
 * "No connection" with the time of the stored data (§13.6). `cached` is the offline page, where only stored data is
 * shown; `live` is the running app that lost its connection, where chat keeps queueing what is written (D-064).
 */
export function OfflineBanner({
  variant,
  lastUpdated,
}: {
  variant: "live" | "cached";
  lastUpdated: number | null;
}) {
  const t = useTranslations("offline.banner");
  const { formatDateTime } = useFormatters();
  return (
    <Banner tone="warning" title={t("title")}>
      <p>{variant === "live" ? t("live") : t("cached")}</p>
      {lastUpdated ? (
        <p className="text-muted">
          {t("lastUpdated", { time: formatDateTime(new Date(lastUpdated)) })}
        </p>
      ) : null}
    </Banner>
  );
}

/** The non-modal notices above every page of the app: lost connection, new version, install offer. */
export function PwaNotices() {
  const online = useOnline();
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  useEffect(() => {
    if (!online) void lastSavedAt().then(setLastUpdated, () => setLastUpdated(null));
  }, [online]);
  return (
    <div className="flex flex-col gap-3 empty:hidden [&:not(:empty)]:pb-4">
      {online ? null : <OfflineBanner variant="live" lastUpdated={lastUpdated} />}
      <UpdateBanner />
      <InstallPrompt />
    </div>
  );
}

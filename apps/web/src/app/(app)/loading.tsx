import { getTranslations } from "next-intl/server";

import { Panel, PanelBody } from "@/components/ui/panel";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";

/** Mirrors the page header + panel layout so content does not jump when it arrives (§12.4). */
export default async function Loading() {
  const t = await getTranslations("status");
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{t("loading")}</span>
      <div className="flex flex-col gap-2 pb-6">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <Panel>
        <div className="border-b border-border px-4 py-3">
          <Skeleton className="h-5 w-40" />
        </div>
        <PanelBody>
          <SkeletonText lines={2} />
        </PanelBody>
      </Panel>
    </div>
  );
}

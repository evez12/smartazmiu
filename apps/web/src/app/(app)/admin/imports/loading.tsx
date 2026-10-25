import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui/panel";
import { Skeleton, SkeletonTable } from "@/components/ui/skeleton";

/** Page header, then a panel with a table: the shape of the import list and detail pages. */
export default async function Loading() {
  const t = await getTranslations("status");
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{t("loading")}</span>
      <div className="flex flex-col gap-2 pb-6">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <Panel>
        <div className="border-b border-border px-4 py-3">
          <Skeleton className="h-5 w-40" />
        </div>
        <SkeletonTable className="px-4 pb-4" />
      </Panel>
    </div>
  );
}

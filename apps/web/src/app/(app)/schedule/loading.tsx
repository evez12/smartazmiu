import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";

/** Page header, toolbar and day panels with class rows, as on the loaded page (§12.4). */
export default async function Loading() {
  const t = await getTranslations("status");
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{t("loading")}</span>
      <div className="flex flex-col gap-2 pb-6">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="flex justify-between pb-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-8 w-40" />
      </div>
      <Skeleton className="mb-4 h-7 w-64" />
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }, (_, panel) => (
          <Panel key={panel}>
            <div className="border-b border-border px-4 py-3">
              <Skeleton className="h-5 w-48" />
            </div>
            <div className="flex flex-col px-4">
              {Array.from({ length: 3 }, (_, row) => (
                <div key={row} className="flex gap-4 border-b border-border py-3 last:border-b-0">
                  <Skeleton className="h-4 w-24 shrink-0" />
                  <div className="flex flex-1 flex-col gap-2">
                    <Skeleton className="h-4 w-3/5" />
                    <Skeleton className="h-3.5 w-4/5" />
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}

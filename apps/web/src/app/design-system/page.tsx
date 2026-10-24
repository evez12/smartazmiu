import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getTranslations } from "next-intl/server";

import { Wordmark } from "@/components/brand/wordmark";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { InteractiveSpecimens } from "@/features/design-system/interactive";
import { StaticSpecimens } from "@/features/design-system/specimens";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("designSystem");
  return { title: t("title"), robots: { index: false, follow: false } };
}

/** Internal reference page (Sprint 1): every primitive in both themes. Disabled unless explicitly enabled. */
export default async function DesignSystemPage() {
  await connection();
  if (process.env.DESIGN_SYSTEM_ENABLED !== "true") notFound();
  const t = await getTranslations("designSystem");

  return (
    <div className="min-h-dvh bg-bg-subtle">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-border bg-surface px-4">
        <Wordmark />
        <ThemeSwitcher />
      </header>
      <main className="mx-auto flex max-w-[1200px] flex-col gap-12 px-4 py-8">
        <PageHeader title={t("title")} description={t("description")} className="pb-0" />
        <InteractiveSpecimens />
        <div className="grid gap-6 xl:grid-cols-2">
          {(["light", "dark"] as const).map((theme) => (
            <div
              key={theme}
              data-theme={theme}
              className="flex min-w-0 flex-col gap-8 rounded-panel border border-border bg-bg p-4 text-text sm:p-6"
            >
              <p className="text-sm font-medium text-muted">
                {theme === "light" ? t("lightTheme") : t("darkTheme")}
              </p>
              <StaticSpecimens />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

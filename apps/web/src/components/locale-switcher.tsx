"use client";

import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { ToggleGroup } from "radix-ui";

import { Icon } from "@/components/ui/icon";
import { LOCALES, type Locale } from "@/i18n/config";
import { setLocaleCookie } from "@/i18n/client";
import { cn } from "@/lib/cn";
import { HydrationMark } from "@/lib/hydration-mark";

/** Language choice for pages without a signed-in user: it is kept in a cookie only. */
export function LocaleSwitcher({ className }: { className?: string }) {
  const t = useTranslations("locale");
  const current = useLocale();
  const router = useRouter();

  return (
    <>
      <HydrationMark />
      <ToggleGroup.Root
        type="single"
        aria-label={t("label")}
        value={current}
        onValueChange={(value) => {
          if (!value || value === current) return;
          setLocaleCookie(value as Locale);
          router.refresh();
        }}
        className={cn(
          "inline-flex rounded-control border border-border-control bg-surface p-0.5",
          className,
        )}
      >
        <Icon icon={Languages} className="mx-1.5 self-center text-muted" />
        {LOCALES.map((locale) => (
          <ToggleGroup.Item
            key={locale}
            value={locale}
            lang={locale}
            aria-label={t(`names.${locale}`)}
            className={cn(
              "inline-flex h-7 items-center rounded-[2px] px-2 text-sm text-muted transition-colors",
              "hover:text-text data-[state=on]:bg-primary data-[state=on]:text-primary-contrast",
              "pointer-coarse:h-10 pointer-coarse:min-w-11 pointer-coarse:justify-center",
            )}
          >
            {t(`short.${locale}`)}
          </ToggleGroup.Item>
        ))}
      </ToggleGroup.Root>
    </>
  );
}

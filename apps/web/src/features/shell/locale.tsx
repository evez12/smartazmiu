"use client";

import { useMutation } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { MenuGroup, MenuLabel, MenuRadioGroup, MenuRadioItem } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { LOCALES, isLocale, type Locale } from "@/i18n/config";
import { setLocaleCookie } from "@/i18n/client";
import { useApi } from "@/lib/api/provider";
import { unwrap } from "@/lib/api/browser";

/** Saves the choice on the account (so every device follows it), then renders the page again in that language. */
function useChooseLocale() {
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const t = useTranslations("locale");
  return useMutation({
    mutationFn: async (locale: Locale) =>
      unwrap(await api.PUT("/api/v1/me/locale", { body: { locale } })),
    onSuccess: (_, locale) => {
      setLocaleCookie(locale);
      router.refresh();
    },
    onError: () => toast({ title: t("failed"), tone: "danger" }),
  });
}

export function LocaleMenuGroup() {
  const t = useTranslations("locale");
  const current = useLocale();
  const choose = useChooseLocale();
  return (
    <MenuGroup>
      <MenuLabel>{t("label")}</MenuLabel>
      <MenuRadioGroup
        value={current}
        onValueChange={(value) => {
          if (isLocale(value) && value !== current) choose.mutate(value);
        }}
      >
        {LOCALES.map((locale) => (
          <MenuRadioItem key={locale} network="required" value={locale} lang={locale}>
            {t(`names.${locale}`)}
          </MenuRadioItem>
        ))}
      </MenuRadioGroup>
    </MenuGroup>
  );
}

/**
 * The account's language wins over the device's cookie: on a new device, or after a change made elsewhere, the first
 * page shows the browser's language and this switches it once the account is known (D-113).
 */
export function LocaleSync({ preferred }: { preferred: string | null }) {
  const current = useLocale();
  const router = useRouter();
  useEffect(() => {
    if (!isLocale(preferred) || preferred === current) return;
    setLocaleCookie(preferred);
    router.refresh();
  }, [preferred, current, router]);
  return null;
}

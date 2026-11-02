import { render, type RenderOptions } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import type { Locale } from "@/i18n/config";

import az from "../../messages/az.json";
import en from "../../messages/en.json";
import ru from "../../messages/ru.json";

const CATALOGUES = { az, en, ru };

type IntlOptions = Omit<RenderOptions, "wrapper"> & { locale?: Locale };

export function renderWithIntl(ui: ReactElement, { locale = "az", ...options }: IntlOptions = {}) {
  function Providers({ children }: { children: ReactNode }) {
    return (
      <NextIntlClientProvider locale={locale} messages={CATALOGUES[locale]} timeZone="Asia/Baku">
        {children}
      </NextIntlClientProvider>
    );
  }
  return render(ui, { wrapper: Providers, ...options });
}

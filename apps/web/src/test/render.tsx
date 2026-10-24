import { render, type RenderOptions } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import messages from "../../messages/az.json";

function Providers({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="az" messages={messages} timeZone="Asia/Baku">
      {children}
    </NextIntlClientProvider>
  );
}

export function renderWithIntl(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return render(ui, { wrapper: Providers, ...options });
}

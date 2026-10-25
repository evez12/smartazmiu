"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { createContext, useContext, useState, type ReactNode } from "react";

import { ApiRequestError, createBrowserApi, type BrowserApi } from "./browser";

const ApiContext = createContext<BrowserApi | null>(null);

/** Browser API client and mutation state for the signed-in part of the app. */
export function ApiProvider({ csrfToken, children }: { csrfToken: string; children: ReactNode }) {
  const [api] = useState(() => createBrowserApi(csrfToken));
  const [queryClient] = useState(
    () =>
      new QueryClient({
        // Mutations are not retried automatically: the user decides, and every retry is explicit (§1.1).
        defaultOptions: { mutations: { retry: false }, queries: { retry: 1, staleTime: 30_000 } },
      }),
  );
  return (
    <ApiContext value={api}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ApiContext>
  );
}

export function useApi(): BrowserApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi must be used inside <ApiProvider>");
  return api;
}

/** Text for a failed request: the API's localized message, or a network hint when there was no answer. */
export function useErrorMessage(): (error: unknown) => string {
  const t = useTranslations("errors");
  return (error) =>
    error instanceof ApiRequestError && error.message ? error.message : t("network");
}

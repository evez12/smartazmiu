"use client";

import { useEffect } from "react";

/**
 * Marks the document once the page segment around it has hydrated. Until then, server-rendered controls do
 * nothing: a chosen file or a pressed button is lost. Pages stream inside Suspense boundaries that hydrate after
 * the shell, so the mark sits in the page header rather than the root layout. E2E tests wait for it.
 */
export function HydrationMark() {
  useEffect(() => {
    document.documentElement.dataset.hydrated = "true";
  }, []);
  return null;
}

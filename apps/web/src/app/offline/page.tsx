import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { OfflineApp } from "@/features/offline/offline-app";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("offline.page");
  return { title: t("title") };
}

/** The offline shell: public, the same for everyone, and kept by the service worker (D-117). */
export default function OfflinePage() {
  return <OfflineApp />;
}

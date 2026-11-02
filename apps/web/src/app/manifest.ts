import type { MetadataRoute } from "next";
import { getLocale, getTranslations } from "next-intl/server";

import { WORDMARK } from "@/components/brand/brand";
import colours from "@/lib/pwa/theme-colours.json";

/**
 * Web app manifest (§7). It reads the language cookie like every page, so the description follows the chosen
 * language (D-113); the name is the brand and stays the same in all three.
 */
export default async function manifest(): Promise<MetadataRoute.Manifest> {
  const t = await getTranslations("meta");
  return {
    id: "/",
    name: WORDMARK,
    short_name: WORDMARK,
    description: t("description"),
    lang: await getLocale(),
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: colours.light.background,
    theme_color: colours.light.surface,
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}

"use client";

import { Lock } from "lucide-react";
import { useTranslations } from "next-intl";

import { Icon } from "@/components/ui/icon";
import { formatDateTime } from "@/lib/format";

import { REASON_KEYS, type Posting, type PostingReason } from "./model";

/** Plain-language text for a refusal code from the policy (ADR 0004) or the socket (§13.2). */
export function useRefusalText(): (
  code: string | null | undefined,
  detail?: { until?: string | null; retry_after_seconds?: number | null },
) => string {
  const t = useTranslations("chat.reasons");
  return (code, detail = {}) => {
    if (code === "chat.queue_expired") return t("queueExpired");
    const key = code ? REASON_KEYS[code as PostingReason] : undefined;
    if (!key) return t("generic");
    // Without the number of seconds the sentence would say "0 saniyə"; the short form says to wait a little.
    if ((key === "rateLimited" || key === "slowMode") && !detail.retry_after_seconds) {
      return t(`${key}Short`);
    }
    return t(key, {
      until: detail.until ? formatDateTime(detail.until) : "",
      seconds: detail.retry_after_seconds ?? 0,
    });
  };
}

/** Persistent line above the composer explaining why posting is not possible, and until when (§12.7). */
export function PostingBanner({ posting }: { posting: Posting }) {
  const refusal = useRefusalText();
  if (posting.allowed) return null;
  return (
    <p
      role="status"
      className="flex items-start gap-2 border-t border-border bg-bg-subtle px-4 py-3 text-sm text-text"
    >
      <Icon icon={Lock} className="mt-0.5 shrink-0 text-muted" />
      {refusal(posting.reason, posting)}
    </p>
  );
}

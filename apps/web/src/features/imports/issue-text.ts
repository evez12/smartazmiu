import { useTranslations } from "next-intl";

/** Text for a row-level issue code; a code this build does not know yet gets a generic text. */
export function useIssueText(): (code: string) => string {
  const t = useTranslations("imports.issues");
  return (code) => (t.has(code as "unknown") ? t(code as "unknown") : t("unknown"));
}

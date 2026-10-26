import { useTranslations } from "next-intl";

import { Banner } from "@/components/ui/banner";

/** On every guide-facing screen (§5.2): advice from students, not official information. */
export function StudentAdviceDisclaimer({ className }: { className?: string }) {
  const t = useTranslations("guides");
  return (
    <Banner tone="info" title={t("disclaimer")} className={className}>
      {t("disclaimerBody")}
    </Banner>
  );
}

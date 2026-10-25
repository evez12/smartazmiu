import { useTranslations } from "next-intl";

import type { Audience } from "./model";

/** "Qrup · 765a2" or "Bütün universitet"; works in server and client components. */
export function AudienceLabel({ audience }: { audience: Audience }) {
  const t = useTranslations("audiences.types");
  if (audience.type === "university") return <>{t("university")}</>;
  return (
    <>
      {t(audience.type)} · {audience.label}
      {audience.detail ? <span className="text-muted"> ({audience.detail})</span> : null}
    </>
  );
}

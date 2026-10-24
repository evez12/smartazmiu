"use client";

import { RotateCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

/** Error state inside the shell: what happened, what to do, and a retry (§12.8, §13.6). */
export default function AppError({ retry }: { error: unknown; retry: () => void }) {
  const t = useTranslations("status");
  return (
    <Banner
      tone="danger"
      title={t("errorTitle")}
      action={
        <Button size="dense" onClick={() => retry()}>
          <Icon icon={RotateCw} />
          {t("retry")}
        </Button>
      }
    >
      {t("errorBody")}
    </Banner>
  );
}

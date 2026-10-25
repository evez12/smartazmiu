import { Lock } from "lucide-react";
import { useTranslations } from "next-intl";

import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";

/** 403 inside the shell: what is missing and whom to ask (§13.6). */
export function ForbiddenState() {
  const t = useTranslations("status");
  return (
    <Panel>
      <PanelBody className="flex flex-col items-start gap-3 p-6">
        <h1 className="flex items-start gap-2 text-lg font-semibold text-text">
          <Icon icon={Lock} size={20} className="mt-1 text-muted" />
          {t("forbiddenTitle")}
        </h1>
        <p className="max-w-[75ch] text-muted">{t("forbiddenBody")}</p>
        <TextLink href="/">{t("goHome")}</TextLink>
      </PanelBody>
    </Panel>
  );
}

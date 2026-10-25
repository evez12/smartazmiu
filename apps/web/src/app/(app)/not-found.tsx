import { FileQuestion } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";

/** 404 inside the shell (e.g. an import id that does not exist); the root page covers unknown URLs. */
export default async function NotFound() {
  const t = await getTranslations("status");
  return (
    <Panel>
      <PanelBody className="flex flex-col items-start gap-3 p-6">
        <h1 className="flex items-start gap-2 text-lg font-semibold text-text">
          <Icon icon={FileQuestion} size={20} className="mt-1 text-muted" />
          {t("notFoundTitle")}
        </h1>
        <p className="max-w-[75ch] text-muted">{t("notFoundBody")}</p>
        <TextLink href="/">{t("goHome")}</TextLink>
      </PanelBody>
    </Panel>
  );
}

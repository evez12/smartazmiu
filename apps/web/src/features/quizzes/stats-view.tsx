import { BarChart3 } from "lucide-react";
import { useTranslations } from "next-intl";

import { EmptyState } from "@/components/ui/empty-state";
import { Panel, PanelBody } from "@/components/ui/panel";

export function QuizStats() {
  const t = useTranslations("quizzes");
  return (
    <Panel>
      <PanelBody>
        <EmptyState icon={BarChart3} message={t("statsEmpty")} />
      </PanelBody>
    </Panel>
  );
}

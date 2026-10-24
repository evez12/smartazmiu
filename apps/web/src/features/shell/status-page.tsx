import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Wordmark } from "@/components/brand/wordmark";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody } from "@/components/ui/panel";

type StatusPageProps = {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: ReactNode;
};

/** Full-page state shown when the app shell cannot render (inactive account, API down, unknown page). */
export function StatusPage({ icon, title, body, action }: StatusPageProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-bg-subtle">
      <header className="flex h-14 items-center border-b border-border bg-surface px-4">
        <Wordmark />
      </header>
      <main id="main" className="mx-auto w-full max-w-xl px-4 py-12">
        <Panel>
          <PanelBody className="flex flex-col items-start gap-3 p-6">
            <Icon icon={icon} size={20} className="text-muted" />
            <h1 className="text-xl font-semibold">{title}</h1>
            <p className="text-muted">{body}</p>
            {action ? <div className="mt-2 flex flex-wrap gap-2">{action}</div> : null}
          </PanelBody>
        </Panel>
      </main>
    </div>
  );
}

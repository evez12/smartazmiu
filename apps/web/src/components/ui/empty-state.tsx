import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";

type EmptyStateProps = {
  /** One sentence explaining why nothing is shown (§12.4). */
  message: string;
  /** The next step the user can take. */
  action?: ReactNode;
  icon?: LucideIcon;
  className?: string;
};

export function EmptyState({ message, action, icon, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-start gap-3 py-6", className)}>
      <div className="flex items-start gap-2 text-muted">
        {icon ? <Icon icon={icon} size={20} className="mt-px" /> : null}
        <p className="max-w-[75ch]">{message}</p>
      </div>
      {action}
    </div>
  );
}

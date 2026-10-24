import { cva, type VariantProps } from "class-variance-authority";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";

const tagVariants = cva(
  "inline-flex h-5 max-w-full items-center gap-1 rounded-control border bg-surface px-1.5 text-xs font-medium whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "border-border-strong text-muted",
        info: "border-info text-info",
        success: "border-success text-success",
        warning: "border-warning text-warning",
        danger: "border-danger text-danger",
        accent: "border-accent text-accent",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

type TagProps = VariantProps<typeof tagVariants> & {
  /** Status tags always carry text; colour alone never conveys the status (§12.2). */
  children: string;
  icon?: LucideIcon;
  className?: string;
};

export function Tag({ tone, icon, className, children }: TagProps) {
  return (
    <span className={cn(tagVariants({ tone }), className)}>
      {icon ? <Icon icon={icon} size={16} className="-ml-0.5 size-3.5" /> : null}
      <span className="truncate">{children}</span>
    </span>
  );
}

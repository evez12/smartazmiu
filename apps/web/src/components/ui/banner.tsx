"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Button } from "./button";
import { Icon } from "./icon";

const bannerVariants = cva(
  "flex items-start gap-3 rounded-control border border-l-4 border-border-strong bg-surface p-3",
  {
    variants: {
      tone: {
        info: "border-l-info",
        success: "border-l-success",
        warning: "border-l-warning",
        danger: "border-l-danger",
      },
    },
    defaultVariants: { tone: "info" },
  },
);

const toneIcon = {
  info: { icon: Info, className: "text-info" },
  success: { icon: CircleCheck, className: "text-success" },
  warning: { icon: TriangleAlert, className: "text-warning" },
  danger: { icon: CircleAlert, className: "text-danger" },
} as const;

type BannerProps = VariantProps<typeof bannerVariants> & {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  onDismiss?: () => void;
  className?: string;
};

/** Inline page-level message. Errors interrupt screen readers; other tones are announced politely. */
export function Banner({ tone, title, children, action, onDismiss, className }: BannerProps) {
  const t = useTranslations("ui");
  const resolvedTone = tone ?? "info";
  const { icon, className: iconClassName } = toneIcon[resolvedTone];
  return (
    <div
      role={resolvedTone === "danger" ? "alert" : "status"}
      className={cn(bannerVariants({ tone }), className)}
    >
      <Icon icon={icon} size={20} className={cn("mt-px", iconClassName)} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="font-medium text-text">{title}</p>
        {children ? <div className="text-text">{children}</div> : null}
        {action ? <div className="mt-1 flex flex-wrap gap-2">{action}</div> : null}
      </div>
      {onDismiss ? (
        <Button variant="tertiary" size="icon-dense" onClick={onDismiss} aria-label={t("close")}>
          <Icon icon={X} />
        </Button>
      ) : null}
    </div>
  );
}

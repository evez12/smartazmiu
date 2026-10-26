import { cva, type VariantProps } from "class-variance-authority";
import { LoaderCircle } from "lucide-react";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";
import { touchTarget } from "./touch-target";

export const buttonVariants = cva(
  [
    "inline-flex shrink-0 items-center justify-center gap-2 rounded-control border font-medium whitespace-nowrap",
    "transition-colors select-none disabled:cursor-not-allowed disabled:opacity-60 aria-busy:cursor-progress",
    touchTarget,
  ],
  {
    variants: {
      variant: {
        primary: "border-transparent bg-primary text-primary-contrast hover:bg-primary-hover",
        secondary: "border-border-control bg-surface text-text hover:bg-bg-subtle",
        tertiary: "border-transparent bg-transparent text-primary hover:bg-bg-subtle",
        destructive: "border-danger bg-surface text-danger hover:bg-bg-subtle",
        /** Only inside confirmation dialogs (§12.4). */
        "destructive-solid": "border-transparent bg-danger text-primary-contrast hover:opacity-90",
      },
      size: {
        default: "h-9 px-4 text-base",
        dense: "h-8 px-3 text-sm",
        icon: "size-9 p-0",
        "icon-dense": "size-8 p-0",
      },
    },
    defaultVariants: { variant: "secondary", size: "default" },
  },
);

type ButtonProps = ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
    /** In-place action running: keeps the label, shows a spinner and blocks repeat submits. */
    loading?: boolean;
  };

export function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  disabled,
  children,
  type,
  ...rest
}: ButtonProps) {
  const classes = cn(buttonVariants({ variant, size }), className);
  if (asChild) {
    return (
      <Slot.Root className={classes} {...rest}>
        {children}
      </Slot.Root>
    );
  }
  return (
    <button
      type={type ?? "button"}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Icon icon={LoaderCircle} className="animate-spin" /> : null}
      {children}
    </button>
  );
}

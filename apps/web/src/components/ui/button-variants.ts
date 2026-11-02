import { cva } from "class-variance-authority";

import { touchTarget } from "./touch-target";

/**
 * Button classes, kept apart from the component so that server components can put them on a link
 * (`<Link className={buttonVariants()}>`): the component itself is a client component (it follows the connection).
 */
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

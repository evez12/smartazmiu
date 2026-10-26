import Link from "next/link";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

import { touchTarget } from "./touch-target";

/** Shared with plain anchors (file downloads), which must not go through client-side navigation. */
export const textLinkClasses =
  "rounded-control text-primary underline underline-offset-2 hover:text-primary-hover";

type TextLinkProps = ComponentProps<typeof Link> & {
  /** Set for links inside a sentence: WCAG exempts them from the target size, and a tap area would cover the words around them. */
  inline?: boolean;
};

export function TextLink({ className, inline = false, ...rest }: TextLinkProps) {
  return <Link className={cn(textLinkClasses, !inline && touchTarget, className)} {...rest} />;
}

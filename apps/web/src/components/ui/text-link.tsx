import Link from "next/link";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

/** Shared with plain anchors (file downloads), which must not go through client-side navigation. */
export const textLinkClasses =
  "rounded-control text-primary underline underline-offset-2 hover:text-primary-hover";

export function TextLink({ className, ...rest }: ComponentProps<typeof Link>) {
  return <Link className={cn(textLinkClasses, className)} {...rest} />;
}

import Link from "next/link";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

export function TextLink({ className, ...rest }: ComponentProps<typeof Link>) {
  return (
    <Link
      className={cn(
        "rounded-control text-primary underline underline-offset-2 hover:text-primary-hover",
        className,
      )}
      {...rest}
    />
  );
}

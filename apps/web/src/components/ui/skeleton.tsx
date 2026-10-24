import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

/** Placeholder block shaped like the content it replaces; never a full-page spinner (§12.4). */
export function Skeleton({ className, ...rest }: ComponentProps<"div">) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-control bg-border", className)}
      {...rest}
    />
  );
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div aria-hidden="true" className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} className={cn("h-3.5", index === lines - 1 ? "w-3/5" : "w-full")} />
      ))}
    </div>
  );
}

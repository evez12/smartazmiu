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

/** Placeholder for a data table: a header line and rows of the same height as real rows (40 px). */
export function SkeletonTable({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div aria-hidden="true" className={cn("flex flex-col", className)}>
      <div className="flex h-10 items-center border-b border-border-strong">
        <Skeleton className="h-3.5 w-1/3" />
      </div>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex h-10 items-center gap-4 border-b border-border">
          <Skeleton className="h-3.5 w-2/5" />
          <Skeleton className="h-3.5 w-1/5" />
          <Skeleton className="h-3.5 w-1/6" />
        </div>
      ))}
    </div>
  );
}

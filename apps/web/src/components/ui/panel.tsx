import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Flat bordered surface (§12.1): no shadow, 6 px radius, never nested inside another panel. */
export function Panel({ className, ...rest }: ComponentProps<"section">) {
  return (
    <section className={cn("rounded-panel border border-border bg-surface", className)} {...rest} />
  );
}

type PanelHeaderProps = {
  title: ReactNode;
  /** Lets the panel name itself after its title (`aria-labelledby`), so it is a navigable region. */
  titleId?: string;
  description?: ReactNode;
  action?: ReactNode;
  headingLevel?: 2 | 3;
  className?: string;
};

export function PanelHeader({
  title,
  titleId,
  description,
  action,
  headingLevel = 2,
  className,
}: PanelHeaderProps) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <header
      className={cn(
        "flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3",
        className,
      )}
    >
      <div className="flex min-w-0 flex-col">
        <Heading id={titleId} className="text-md font-semibold text-text">
          {title}
        </Heading>
        {description ? <p className="text-sm text-muted">{description}</p> : null}
      </div>
      {action}
    </header>
  );
}

export function PanelBody({ className, ...rest }: ComponentProps<"div">) {
  return <div className={cn("p-4", className)} {...rest} />;
}

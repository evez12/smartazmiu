"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";

/*
 * Compact data table (§12.4): 40 px rows, sticky header, no zebra striping, right-aligned numbers.
 * Below `md` the rows stack and every cell shows its column label, so the page never scrolls sideways.
 */

export function Table({ className, ...rest }: ComponentProps<"table">) {
  return (
    <table
      className={cn("w-full border-collapse text-base max-md:block max-md:min-w-0", className)}
      {...rest}
    />
  );
}

export function TableHeader({ className, ...rest }: ComponentProps<"thead">) {
  return (
    <thead
      className={cn("max-md:sr-only md:sticky md:top-0 md:z-10 md:bg-surface", className)}
      {...rest}
    />
  );
}

export function TableBody({ className, ...rest }: ComponentProps<"tbody">) {
  return <tbody className={cn("max-md:block max-md:min-w-0", className)} {...rest} />;
}

export function TableRow({ className, ...rest }: ComponentProps<"tr">) {
  return (
    <tr
      className={cn(
        "border-b border-border transition-colors md:h-10 md:hover:bg-bg-subtle",
        "max-md:flex max-md:flex-col max-md:gap-1 max-md:py-3",
        className,
      )}
      {...rest}
    />
  );
}

export type SortDirection = "ascending" | "descending" | "none";

type TableHeadProps = ComponentProps<"th"> & {
  numeric?: boolean;
  sort?: SortDirection;
  onSort?: () => void;
};

export function TableHead({ numeric, sort, onSort, className, children, ...rest }: TableHeadProps) {
  const t = useTranslations("ui");
  const sortable = onSort !== undefined;
  const sortIcon = sort === "ascending" ? ArrowUp : sort === "descending" ? ArrowDown : ArrowUpDown;
  return (
    <th
      scope="col"
      aria-sort={sortable ? (sort ?? "none") : undefined}
      className={cn(
        "h-10 border-b border-border-strong px-3 text-left text-sm font-medium text-muted",
        numeric && "text-right",
        className,
      )}
      {...rest}
    >
      {sortable ? (
        <button
          type="button"
          onClick={onSort}
          className={cn(
            "inline-flex items-center gap-1 rounded-control hover:text-text",
            numeric && "flex-row-reverse",
          )}
          aria-label={t("sortBy", { column: String(children) })}
        >
          {children}
          <Icon icon={sortIcon} className={sort && sort !== "none" ? "text-text" : undefined} />
        </button>
      ) : (
        children
      )}
    </th>
  );
}

type TableCellProps = ComponentProps<"td"> & {
  /** Column label repeated in the stacked mobile layout. */
  label: string;
  numeric?: boolean;
  children: ReactNode;
};

export function TableCell({ label, numeric, className, children, ...rest }: TableCellProps) {
  return (
    <td
      data-label={label}
      className={cn(
        "px-3 text-text md:py-2",
        numeric && "tabular md:text-right",
        "max-md:flex max-md:min-w-0 max-md:justify-between max-md:gap-4 max-md:px-0 max-md:[&>*]:min-w-0",
        "max-md:before:text-sm max-md:before:text-muted max-md:before:content-[attr(data-label)]",
        className,
      )}
      {...rest}
    >
      {children}
    </td>
  );
}

export function TableCaption({ className, ...rest }: ComponentProps<"caption">) {
  return <caption className={cn("sr-only", className)} {...rest} />;
}

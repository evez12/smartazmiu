import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";

import { buttonVariants } from "./button";
import { Icon } from "./icon";

type PaginationProps = {
  /** 1-based. */
  page: number;
  pageSize: number;
  total: number;
  /** Link for another page; keeps the table's other query parameters. */
  href: (page: number) => string;
  className?: string;
};

/** Offset pagination for admin tables (§4.2) with the total count (§12.4). */
export function Pagination({ page, pageSize, total, href, className }: PaginationProps) {
  const t = useTranslations("ui.pagination");
  if (total <= pageSize && page === 1) return null;
  const from = Math.min((page - 1) * pageSize + 1, total);
  const to = Math.min(page * pageSize, total);
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const link = buttonVariants({ variant: "secondary", size: "dense" });
  const disabled = cn(link, "pointer-events-none opacity-60");
  return (
    <nav
      aria-label={t("label")}
      className={cn("flex flex-wrap items-center justify-between gap-3", className)}
    >
      <p className="text-sm text-muted tabular">
        {t("range", { from: formatNumber(from), to: formatNumber(to), total: formatNumber(total) })}
      </p>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link href={href(page - 1)} className={link} rel="prev">
            <Icon icon={ChevronLeft} />
            {t("previous")}
          </Link>
        ) : (
          <span aria-disabled="true" className={disabled}>
            <Icon icon={ChevronLeft} />
            {t("previous")}
          </span>
        )}
        {page < pages ? (
          <Link href={href(page + 1)} className={link} rel="next">
            {t("next")}
            <Icon icon={ChevronRight} />
          </Link>
        ) : (
          <span aria-disabled="true" className={disabled}>
            {t("next")}
            <Icon icon={ChevronRight} />
          </span>
        )}
      </div>
    </nav>
  );
}

/** Reads a 1-based page number from a search parameter, falling back to the first page. */
export function pageFromParam(value: string | string[] | undefined): number {
  const page = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(page) && page > 0 ? page : 1;
}

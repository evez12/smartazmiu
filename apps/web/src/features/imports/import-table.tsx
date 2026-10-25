import { useTranslations } from "next-intl";

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { formatDateTime, formatNumber } from "@/lib/format";

import { displayStatus, STATUS_TONE, type ImportOut } from "./model";

export function ImportTable({ items, now }: { items: ImportOut[]; now: Date }) {
  const t = useTranslations("imports");
  return (
    <Table>
      <TableCaption>{t("recentTitle")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.file")}</TableHead>
          <TableHead>{t("columns.kind")}</TableHead>
          <TableHead>{t("columns.status")}</TableHead>
          <TableHead numeric>{t("columns.rows")}</TableHead>
          <TableHead>{t("columns.result")}</TableHead>
          <TableHead>{t("columns.createdBy")}</TableHead>
          <TableHead>{t("columns.createdAt")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const status = displayStatus(item, now);
          return (
            <TableRow key={item.id}>
              <TableCell label={t("columns.file")} className="max-w-64">
                <TextLink href={`/admin/imports/${item.id}`} className="break-all">
                  {item.file_name}
                </TextLink>
              </TableCell>
              <TableCell label={t("columns.kind")}>{t(`kinds.${item.kind}`)}</TableCell>
              <TableCell label={t("columns.status")}>
                <Tag tone={STATUS_TONE[status]}>{t(`statuses.${status}`)}</Tag>
              </TableCell>
              <TableCell label={t("columns.rows")} numeric>
                {formatNumber(item.row_count)}
              </TableCell>
              <TableCell label={t("columns.result")} className="text-sm">
                {item.status === "invalid" ? "—" : t("result", item.summary)}
              </TableCell>
              <TableCell label={t("columns.createdBy")}>
                {item.created_by?.display_name ?? t("system")}
              </TableCell>
              <TableCell label={t("columns.createdAt")} className="whitespace-nowrap tabular">
                {formatDateTime(item.created_at)}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

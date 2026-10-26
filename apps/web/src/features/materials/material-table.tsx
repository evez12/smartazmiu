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
import { formatDate } from "@/lib/format";
import { formatSize } from "@/lib/uploads";

import { materialHref, type Material } from "./model";
import { VersionActions } from "./version-actions";

/** A subject's catalogue (§6.1): one row per material, its newest clean file and the actions on it. */
export function MaterialTable({
  items,
  caption,
  showSemester,
}: {
  items: Material[];
  caption: string;
  showSemester: boolean;
}) {
  const t = useTranslations("materials");
  return (
    <Table>
      <TableCaption>{caption}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.title")}</TableHead>
          <TableHead>{t("columns.type")}</TableHead>
          {showSemester ? <TableHead>{t("columns.semester")}</TableHead> : null}
          <TableHead>{t("columns.file")}</TableHead>
          <TableHead>{t("columns.updated")}</TableHead>
          <TableHead>{t("columns.actions")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell label={t("columns.title")} className="max-w-md">
              <span className="flex flex-col items-start gap-1">
                <TextLink
                  href={materialHref(item.subject_id, item.id)}
                  className="font-medium break-words"
                >
                  {item.title}
                </TextLink>
                <span className="flex flex-wrap gap-1">
                  {item.hidden ? <Tag tone="warning">{t("hidden")}</Tag> : null}
                  {item.scanning ? <Tag tone="info">{t("scanning")}</Tag> : null}
                </span>
              </span>
            </TableCell>
            <TableCell label={t("columns.type")}>{t(`types.${item.type}`)}</TableCell>
            {showSemester ? (
              <TableCell label={t("columns.semester")} className="whitespace-nowrap">
                {item.semester.label}
              </TableCell>
            ) : null}
            <TableCell label={t("columns.file")}>
              {item.current ? (
                <span className="flex flex-col">
                  <span className="break-all">{item.current.filename}</span>
                  <span className="text-sm text-muted tabular">
                    {formatSize(item.current.size_bytes)} ·{" "}
                    {t("versionCount", { count: item.version_count })}
                  </span>
                </span>
              ) : (
                <span className="text-muted">{t("notChecked")}</span>
              )}
            </TableCell>
            <TableCell label={t("columns.updated")} className="whitespace-nowrap tabular">
              {formatDate(item.current?.created_at ?? item.created_at)}
            </TableCell>
            <TableCell label={t("columns.actions")}>
              {item.current ? <VersionActions version={item.current} /> : null}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

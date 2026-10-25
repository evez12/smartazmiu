import { useTranslations } from "next-intl";

import { Banner } from "@/components/ui/banner";
import { EmptyState } from "@/components/ui/empty-state";
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
import type { components } from "@/lib/api/schema";
import { formatDateTime } from "@/lib/format";

export type MyConsents = components["schemas"]["MyConsentsOut"];

export const NOTICE_SECTIONS = [
  "data",
  "purpose",
  "visibility",
  "rights",
  "retention",
  "contact",
] as const;

/** Shown until the current notice version is acknowledged; never blocks using the platform. */
export function NoticePrompt({ consents }: { consents: MyConsents }) {
  const t = useTranslations("privacy");
  if (consents.notice_acknowledged_at) return null;
  return (
    <Banner
      tone="info"
      title={t("promptTitle")}
      action={<TextLink href="/privacy">{t("promptLink")}</TextLink>}
    >
      {t("promptBody")}
    </Banner>
  );
}

export function ConsentHistory({ consents }: { consents: MyConsents }) {
  const t = useTranslations("profile.data");
  if (consents.history.length === 0) {
    return <EmptyState className="py-0" message={t("historyEmpty")} />;
  }
  return (
    <Table>
      <TableCaption>{t("historyTitle")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.time")}</TableHead>
          <TableHead>{t("columns.purpose")}</TableHead>
          <TableHead>{t("columns.decision")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {consents.history.map((record) => (
          <TableRow key={`${record.purpose}-${record.recorded_at}`}>
            <TableCell label={t("columns.time")} className="whitespace-nowrap tabular">
              {formatDateTime(record.recorded_at)}
            </TableCell>
            <TableCell label={t("columns.purpose")}>{t(`purposes.${record.purpose}`)}</TableCell>
            <TableCell label={t("columns.decision")}>
              <Tag tone={record.granted ? "success" : "neutral"}>
                {record.granted ? t("granted") : t("withdrawn")}
              </Tag>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

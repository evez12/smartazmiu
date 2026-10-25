import { useTranslations } from "next-intl";

import { Banner } from "@/components/ui/banner";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime, formatNumber } from "@/lib/format";

import { DownloadReportButton } from "./import-actions";
import { useIssueText } from "./issue-text";
import type { DisplayStatus, ImportDetail } from "./model";

export function ImportStatusBanner({
  record,
  status,
}: {
  record: ImportDetail;
  status: DisplayStatus;
}) {
  const t = useTranslations("imports.detail");
  switch (status) {
    case "ready":
      return record.previously_applied_at ? (
        <Banner tone="info" title={t("alreadyAppliedTitle")}>
          {t("alreadyAppliedBody", { date: formatDateTime(record.previously_applied_at) })}
        </Banner>
      ) : (
        <Banner tone="success" title={t("readyTitle")}>
          {t("readyBody", { expires: formatDateTime(record.expires_at ?? record.created_at) })}
        </Banner>
      );
    case "invalid":
      return (
        <Banner
          tone="danger"
          title={t("invalidTitle", { count: formatNumber(record.error_count) })}
        >
          {t("invalidBody")}
        </Banner>
      );
    case "applied":
      return (
        <Banner tone="success" title={t("appliedTitle")}>
          {t("appliedBody", { date: formatDateTime(record.applied_at ?? record.created_at) })}
        </Banner>
      );
    case "failed":
      return (
        <Banner tone="danger" title={t("failedTitle")}>
          {t("failedBody")}
        </Banner>
      );
    case "expired":
      return (
        <Banner tone="warning" title={t("expiredTitle")}>
          {t("expiredBody")}
        </Banner>
      );
  }
}

/** Non-UTF-8 CSV files are read with a detected code page; the result is shown, never assumed (§13.5). */
export function EncodingBanner({ record }: { record: ImportDetail }) {
  const t = useTranslations("imports");
  if (!record.encoding || record.encoding === "utf-8") return null;
  return (
    <Banner
      tone="warning"
      title={t("detail.encodingTitle", { encoding: t(`new.encodings.${record.encoding}`) })}
    >
      {t("detail.encodingBody")}
    </Banner>
  );
}

export function ImportSummary({ record }: { record: ImportDetail }) {
  const t = useTranslations("imports");
  const facts = [
    { label: t("detail.rows"), value: formatNumber(record.row_count) },
    { label: t("detail.created"), value: formatNumber(record.summary.created) },
    { label: t("detail.updated"), value: formatNumber(record.summary.updated) },
    { label: t("detail.unchanged"), value: formatNumber(record.summary.unchanged) },
    {
      label: t("detail.encoding"),
      value: record.encoding ? t(`new.encodings.${record.encoding}`) : "XLSX",
    },
    ...(record.applied_by
      ? [{ label: t("detail.appliedBy"), value: record.applied_by.display_name }]
      : []),
  ];
  return (
    <Panel>
      <PanelHeader title={t("detail.summaryTitle")} />
      <PanelBody>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
          {facts.map((fact) => (
            <div key={fact.label} className="flex flex-col">
              <dt className="text-sm text-muted">{fact.label}</dt>
              <dd className="text-text tabular">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </PanelBody>
    </Panel>
  );
}

export function ImportIssues({ record }: { record: ImportDetail }) {
  const t = useTranslations("imports");
  const describe = useIssueText();
  if (record.errors.length === 0) return null;
  return (
    <Panel>
      <PanelHeader
        title={t("detail.errorsTitle")}
        description={
          record.error_count > record.errors.length
            ? t("detail.errorsTruncated", {
                shown: formatNumber(record.errors.length),
                total: formatNumber(record.error_count),
              })
            : undefined
        }
        action={<DownloadReportButton fileName={record.file_name} issues={record.errors} />}
      />
      <div className="px-4 pb-2">
        <Table>
          <TableCaption>{t("detail.errorsTitle")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead numeric className="w-20">
                {t("detail.row")}
              </TableHead>
              <TableHead className="w-48">{t("detail.column")}</TableHead>
              <TableHead>{t("detail.problem")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {record.errors.map((issue, index) => (
              <TableRow key={`${issue.row}-${issue.column}-${issue.code}-${index}`}>
                <TableCell label={t("detail.row")} numeric>
                  {issue.row === null ? t("detail.wholeFile") : issue.row}
                </TableCell>
                <TableCell label={t("detail.column")} className="font-mono text-sm">
                  {issue.column ?? "—"}
                </TableCell>
                <TableCell label={t("detail.problem")}>{describe(issue.code)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Panel>
  );
}

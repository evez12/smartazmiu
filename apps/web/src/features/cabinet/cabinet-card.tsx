"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";

import { SourceNotice } from "./source-notice";
import { formatAverage, useTranscript } from "./transcript-page";

/**
 * The cabinet's own cumulative figure beside the calculator (D-126). The calculator keeps counting the registry
 * results under the rules of D-100; this card only shows what the cabinet reports, with its sync time, and never
 * feeds the simulator. It stays out of the way when there is nothing to show or the call fails.
 */
export function CabinetCard() {
  const t = useTranslations("cabinet.gpaCard");
  const query = useTranscript();
  const data = query.data;
  if (!data || (data.student === null && data.source.state !== "unavailable")) return null;
  const differs = data.semesters.reduce(
    (sum, semester) => sum + semester.courses.filter((course) => course.differs).length,
    0,
  );
  return (
    <Panel aria-labelledby="cabinet-card">
      <PanelHeader title={t("title")} titleId="cabinet-card" description={t("description")} />
      <PanelBody className="flex flex-col gap-3">
        <SourceNotice source={data.source} />
        {data.student ? (
          <p className="tabular">
            <span className="text-3xl font-semibold" data-testid="cabinet-card-average">
              {formatAverage(data.student.cumulative_average)}
            </span>
            <span className="ml-2 text-sm text-muted">
              {t("credits", { n: data.student.credits_earned })}
            </span>
          </p>
        ) : null}
        {differs > 0 ? <p className="text-sm">{t("differs", { count: differs })}</p> : null}
        <p className="text-sm">
          <Link href="/transcript" className="text-primary underline">
            {t("open")}
          </Link>
        </p>
      </PanelBody>
    </Panel>
  );
}

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { AcknowledgeButton } from "@/features/privacy/acknowledge-button";
import { NOTICE_SECTIONS } from "@/features/privacy/privacy-parts";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("privacy");
  return { title: t("title") };
}

export default async function PrivacyPage() {
  const t = await getTranslations("privacy");
  const result = await loaded(await (await serverApi()).GET("/api/v1/me/consents"));
  const header = (
    <PageHeader
      title={t("title")}
      description={t("description")}
      breadcrumb={[{ label: t("title") }]}
    />
  );
  if (result.status !== "ok") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }

  const consents = result.data;
  return (
    <>
      {header}
      <Panel>
        <PanelBody className="flex flex-col gap-6 p-6">
          <p className="text-sm text-muted">
            {t("versionLabel", { version: consents.notice_version })} · {t("draftNote")}
          </p>
          {/* Public-body reading size and line length (§12.3). */}
          <div className="flex max-w-[75ch] flex-col gap-6 text-md">
            {NOTICE_SECTIONS.map((section) => (
              <section key={section} className="flex flex-col gap-2">
                <h2 className="text-lg font-semibold text-text">
                  {t(`sections.${section}.title`)}
                </h2>
                <p className="text-text">{t(`sections.${section}.body`)}</p>
              </section>
            ))}
          </div>
          {consents.notice_acknowledged_at ? (
            <p className="text-muted">
              {t("acknowledgedAt", { date: formatDate(consents.notice_acknowledged_at) })}
            </p>
          ) : (
            <AcknowledgeButton version={consents.notice_version} />
          )}
        </PanelBody>
      </Panel>
    </>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Banner } from "@/components/ui/banner";
import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { FeedbackButton } from "@/features/feedback/feedback-dialog";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("support");
  return { title: t("title") };
}

/** Where to get help during the pilot (D-074, D-081): the support channel, the feedback form, answer times. */
export default async function SupportPage() {
  const t = await getTranslations("support");
  const channels = await loaded(await (await serverApi()).GET("/api/v1/chat/channels"));
  const support =
    channels.status === "ok"
      ? channels.data.channels.find((channel) => channel.type === "support")
      : undefined;

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
      />
      <Panel>
        <PanelBody className="flex max-w-[75ch] flex-col gap-8 p-6 text-md">
          <section aria-labelledby="support-channel" className="flex flex-col gap-3">
            <h2 id="support-channel" className="text-lg font-semibold">
              {t("channel.title")}
            </h2>
            {support ? (
              <>
                <p>{t("channel.body")}</p>
                <div>
                  <Link
                    href={`/chat/${support.id}`}
                    className={buttonVariants({ variant: "secondary" })}
                  >
                    {t("channel.open")}
                  </Link>
                </div>
              </>
            ) : channels.status === "ok" ? (
              <p>{t("channel.notMember")}</p>
            ) : (
              <Banner tone="warning" title={t("channel.unavailable")} />
            )}
          </section>
          <section aria-labelledby="support-feedback" className="flex flex-col gap-3">
            <h2 id="support-feedback" className="text-lg font-semibold">
              {t("feedback.title")}
            </h2>
            <p>{t("feedback.body")}</p>
            <div>
              <FeedbackButton />
            </div>
          </section>
          <section aria-labelledby="support-hours" className="flex flex-col gap-3">
            <h2 id="support-hours" className="text-lg font-semibold">
              {t("hours.title")}
            </h2>
            <p>{t("hours.body")}</p>
            <p className="text-muted">{t("privacy")}</p>
          </section>
        </PanelBody>
      </Panel>
    </>
  );
}

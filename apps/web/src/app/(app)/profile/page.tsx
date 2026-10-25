import { Download } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";
import { GroupFacts } from "@/features/academics/my-academics";
import { ConsentHistory } from "@/features/privacy/privacy-parts";
import { PhotoControls } from "@/features/profile/photo-controls";
import { ProfileForm } from "@/features/profile/profile-form";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("profile");
  return { title: t("title") };
}

export default async function ProfilePage() {
  const t = await getTranslations("profile");
  const api = await serverApi();
  const [profile, academics, consents] = await Promise.all([
    api.GET("/api/v1/me/profile").then(loaded),
    api.GET("/api/v1/me/academics").then(loaded),
    api.GET("/api/v1/me/consents").then(loaded),
  ]);
  const header = (
    <PageHeader
      title={t("title")}
      description={t("description")}
      breadcrumb={[{ label: t("title") }]}
    />
  );
  if (profile.status !== "ok" || academics.status !== "ok" || consents.status !== "ok") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }

  const me = profile.data;
  const group = academics.data.group;
  const identity = [
    { label: t("name"), value: me.display_name },
    { label: t("email"), value: me.email ?? t("notAssigned") },
    { label: t("universityId"), value: me.university_id ?? t("notAssigned") },
  ];
  return (
    <>
      {header}
      <div className="flex flex-col gap-6">
        <Panel>
          <PanelHeader title={t("identityTitle")} description={t("identityHint")} />
          <PanelBody className="flex flex-col gap-6">
            <PhotoControls displayName={me.display_name} photoUrl={me.photo_url} />
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
              {identity.map((fact) => (
                <div key={fact.label} className="flex min-w-0 flex-col">
                  <dt className="text-sm text-muted">{fact.label}</dt>
                  <dd className="break-all text-text tabular">{fact.value}</dd>
                </div>
              ))}
            </dl>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title={t("academicTitle")} />
          <PanelBody>
            {group ? (
              <GroupFacts group={group} />
            ) : (
              <EmptyState className="py-0" message={t("noGroup")} />
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title={t("settingsTitle")} />
          <PanelBody className="p-6">
            {/* Keyed by version so a refresh after saving resets the form to the stored values. */}
            <ProfileForm key={me.version} profile={me} />
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title={t("data.title")} description={t("data.description")} />
          <PanelBody className="flex flex-col gap-6">
            <div className="flex flex-col items-start gap-2">
              {/* A plain download: the proxy adds the token, the API sets the file name. */}
              <a href="/api/v1/me/export" download className={buttonVariants()}>
                <Icon icon={Download} />
                {t("data.export")}
              </a>
              <p className="max-w-[75ch] text-sm text-muted">{t("data.exportHelper")}</p>
            </div>
            <div className="flex flex-col gap-1">
              <h3 className="font-medium text-text">{t("data.notice")}</h3>
              <p className="text-muted">
                {consents.data.notice_acknowledged_at
                  ? t("data.noticeAcknowledged", {
                      version: consents.data.notice_version,
                      date: formatDate(consents.data.notice_acknowledged_at),
                    })
                  : t("data.noticePending", { version: consents.data.notice_version })}{" "}
                <TextLink href="/privacy">{t("data.noticeLink")}</TextLink>
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="font-medium text-text">{t("data.historyTitle")}</h3>
              <ConsentHistory consents={consents.data} />
            </div>
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}

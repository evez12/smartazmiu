import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { GroupFacts } from "@/features/academics/my-academics";
import { PhotoControls } from "@/features/profile/photo-controls";
import { ProfileForm } from "@/features/profile/profile-form";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("profile");
  return { title: t("title") };
}

export default async function ProfilePage() {
  const t = await getTranslations("profile");
  const api = await serverApi();
  const [profile, academics] = await Promise.all([
    api.GET("/api/v1/me/profile").then(loaded),
    api.GET("/api/v1/me/academics").then(loaded),
  ]);
  const header = (
    <PageHeader
      title={t("title")}
      description={t("description")}
      breadcrumb={[{ label: t("title") }]}
    />
  );
  if (profile.status !== "ok" || academics.status !== "ok") {
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
      </div>
    </>
  );
}

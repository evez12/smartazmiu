import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { PushDevice } from "@/features/notifications/push-device";
import { NotificationSettingsForm } from "@/features/notifications/settings-form";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("notifications.settings");
  return { title: t("title") };
}

export default async function NotificationSettingsPage() {
  const t = await getTranslations("notifications");
  const api = await serverApi();
  const settings = await api.GET("/api/v1/me/notification-settings").then(loaded);
  return (
    <>
      <PageHeader
        title={t("settings.title")}
        description={t("settings.description")}
        breadcrumb={[{ label: t("title"), href: "/notifications" }, { label: t("settings.title") }]}
      />
      {settings.status === "ok" ? (
        <div className="flex flex-col gap-6">
          <Panel>
            <PanelHeader title={t("settings.channelsTitle")} />
            <PanelBody>
              <NotificationSettingsForm settings={settings.data} />
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title={t("settings.deviceTitle")} />
            <PanelBody>
              <PushDevice
                publicKey={settings.data.push_public_key}
                devices={settings.data.devices}
              />
            </PanelBody>
          </Panel>
        </div>
      ) : (
        <ForbiddenState />
      )}
    </>
  );
}

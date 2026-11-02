import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { PushDevice } from "@/features/notifications/push-device";
import { OfflineDeviceSwitch } from "@/features/offline/device-switch";
import { NotificationSettingsForm } from "@/features/notifications/settings-form";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { getCurrentUser, loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("notifications.settings");
  return { title: t("title") };
}

export default async function NotificationSettingsPage() {
  const t = await getTranslations("notifications");
  const tOffline = await getTranslations("offline.device");
  const api = await serverApi();
  const settings = await api.GET("/api/v1/me/notification-settings").then(loaded);
  const current = await getCurrentUser();
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
          {current.status === "ok" ? (
            <Panel>
              <PanelHeader title={tOffline("title")} />
              <PanelBody>
                <OfflineDeviceSwitch
                  userId={current.user.id}
                  sessionEndsAt={current.session.expiresAt}
                />
              </PanelBody>
            </Panel>
          ) : null}
        </div>
      ) : (
        <ForbiddenState />
      )}
    </>
  );
}

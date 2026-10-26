"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Menu,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuRadioGroup,
  MenuRadioItem,
  MenuSeparator,
  MenuTrigger,
} from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import { formatDateTime } from "@/lib/format";

import { chatKeys, isMuted, type Channel, type NotifyLevel } from "./model";

const HOUR_MS = 3_600_000;
const SNOOZES = [
  { key: "mute1h", ms: HOUR_MS },
  { key: "mute8h", ms: 8 * HOUR_MS },
  { key: "mute24h", ms: 24 * HOUR_MS },
  { key: "mute7d", ms: 7 * 24 * HOUR_MS },
] as const;

type Change = { notify_level?: NotifyLevel; muted_until?: string | null };

/**
 * The member's own notification level and snooze for one channel (§5.3). They change badges and push only;
 * history stays as it is. This is not the moderator's posting mute (D-058).
 */
export function NotifyMenu({ channel }: { channel: Channel }) {
  const t = useTranslations("chat.notify");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [now] = useState(() => Date.now());
  const snoozed = channel.muted_until !== null && Date.parse(channel.muted_until) > now;

  const save = useMutation({
    mutationFn: async (change: Change) =>
      unwrap(
        await api.PATCH("/api/v1/chat/channels/{channel_id}/members/me", {
          params: { path: { channel_id: channel.id } },
          body: change,
        }),
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData<{ channels: Channel[]; blocked_user_ids: string[] }>(
        chatKeys.channels,
        (data) =>
          data
            ? {
                ...data,
                channels: data.channels.map((item) =>
                  item.id === updated.id ? { ...item, ...updated } : item,
                ),
              }
            : data,
      );
      void queryClient.invalidateQueries({ queryKey: chatKeys.channel(channel.id) });
      toast({ title: t("saved") });
    },
    onError: () => toast({ title: t("failed"), tone: "danger" }),
  });

  const muted = isMuted(channel, now);
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button variant="tertiary" size="dense">
          <Icon icon={muted ? BellOff : Bell} />
          <span className="max-md:sr-only">
            {snoozed
              ? t("mutedUntil", { until: formatDateTime(channel.muted_until!) })
              : muted
                ? t("muted")
                : t("levelTitle")}
          </span>
        </Button>
      </MenuTrigger>
      <MenuContent className="min-w-60">
        <MenuLabel>{t("levelTitle")}</MenuLabel>
        <MenuRadioGroup
          value={channel.notify_level}
          onValueChange={(value) => save.mutate({ notify_level: value as NotifyLevel })}
        >
          <MenuRadioItem value="all">{t("all")}</MenuRadioItem>
          <MenuRadioItem value="mentions">{t("mentions")}</MenuRadioItem>
          <MenuRadioItem value="none">{t("none")}</MenuRadioItem>
        </MenuRadioGroup>
        <MenuSeparator />
        <MenuLabel>{t("muteTitle")}</MenuLabel>
        {SNOOZES.map((snooze) => (
          <MenuItem
            key={snooze.key}
            onSelect={() =>
              save.mutate({ muted_until: new Date(Date.now() + snooze.ms).toISOString() })
            }
          >
            {t(snooze.key)}
          </MenuItem>
        ))}
        {snoozed ? (
          <MenuItem onSelect={() => save.mutate({ muted_until: null })}>{t("unmute")}</MenuItem>
        ) : null}
      </MenuContent>
    </Menu>
  );
}

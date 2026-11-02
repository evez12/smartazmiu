"use client";

import { WifiOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { createContext, useContext, type ReactNode } from "react";

import { useOnline } from "@/lib/use-online";

import { Icon } from "./icon";

/**
 * `required`: the control needs the server and is disabled, with the reason, while the browser is offline (§13.6).
 * `local`: it works on what is already on the page (calculators, a tour step, a dialog's close button) and stays
 * enabled. See `networkDefault` for what a control is when it says nothing.
 */
export type NetworkNeed = "required" | "local";

type NetworkState = { online: boolean; reason: string };

/** Outside the provider (isolated component tests, specimens) everything is online. */
const NetworkContext = createContext<NetworkState>({ online: true, reason: "" });

export function NetworkProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("offline.network");
  const online = useOnline();
  return <NetworkContext value={{ online, reason: t("reason") }}>{children}</NetworkContext>;
}

export function useNetwork(): NetworkState {
  return useContext(NetworkContext);
}

/** The attributes of a control that is switched off because there is no connection, or nothing. */
export function useOfflineLock(need: NetworkNeed): {
  locked: boolean;
  props: { title?: string; "data-offline"?: "" };
} {
  const { online, reason } = useNetwork();
  const locked = need === "required" && !online;
  return { locked, props: locked ? { title: reason, "data-offline": "" } : {} };
}

/** The reason as visible text, for places where the page's own banner is out of sight (dialogs, sheets). */
export function OfflineNote() {
  const { online, reason } = useNetwork();
  if (online) return null;
  return (
    <p role="status" className="flex items-start gap-2 text-sm text-muted">
      <Icon icon={WifiOff} className="mt-px" />
      {reason}
    </p>
  );
}

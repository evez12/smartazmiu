"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import {
  isDismissed,
  isIosSafari,
  isStandalone,
  recordVisit,
  rememberDismissed,
  shouldOffer,
} from "@/lib/offline/install";

import { useOnline } from "@/lib/use-online";

type InstallEvent = Event & { prompt: () => Promise<void> };

type Facts = { visits: number; dismissed: boolean; standalone: boolean; ios: boolean };

/**
 * Non-modal offer to install the app. It appears from the second visit on, can be dismissed for good, and never
 * appears inside the installed app. Browsers without an install event (Safari on iOS) get the steps instead.
 */
export function InstallPrompt() {
  const online = useOnline();
  const [facts, setFacts] = useState<Facts | null>(null);
  const [event, setEvent] = useState<InstallEvent | null>(null);

  useEffect(() => {
    const read = () =>
      setFacts({
        visits: recordVisit(),
        dismissed: isDismissed(),
        standalone: isStandalone(),
        ios: isIosSafari(navigator.userAgent),
      });
    read();
    const onPrompt = (installEvent: Event) => {
      // Keeps the browser's own mini bar away; the offer is ours, at a moment of our choosing.
      installEvent.preventDefault();
      setEvent(installEvent as InstallEvent);
    };
    const onInstalled = () => {
      rememberDismissed();
      setEvent(null);
      read();
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!facts || !online || !shouldOffer({ ...facts, canPrompt: event !== null })) return null;

  const dismiss = () => {
    rememberDismissed();
    setFacts({ ...facts, dismissed: true });
  };
  return (
    <InstallOffer
      canPrompt={event !== null}
      onInstall={() => {
        void event?.prompt();
        setEvent(null);
      }}
      onDismiss={dismiss}
    />
  );
}

/** The offer itself: an install button where the browser can install, the steps where it cannot (Safari on iOS). */
export function InstallOffer({
  canPrompt,
  onInstall,
  onDismiss,
}: {
  canPrompt: boolean;
  onInstall: () => void;
  onDismiss: () => void;
}) {
  const t = useTranslations("offline.install");
  return (
    <Banner
      tone="info"
      title={t("title")}
      onDismiss={onDismiss}
      action={
        canPrompt ? (
          <Button variant="primary" size="dense" onClick={onInstall}>
            {t("action")}
          </Button>
        ) : null
      }
    >
      {canPrompt ? t("body") : t("ios")}
    </Banner>
  );
}

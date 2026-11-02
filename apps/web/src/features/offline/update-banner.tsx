"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useStore } from "zustand";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { createChatStore } from "@/features/chat/store";
import { useOptionalChatRuntime } from "@/features/chat/runtime";
import { hasUnsentText, serviceWorkerSupported, watchForUpdate } from "@/lib/offline/register";

const fallbackStore = createChatStore();

/** True while the user has text in a composer or a message still waiting to be sent; a reload would lose both. */
function useUnsentWork(): boolean {
  const runtime = useOptionalChatRuntime();
  const queued = useStore(
    runtime?.store ?? fallbackStore,
    (state) => Object.keys(state.pending).length,
  );
  const [typing, setTyping] = useState(false);
  useEffect(() => {
    const check = () => setTyping(hasUnsentText());
    document.addEventListener("input", check, true);
    const interval = setInterval(check, 1_000);
    return () => {
      document.removeEventListener("input", check, true);
      clearInterval(interval);
    };
  }, []);
  return typing || queued > 0;
}

function useWaitingWorker(): ServiceWorker | null {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  useEffect(() => {
    if (!serviceWorkerSupported()) return;
    let stop: (() => void) | undefined;
    let cancelled = false;
    void navigator.serviceWorker.ready.then((registration) => {
      if (!cancelled) stop = watchForUpdate(registration, setWaiting);
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, []);
  return waiting;
}

/** The banner itself; the button is disabled with its reason while something unsent would be lost. */
export function UpdateNotice({ unsent, onApply }: { unsent: boolean; onApply: () => void }) {
  const t = useTranslations("offline.update");
  return (
    <Banner
      tone="info"
      title={t("title")}
      action={
        <Button variant="primary" size="dense" disabled={unsent} onClick={onApply}>
          {t("action")}
        </Button>
      }
    >
      {unsent ? t("blocked") : t("body")}
    </Banner>
  );
}

/**
 * "A new version is available": the new worker waits (D-118) until the user asks for it, and the page is never
 * reloaded while something unsent would be lost.
 */
export function UpdateBanner() {
  const waiting = useWaitingWorker();
  const unsent = useUnsentWork();
  if (!waiting) return null;

  const apply = () => {
    navigator.serviceWorker.addEventListener("controllerchange", () => location.reload(), {
      once: true,
    });
    waiting.postMessage({ type: "SKIP_WAITING" });
  };
  return <UpdateNotice unsent={unsent} onApply={apply} />;
}

"use client";

import { useLocale } from "next-intl";
import { useEffect, useRef, useState } from "react";

import type { Channel } from "@/features/chat/model";
import { useChannels, useChatRuntime } from "@/features/chat/runtime";
import { useApi } from "@/lib/api/provider";
import { claimDevice } from "@/lib/offline/device";
import { isStorableChannel, SYNC_INTERVAL_MS } from "@/lib/offline/policy";
import { ensureShell, registerServiceWorker, serviceWorkerSupported } from "@/lib/offline/register";
import { clearSignOutPending, isSignOutPending, submitSignOut } from "@/lib/offline/sign-out";
import { getSnapshot, putSnapshot, readDevice } from "@/lib/offline/store";
import { onWiped, wipeOfflineData } from "@/lib/offline/wipe";

import { DEVICE_CHANGED } from "./device-events";
import {
  lastMessages,
  mergeHistory,
  toOfflineChannel,
  toOfflineMessage,
  type ChannelHistory,
} from "./model";
import { syncAll } from "./sync";
import { useOnline } from "./use-online";

/** Largest delay `setTimeout` accepts; a session end further away is checked again after this long. */
const MAX_TIMER_MS = 2 ** 31 - 1;
const PERSIST_DEBOUNCE_MS = 2_000;

type Props = { userId: string; sessionEndsAt: number; csrfToken: string };

/**
 * The device side of the offline feature for the signed-in app (D-117). It registers the service worker (only in a
 * production build), makes this user the owner of the device's data, and, when the user switched storing on,
 * keeps the schedule and the channels' newest messages up to date. It renders nothing.
 */
export function OfflineRuntime({ userId, sessionEndsAt, csrfToken }: Props) {
  const api = useApi();
  const locale = useLocale();
  const online = useOnline();
  const [enabled, setEnabled] = useState(false);
  const [claimed, setClaimed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      const device = await readDevice();
      if (!cancelled) setEnabled(Boolean(device && device.userId === userId && device.enabled));
    };
    void (async () => {
      if (isSignOutPending()) return;
      try {
        const device = await claimDevice(userId, sessionEndsAt);
        if (!cancelled) {
          setEnabled(device.enabled);
          setClaimed(true);
        }
      } catch {
        // IndexedDB unavailable (private window, blocked site data): the app works, offline use does not.
      }
    })();
    window.addEventListener(DEVICE_CHANGED, refresh);
    const stopListening = onWiped(() => setEnabled(false));
    // The session ends at an absolute time (D-040); the data is gone then even if the device never hears from the server.
    const untilEnd = Math.min(sessionEndsAt * 1000 - Date.now(), MAX_TIMER_MS);
    const endTimer = setTimeout(() => void wipeOfflineData(), Math.max(untilEnd, 0));
    return () => {
      cancelled = true;
      window.removeEventListener(DEVICE_CHANGED, refresh);
      stopListening();
      clearTimeout(endTimer);
    };
  }, [userId, sessionEndsAt]);

  useEffect(() => {
    if (!serviceWorkerSupported() || process.env.NODE_ENV !== "production" || !claimed) return;
    registerServiceWorker()
      .then((registration) => ensureShell(registration, locale))
      .catch(() => undefined);
  }, [claimed, locale]);

  // A sign-out asked for while offline reaches the server as soon as there is a connection.
  useEffect(() => {
    if (!online || !isSignOutPending()) return;
    clearSignOutPending();
    submitSignOut(csrfToken);
  }, [online, csrfToken]);

  useEffect(() => {
    if (!enabled || !online) return;
    let running = false;
    const run = (force: boolean) => {
      if (running) return;
      running = true;
      syncAll(api, userId, force)
        .catch(() => undefined)
        .finally(() => {
          running = false;
        });
    };
    // Back online or freshly switched on: refresh everything now; afterwards only what is older than the interval.
    run(true);
    const interval = setInterval(() => run(false), SYNC_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") run(false);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [api, enabled, online, userId]);

  usePersistedChannels(userId, enabled);
  return null;
}

/**
 * Messages that arrive while a channel is open are written to the stored copy as well, so leaving the app right
 * after reading does not show an older state offline. Only windows that reach the newest message are used.
 */
function usePersistedChannels(userId: string, enabled: boolean) {
  const runtime = useChatRuntime();
  const channels = useChannels();
  const known = useRef<{ storable: Channel[]; blocked: ReadonlySet<string> }>({
    storable: [],
    blocked: new Set(),
  });

  useEffect(() => {
    known.current = {
      storable: (channels.data?.channels ?? []).filter(isStorableChannel),
      blocked: new Set(channels.data?.blocked_user_ids ?? []),
    };
  }, [channels.data]);

  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const persist = async () => {
      const { windows } = runtime.store.getState();
      for (const channel of known.current.storable) {
        const window = windows[channel.id];
        if (!window || window.hasNewer || window.truncated) continue;
        const stored = await getSnapshot<ChannelHistory>(userId, "channel", channel.id);
        const live = lastMessages(Object.values(window.messages)).map((message) =>
          toOfflineMessage(message, known.current.blocked),
        );
        const history: ChannelHistory = {
          channel: toOfflineChannel(channel),
          messages: mergeHistory(stored?.data.messages ?? [], live),
        };
        await putSnapshot(userId, "channel", channel.id, history);
      }
    };
    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(() => void persist().catch(() => undefined), PERSIST_DEBOUNCE_MS);
    };
    const unsubscribe = runtime.store.subscribe((state, previous) => {
      if (state.windows !== previous.windows) schedule();
    });
    // Windows loaded before storing was switched on are stored too.
    schedule();
    return () => {
      unsubscribe();
      clearTimeout(timer);
    };
  }, [enabled, runtime.store, userId]);
}

import { STORAGE_PREFIX } from "./policy";

export const SERVICE_WORKER_URL = "/sw.js";
/** The build the running page belongs to; the worker's caches carry the same id (`next.config.ts`). */
export const BUILD_ID = process.env.NEXT_PUBLIC_BUILD_ID ?? "development";

const SHELL_MARKER = `${STORAGE_PREFIX}shell`;

export function serviceWorkerSupported(): boolean {
  return typeof navigator !== "undefined" && "serviceWorker" in navigator;
}

export function registerServiceWorker(): Promise<ServiceWorkerRegistration> {
  // The browser must never reuse a cached copy of the script, or a deploy would not be noticed.
  return navigator.serviceWorker.register(SERVICE_WORKER_URL, { updateViaCache: "none" });
}

/** Asks the active worker to store the offline page for this build and language; resolves with its answer. */
function requestShell(worker: ServiceWorker): Promise<boolean> {
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    const timer = setTimeout(() => resolve(false), 20_000);
    channel.port1.onmessage = (event) => {
      clearTimeout(timer);
      resolve(event.data === true);
    };
    worker.postMessage({ type: "PRECACHE_SHELL" }, [channel.port2]);
  });
}

/**
 * Keeps the offline page in the worker's cache for the current build and language. It is stored again after a
 * deploy, a language change or a wipe (the marker is removed with the other offline markers).
 */
export async function ensureShell(registration: ServiceWorkerRegistration, locale: string) {
  const wanted = `${BUILD_ID}:${locale}`;
  if (localStorage.getItem(SHELL_MARKER) === wanted) return;
  const ready = await navigator.serviceWorker.ready;
  const worker = ready.active ?? registration.active;
  if (worker && (await requestShell(worker))) localStorage.setItem(SHELL_MARKER, wanted);
}

/** Calls `onWaiting` when a newer worker has installed and is waiting for the page to accept it. */
export function watchForUpdate(
  registration: ServiceWorkerRegistration,
  onWaiting: (worker: ServiceWorker) => void,
): () => void {
  const check = (worker: ServiceWorker | null) => {
    // Without a controller this is the first install, not an update.
    if (worker?.state === "installed" && navigator.serviceWorker.controller) onWaiting(worker);
  };
  check(registration.waiting);
  const onFound = () => {
    const installing = registration.installing;
    installing?.addEventListener("statechange", () => check(installing));
  };
  registration.addEventListener("updatefound", onFound);
  const hourly = setInterval(() => void registration.update().catch(() => undefined), 60 * 60_000);
  return () => {
    registration.removeEventListener("updatefound", onFound);
    clearInterval(hourly);
  };
}

/** Text in a message box or reply field that has not been sent; an update must not reload the page over it. */
export function hasUnsentText(root: ParentNode = document): boolean {
  return [...root.querySelectorAll<HTMLTextAreaElement>("textarea[data-composer]")].some(
    (field) => field.value.trim().length > 0,
  );
}

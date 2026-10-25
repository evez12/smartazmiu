/**
 * Web Push in the browser: the service worker (`public/sw.js`), permission and the push subscription. The server
 * stores the subscription; the browser only ever holds its own.
 */

const WORKER_URL = "/sw.js";

export type PushSupport = "supported" | "unsupported" | "denied";

export function pushSupport(): PushSupport {
  if (
    typeof window === "undefined" ||
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    !("Notification" in window)
  ) {
    return "unsupported";
  }
  return Notification.permission === "denied" ? "denied" : "supported";
}

export class PushPermissionError extends Error {
  constructor() {
    super("Notification permission was not granted");
    this.name = "PushPermissionError";
  }
}

/** The VAPID key from the API is base64url; `PushManager.subscribe` wants the raw bytes. */
export function applicationServerKey(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = base64url.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="));
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration(WORKER_URL);
  return (await registration?.pushManager.getSubscription()) ?? null;
}

export type SubscriptionBody = { endpoint: string; keys: { p256dh: string; auth: string } };

/** Asks for permission (only on this explicit user action) and subscribes this browser. */
export async function subscribe(publicKey: string): Promise<SubscriptionBody> {
  const registration = await navigator.serviceWorker.register(WORKER_URL);
  if ((await Notification.requestPermission()) !== "granted") throw new PushPermissionError();
  await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: applicationServerKey(publicKey),
  });
  const json = subscription.toJSON();
  return {
    endpoint: subscription.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
  };
}

/** Unsubscribes this browser; returns the endpoint the server should forget. */
export async function unsubscribe(): Promise<string | null> {
  const subscription = await currentSubscription();
  if (!subscription) return null;
  await subscription.unsubscribe();
  return subscription.endpoint;
}
